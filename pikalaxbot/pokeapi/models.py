# PikalaxBOT - A Discord bot in discord.py
# Copyright (C) 2018-2021  PikalaxALT
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from sqlite3 import Connection, Row, Cursor
from typing import Optional, TYPE_CHECKING
from contextlib import contextmanager
from re import sub
import json
from discord.ext import commands
from ..context import MyContext
if TYPE_CHECKING:
    from .types import *


__all__ = (
    'PokeApiConnection',
    'PokeapiResource',
    'NamedPokeapiResource',
    'PokeapiModels',
)


class PokeApiConnection(Connection):
    _default_language = 9

    @contextmanager
    def replace_row_factory(self, factory: Optional['RowFactory']):
        old_factory = self.row_factory
        self.row_factory = factory
        yield self
        self.row_factory = old_factory

    def get_model(self, model: 'ModelType', id_: Optional[int]) -> Optional['Model']:
        if id_ is None:
            return
        statement = """
        SELECT *
        FROM pokemon_v2_{}
        WHERE id = :id
        """.format(model.__name__.lower())
        with self.replace_row_factory(model) as conn:
            cur = conn.execute(statement, {'id': id_, 'language': conn._default_language})
            result = cur.fetchone()
        return result


class PokeapiResource:
    _namecol = None
    _suffix = None

    def __init__(self, cursor: Cursor, row: tuple):
        self._row = Row(cursor, row)
        self._connection: PokeApiConnection = cursor.connection
        self.id = self._row['id']
        if 'name' in self._row:
            self._name = self._row['name']
        else:
            self._name = None

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        self._name = value

    def __eq__(self, other):
        return isinstance(other, self.__class__) and other.id == self.id

    def __hash__(self):
        return hash((self.__class__, self.id))

    def __repr__(self):
        attrs = ', '.join(map('{0}={1!r}'.format,self._row.keys(), self._row))
        return '<{0.__class__.__name__} {1}>'.format(self, attrs)

    def get_submodel(self, model: 'ModelType', field: str) -> Optional['Model']:
        return self._connection.get_model(model, self._row[field])


class NamedPokeapiResource(PokeapiResource):
    _suffix = 'name'
    _namecol = 'name',

    def __init__(self, cursor: Cursor, row: tuple):
        super().__init__(cursor, row)
        self.language = self._connection.get_model(PokeapiModels.Language, self._connection._default_language)
        clsname = self.__class__.__name__
        idcol = sub(r'([a-z])([A-Z])', r'\1_\2', clsname).lower()
        statement = """
            SELECT {}
            FROM pokemon_v2_{}{}
            WHERE language_id = {}
            AND {}_id = :id
        """.format(
            ', '.join(self._namecol),
            clsname.lower(),
            self._suffix,
            self._connection._default_language,
            idcol
        )
        with self._connection.replace_row_factory(None) as conn:
            cur = conn.execute(statement, {'id': self.id})
            row = cur.fetchone()
        if row:
            for name, value in zip(self._namecol, row):
                setattr(self, name, value)
        else:
            for name in self._namecol:
                setattr(self, name, None)

    def __str__(self):
        if hasattr(self, 'name'):
            return self.name
        return super().__repr__()

    @classmethod
    async def convert(cls, ctx: MyContext, argument: str) -> 'NamedPokeapiResource':
        try:
            argument = int(argument)
            methd = ctx.bot.pokeapi.get_model
        except ValueError:
            methd = ctx.bot.pokeapi.get_model_named
        try:
            obj = await methd(cls, argument)
            assert obj is not None
        except Exception as e:
            raise commands.BadArgument(f'Failed to convert value "{argument}" into {cls.__name__}', argument) from e
        return obj


class PokeapiModels:
    class Language(PokeapiResource):
        def __init__(self, cursor: Cursor, row: tuple):
            super().__init__(cursor, row)
            statement = """
            SELECT name
            FROM pokemon_v2_languagename
            WHERE language_id = :language
            AND local_language_id = :default_language
            """
            self.iso3166: int = self._row['iso3166']
            self.official = bool(self._row['official'])
            self.order: int = self._row['order']
            self.iso639: int = self._row['iso639']
            with self._connection.replace_row_factory(None) as conn:
                cur = conn.execute(
                    statement,
                    {
                        'language': self.id,
                        'default_language': self._connection._default_language
                    }
                )
                try:
                    self.name, = cur.fetchone()
                except TypeError:
                    self.name = None

    class ItemFlingEffect(NamedPokeapiResource):
        _suffix = 'effecttext'
        _namecol = 'effect',

        def __init__(self, cursor: Cursor, row: tuple):
            super().__init__(cursor, row)

    class ItemPocket(NamedPokeapiResource):
        pass

    class ItemCategory(NamedPokeapiResource):
        def __init__(self, cursor: Cursor, row: tuple):
            super().__init__(cursor, row)
            self.item_pocket = self.get_submodel(PokeapiModels.ItemPocket, 'item_pocket_id')

    class Item(NamedPokeapiResource):
        def __init__(self, cursor: Cursor, row: tuple):
            super().__init__(cursor, row)
            self.cost = self._row['cost']
            self.fling_power = self._row['fling_power']
            self.item_category = self.get_submodel(PokeapiModels.ItemCategory, 'item_category_id')
            self.item_fling_effect = self.get_submodel(PokeapiModels.ItemFlingEffect, 'item_fling_effect_id')

    class EvolutionChain(PokeapiResource):
        def __init__(self, cursor: Cursor, row: tuple):
            super().__init__(cursor, row)
            self.baby_trigger_item = self.get_submodel(PokeapiModels.Item, 'baby_trigger_item_id')

    class Region(NamedPokeapiResource):
        pass

    class Generation(NamedPokeapiResource):
        def __init__(self, cursor: Cursor, row: tuple):
            super().__init__(cursor, row)
            self.region = self.get_submodel(PokeapiModels.Region, 'region_id')

    class PokemonColor(NamedPokeapiResource):
        pass

    class PokemonHabitat(NamedPokeapiResource):
        pass

    class PokemonShape(NamedPokeapiResource):
        _namecol = 'name', 'awesome_name'

        def __init__(self, cursor: Cursor, row: tuple):
            super().__init__(cursor, row)

    class GrowthRate(NamedPokeapiResource):
        _suffix = 'description'
        _namecol = 'description',

        def __init__(self, cursor: Cursor, row: tuple):
            super().__init__(cursor, row)
            self.formula = self._row['formula']

    class MoveDamageClass(NamedPokeapiResource):
        pass

    class MoveEffect(NamedPokeapiResource):
        _suffix = 'effecttext'
        _namecol = 'effect', 'short_effect',

        def __init__(self, cursor: Cursor, row: tuple):
            super().__init__(cursor, row)

    class MoveTarget(NamedPokeapiResource):
        pass

    class Type(NamedPokeapiResource):
        def __init__(self, cursor: Cursor, row: tuple):
            super().__init__(cursor, row)
            self.generation = self.get_submodel(PokeapiModels.Generation, 'generation_id')
            self.damage_class = self.move_damage_class = self.get_submodel(
                PokeapiModels.MoveDamageClass,
                'move_damage_class_id'
            )

    class ContestEffect(NamedPokeapiResource):
        _suffix = 'effecttext'
        _namecol = 'effect',

        def __init__(self, cursor: Cursor, row: tuple):
            super().__init__(cursor, row)
            self.appeal = self._row['appeal']
            self.jam = self._row['jam']

    class ContestType(NamedPokeapiResource):
        pass

    class SuperContestEffect(NamedPokeapiResource):
        _suffix = 'flavortext'
        _namecol = 'flavor_text',

        def __init__(self, cursor: Cursor, row: tuple):
            super().__init__(cursor, row)
            self.appeal = self._row['appeal']

    class Move(NamedPokeapiResource):
        def __init__(self, cursor: Cursor, row: tuple):
            super().__init__(cursor, row)
            self.power = self._row['power']
            self.pp = self._row['pp']
            self.accuracy = self._row['accuracy']
            self.priority = self._row['priority']
            self.effect_chance = self.move_effect_chance = self._row['move_effect_chance']
            self.generation = self.get_submodel(PokeapiModels.Generation, 'generation_id')
            self.damage_class = self.move_damage_class = self.get_submodel(
                PokeapiModels.MoveDamageClass,
                'move_damage_class_id'
            )
            self.effect = self.move_effect = self.get_submodel(PokeapiModels.MoveEffect, 'move_effect_id')
            self.target = self.move_target = self.get_submodel(PokeapiModels.MoveTarget, 'move_target_id')
            self.type = self.get_submodel(PokeapiModels.Type, 'type_id')
            self.contest_effect = self.get_submodel(PokeapiModels.ContestEffect, 'contest_effect_id')
            self.contest_type = self.get_submodel(PokeapiModels.ContestType, 'contest_type_id')
            self.super_contest_effect = self.get_submodel(PokeapiModels.SuperContestEffect, 'super_contest_effect_id')

    class MoveAttribute(NamedPokeapiResource):
        pass

    class MoveAttributeMap(PokeapiResource):
        def __init__(self, cursor: Cursor, row: tuple):
            super().__init__(cursor, row)
            self.move = self.get_submodel(PokeapiModels.Move, 'move_id')
            self.attribute = self.move_attribute = self.get_submodel(PokeapiModels.MoveAttribute, 'move_attribute_id')

    class PokemonSpecies(NamedPokeapiResource):
        def __init__(self, cursor: Cursor, row: tuple):
            super().__init__(cursor, row)
            self.order = self._row['order']
            self.gender_rate = self._row['gender_rate']
            self.capture_rate = self._row['capture_rate']
            self.base_happiness = self._row['base_happiness']
            self.is_baby = bool(self._row['is_baby'])
            self.hatch_counter = self._row['hatch_counter']
            self.has_gender_differences = bool(self._row['has_gender_differences'])
            self.forms_switchable = bool(self._row['forms_switchable'])
            self.evolution_chain = self.get_submodel(PokeapiModels.EvolutionChain, 'evolution_chain_id')
            self.generation = self.get_submodel(PokeapiModels.Generation, 'generation_id')
            self.growth_rate = self.get_submodel(PokeapiModels.GrowthRate, 'growth_rate_id')
            self.color = self.pokemon_color = self.get_submodel(PokeapiModels.PokemonColor, 'pokemon_color_id')
            self.habitat = self.pokemon_habitat = self.get_submodel(PokeapiModels.PokemonHabitat, 'pokemon_habitat_id')
            self.shape = self.pokemon_shape = self.get_submodel(PokeapiModels.PokemonShape, 'pokemon_shape_id')
            self.is_legendary = bool(self._row['is_legendary'])
            self.is_mythical = bool(self._row['is_mythical'])
            self.preevo = self.evolves_from_species = self.get_submodel(
                PokeapiModels.PokemonSpecies,
                'evolves_from_species_id'
            )

    class EvolutionTrigger(NamedPokeapiResource):
        pass

    class Gender(PokeapiResource):
        pass

    class Location(NamedPokeapiResource):
        def __init__(self, cursor: Cursor, row: tuple):
            super().__init__(cursor, row)
            self.region = self.get_submodel(PokeapiModels.Region, 'region_id')

    class PokemonEvolution(PokeapiResource):
        def __init__(self, cursor: Cursor, row: tuple):
            super().__init__(cursor, row)
            self.min_level = self._row['min_level']
            self.time_of_day = self._row['time_of_day']
            self.min_happiness = self._row['min_happiness']
            self.min_beauty = self._row['min_beauty']
            self.min_affection = self._row['min_affection']
            self.relative_physical_stats = self._row['relative_physical_stats']
            self.needs_overworld_rain = bool(self._row['needs_overworld_rain'])
            self.turn_upside_down = bool(self._row['turn_upside_down'])
            self.evolution_trigger = self.get_submodel(PokeapiModels.EvolutionTrigger, 'evolution_trigger_id')
            self.evolved_species = self.get_submodel(PokeapiModels.PokemonSpecies, 'evolved_species_id')
            self.gender = self.get_submodel(PokeapiModels.Gender, 'gender_id')
            self.known_move = self.get_submodel(PokeapiModels.Move, 'known_move_id')
            self.known_move_type = self.get_submodel(PokeapiModels.Type, 'known_move_type_id')
            self.party_species = self.get_submodel(PokeapiModels.PokemonSpecies, 'party_species_id')
            self.party_type = self.get_submodel(PokeapiModels.Type, 'party_type_id')
            self.trade_species = self.get_submodel(PokeapiModels.PokemonSpecies, 'trade_species_id')
            self.evolution_item = self.get_submodel(PokeapiModels.Item, 'evolution_item_id')
            self.held_item = self.get_submodel(PokeapiModels.Item, 'held_item_id')
            self.location = self.get_submodel(PokeapiModels.Location, 'location_id')

    class Pokemon(PokeapiResource):
        def __init__(self, cursor: Cursor, row: tuple):
            super().__init__(cursor, row)
            self.order = self._row['order']
            self.height = self._row['height']
            self.weight = self._row['weight']
            self.is_default = bool(self._row['is_default'])
            self.species = self.pokemon_species = self.get_submodel(PokeapiModels.PokemonSpecies, 'pokemon_species_id')

    class VersionGroup(PokeapiResource):
        def __init__(self, cursor: Cursor, row: tuple):
            super().__init__(cursor, row)
            self.order = self._row['order']
            self.generation = self.get_submodel(PokeapiModels.Generation, 'generation_id')

    class PokemonForm(NamedPokeapiResource):
        def __init__(self, cursor: Cursor, row: tuple):
            super().__init__(cursor, row)
            self.order = self._row['order']
            self.form_name = self._row['form_name']
            self.is_default = bool(self._row['is_default'])
            self.is_battle_only = bool(self._row['is_battle_only'])
            self.is_mega = bool(self._row['is_mega'])
            self.version_group = self.get_submodel(PokeapiModels.VersionGroup, 'version_group_id')
            self.pokemon = self.get_submodel(PokeapiModels.Pokemon, 'pokemon_id')
            self.form_order = self._row['form_order']

    class Pokedex(NamedPokeapiResource):
        def __init__(self, cursor: Cursor, row: tuple):
            super().__init__(cursor, row)
            self.is_main_series = bool(self._row['is_main_series'])
            self.region = self.get_submodel(PokeapiModels.Region, 'region_id')

    class Ability(NamedPokeapiResource):
        def __init__(self, cursor: Cursor, row: tuple):
            super().__init__(cursor, row)
            self.is_main_series = bool(self._row['is_main_series'])
            self.generation = self.get_submodel(PokeapiModels.Generation, 'generation_id')

    class PokemonAbility(PokeapiResource):
        def __init__(self, cursor: Cursor, row: tuple):
            super().__init__(cursor, row)
            self.is_hidden = bool(self._row['is_hidden'])
            self.slot = self._row['slot']
            self.ability = self.get_submodel(PokeapiModels.Ability, 'ability_id')
            self.pokemon = self.get_submodel(PokeapiModels.Pokemon, 'pokemon_id')

    class PokemonType(PokeapiResource):
        def __init__(self, cursor: Cursor, row: tuple):
            super().__init__(cursor, row)
            self.slot = self._row['slot']
            self.pokemon = self.get_submodel(PokeapiModels.Pokemon, 'pokemon_id')
            self.type = self.get_submodel(PokeapiModels.Type, 'type_id')

    class PokemonDexNumber(PokeapiResource):
        def __init__(self, cursor: Cursor, row: tuple):
            super().__init__(cursor, row)
            self.pokedex_number = self._row['pokedex_number']
            self.pokemon = self.species = self.pokemon_species = self.get_submodel(
                PokeapiModels.PokemonSpecies,
                'pokemon_species_id'
            )
            self.pokedex = self.get_submodel(PokeapiModels.Pokedex, 'pokedex_id')

    class MoveLearnMethod(NamedPokeapiResource):
        pass

    class PokemonMove(PokeapiResource):
        def __init__(self, cursor: Cursor, row: tuple):
            super().__init__(cursor, row)
            self.order = self._row['order']
            self.level = self._row['level']
            self.move = self.get_submodel(PokeapiModels.Move, 'move_id')
            self.pokemon = self.get_submodel(PokeapiModels.Pokemon, 'pokemon_id')
            self.version_group = self.get_submodel(PokeapiModels.VersionGroup, 'version_group_id')
            self.move_learn_method = self.get_submodel(PokeapiModels.MoveLearnMethod, 'move_learn_method_id')

    class TypeEfficacy(PokeapiResource):
        def __init__(self, cursor: Cursor, row: tuple):
            super().__init__(cursor, row)
            self.damage_factor = self._row['damage_factor']
            self.damage_type = self.get_submodel(PokeapiModels.Type, 'damage_type_id')
            self.target_type = self.get_submodel(PokeapiModels.Type, 'target_type_id')

    class PokemonSprites(PokeapiResource):
        def __init__(self, cursor: Cursor, row: tuple):
            super().__init__(cursor, row)
            self.pokemon = self.get_submodel(PokeapiModels.Pokemon, 'pokemon_id')
            self.sprites = json.loads(self._row['sprites'])

    class Stat(NamedPokeapiResource):
        def __init__(self, cursor: Cursor, row: tuple):
            super().__init__(cursor, row)
            self.is_battle_only = self._row['is_battle_only']
            self.game_index = self._row['game_index']
            self.move_damage_class = self.get_submodel(PokeapiModels.MoveDamageClass, 'move_damage_class_id')

    class PokemonStat(PokeapiResource):
        def __init__(self, cursor: Cursor, row: tuple):
            super().__init__(cursor, row)
            self.base_stat = self._row['base_stat']
            self.effort = self._row['effort']
            self.pokemon = self.get_submodel(PokeapiModels.Pokemon, 'pokemon_id')
            self.stat = self.get_submodel(PokeapiModels.Stat, 'stat_id')

    class EggGroup(NamedPokeapiResource):
        pass

    class PokemonEggGroup(PokeapiResource):
        def __init__(self, cursor: Cursor, row: tuple):
            super().__init__(cursor, row)
            self.species = self.pokemon_species = self.get_submodel(PokeapiModels.PokemonSpecies, 'pokemon_species_id')
            self.egg_group = self.get_submodel(PokeapiModels.EggGroup, 'egg_group_id')

    class Version(NamedPokeapiResource):
        def __init__(self, cursor: Cursor, row: tuple):
            super().__init__(cursor, row)
            self.version_group = self.get_submodel(PokeapiModels.VersionGroup, 'version_group_id')

    class PokemonSpeciesFlavorText(PokeapiResource):
        def __init__(self, cursor: Cursor, row: tuple):
            super().__init__(cursor, row)
            self.flavor_text = self._row['flavor_text']
            self.language = self.get_submodel(PokeapiModels.Language, 'language_id')
            self.pokemon_species = self.get_submodel(PokeapiModels.PokemonSpecies, 'pokemon_species_id')
            self.version = self.get_submodel(PokeapiModels.Version, 'version_id')

    class Machine(PokeapiResource):
        def __init__(self, cursor: Cursor, row: tuple):
            super().__init__(cursor, row)
            self.number = self.machine_number = self._row['machine_number']
            self.move = self.get_submodel(PokeapiModels.Move, 'move_id')
            self.version_group = self.get_submodel(PokeapiModels.VersionGroup, 'version_group_id')
            self.item = self.get_submodel(PokeapiModels.Item, 'item_id')
            self.growth_rate = self.get_submodel(PokeapiModels.GrowthRate, 'growth_rate_id')
