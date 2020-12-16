from sqlite3 import Connection, Row, Cursor
from typing import Optional, Callable, Tuple, Any
from contextlib import contextmanager
from re import sub
import json
from discord.ext import commands


__all__ = (
    'PokeApiConnection',
    'PokeapiResource',
    'NamedPokeapiResource',
    'PokeapiModels',
)


class PokeApiConnection(Connection):
    _default_language = 9

    @contextmanager
    def replace_row_factory(self, factory: Optional[Callable[[Cursor, Tuple[Any]], Any]]):
        old_factory = self.row_factory
        self.row_factory = factory
        yield self
        self.row_factory = old_factory

    def get_model(self, model: Callable[[Cursor, Tuple[Any]], Any], id_: Optional[int]):
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

    def __init__(self, cursor: Cursor, row: Tuple[Any]):
        self._cursor: Cursor = cursor
        self._row: Row = Row(cursor, row)
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
        attrs = ', '.join(f'{key}={value!r}' for key, value in zip(self._row.keys(), self._row))
        return '<{0.__class__.__name__} {1}>'.format(self, attrs)

    def get_submodel(self, model, field):
        return self._connection.get_model(model, self._row[field])

    @classmethod
    async def convert(cls, ctx: commands.Context, argument: str):
        try:
            argument = int(argument)
            obj = await ctx.bot.pokeapi.get_model(cls, argument)
        except ValueError:
            obj = await ctx.bot.pokeapi.get_model_named(cls, argument)
        if obj is None:
            raise commands.BadArgument(argument)
        return obj


class NamedPokeapiResource(PokeapiResource):
    _suffix = 'name'
    _namecol = 'name',

    def __init__(self, cursor: Cursor, row: Tuple[Any]):
        super().__init__(cursor, row)
        self.language: PokeapiModels.Language = self._connection.get_model(PokeapiModels.Language, self._connection._default_language)
        clsname = self.__class__.__name__
        idcol = sub(r'([a-z])([A-Z])', r'\1_\2', clsname).lower()
        statement = """
            SELECT {}
            FROM pokemon_v2_{}{}
            WHERE language_id = {}
            AND {}_id = :id
            """.format(', '.join(self._namecol), clsname.lower(), self._suffix, self._connection._default_language, idcol)
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


class PokeapiModels:
    class Language(PokeapiResource):
        def __init__(self, cursor: Cursor, row: Tuple[Any]):
            super().__init__(cursor, row)
            statement = """
            SELECT name
            FROM pokemon_v2_languagename
            WHERE language_id = :language
            AND local_language_id = :default_language
            """
            self.iso3166 = self._row['iso3166']
            self.official = bool(self._row['official'])
            self.order = self._row['order']
            self.iso639 = self._row['iso639']
            with self._connection.replace_row_factory(None) as conn:
                cur = conn.execute(statement, {'language': self.id, 'default_language': self._connection._default_language})
                try:
                    self.name, = cur.fetchone()
                except TypeError:
                    self.name = None

    class ItemFlingEffect(NamedPokeapiResource):
        _suffix = 'effecttext'
        _namecol = 'effect',

        def __init__(self, cursor: Cursor, row: Tuple[Any]):
            super().__init__(cursor, row)

    class ItemPocket(NamedPokeapiResource):
        pass

    class ItemCategory(NamedPokeapiResource):
        def __init__(self, cursor: Cursor, row: Tuple[Any]):
            super().__init__(cursor, row)
            self.item_pocket = self.get_submodel(PokeapiModels.ItemPocket, 'item_pocket_id')  # type: PokeapiModels.ItemPocket

    class Item(NamedPokeapiResource):
        def __init__(self, cursor: Cursor, row: Tuple[Any]):
            super().__init__(cursor, row)
            self.cost = self._row['cost']
            self.fling_power = self._row['fling_power']
            self.item_category = self.get_submodel(PokeapiModels.ItemCategory, 'item_category_id')  # type: PokeapiModels.ItemCategory
            self.item_fling_effect = self.get_submodel(PokeapiModels.ItemFlingEffect, 'item_fling_effect_id')  # type: PokeapiModels.ItemFlingEffect

    class EvolutionChain(PokeapiResource):
        def __init__(self, cursor: Cursor, row: Tuple[Any]):
            super().__init__(cursor, row)
            self.baby_trigger_item = self.get_submodel(PokeapiModels.Item, 'baby_trigger_item_id')  # type: PokeapiModels.Item

    class Region(NamedPokeapiResource):
        pass

    class Generation(NamedPokeapiResource):
        def __init__(self, cursor: Cursor, row: Tuple[Any]):
            super().__init__(cursor, row)
            self.region = self.get_submodel(PokeapiModels.Region, 'region_id')  # type: PokeapiModels.Region

    class PokemonColor(NamedPokeapiResource):
        pass

    class PokemonHabitat(NamedPokeapiResource):
        pass

    class PokemonShape(NamedPokeapiResource):
        _namecol = 'name', 'awesome_name'

        def __init__(self, cursor: Cursor, row: Tuple[Any]):
            super().__init__(cursor, row)

    class GrowthRate(NamedPokeapiResource):
        _suffix = 'description'
        _namecol = 'description',

        def __init__(self, cursor: Cursor, row: Tuple[Any]):
            super().__init__(cursor, row)
            self.formula = self._row['formula']

    class MoveDamageClass(NamedPokeapiResource):
        pass

    class MoveEffect(NamedPokeapiResource):
        _suffix = 'effecttext'
        _namecol = 'effect', 'short_effect',

        def __init__(self, cursor: Cursor, row: Tuple[Any]):
            super().__init__(cursor, row)

    class MoveTarget(NamedPokeapiResource):
        pass

    class Type(NamedPokeapiResource):
        def __init__(self, cursor: Cursor, row: Tuple[Any]):
            super().__init__(cursor, row)
            self.generation = self.get_submodel(PokeapiModels.Generation, 'generation_id')  # type: PokeapiModels.Generation
            self.damage_class = self.move_damage_class = self.get_submodel(PokeapiModels.MoveDamageClass, 'move_damage_class_id')  # type: PokeapiModels.MoveDamageClass

    class ContestEffect(NamedPokeapiResource):
        _suffix = 'effecttext'
        _namecol = 'effect',

        def __init__(self, cursor: Cursor, row: Tuple[Any]):
            super().__init__(cursor, row)
            self.appeal = self._row['appeal']
            self.jam = self._row['jam']

    class ContestType(NamedPokeapiResource):
        pass

    class SuperContestEffect(NamedPokeapiResource):
        _suffix = 'flavortext'
        _namecol = 'flavor_text',

        def __init__(self, cursor: Cursor, row: Tuple[Any]):
            super().__init__(cursor, row)
            self.appeal = self._row['appeal']

    class Move(NamedPokeapiResource):
        def __init__(self, cursor: Cursor, row: Tuple[Any]):
            super().__init__(cursor, row)
            self.power = self._row['power']
            self.pp = self._row['pp']
            self.accuracy = self._row['accuracy']
            self.priority = self._row['priority']
            self.effect_chance = self.move_effect_chance = self._row['move_effect_chance']
            self.generation = self.get_submodel(PokeapiModels.Generation, 'generation_id')  # type: PokeapiModels.Generation
            self.damage_class = self.move_damage_class = self.get_submodel(PokeapiModels.MoveDamageClass, 'move_damage_class_id')  # type: PokeapiModels.MoveDamageClass
            self.effect = self.move_effect = self.get_submodel(PokeapiModels.MoveEffect, 'move_effect_id')  # type: PokeapiModels.MoveEffect
            self.target = self.move_target = self.get_submodel(PokeapiModels.MoveTarget, 'move_target_id')  # type: PokeapiModels.MoveTarget
            self.type = self.get_submodel(PokeapiModels.Type, 'type_id')  # type: PokeapiModels.Type
            self.contest_effect = self.get_submodel(PokeapiModels.ContestEffect, 'contest_effect_id')  # type: PokeapiModels.ContestEffect
            self.contest_type = self.get_submodel(PokeapiModels.ContestType, 'contest_type_id')  # type: PokeapiModels.ContestType
            self.super_contest_effect = self.get_submodel(PokeapiModels.SuperContestEffect, 'super_contest_effect_id')  # type: PokeapiModels.SuperContestEffect

    class PokemonSpecies(NamedPokeapiResource):
        def __init__(self, cursor: Cursor, row: Tuple[Any]):
            super().__init__(cursor, row)
            self.order = self._row['order']
            self.gender_rate = self._row['gender_rate']
            self.capture_rate = self._row['capture_rate']
            self.base_happiness = self._row['base_happiness']
            self.is_baby = bool(self._row['is_baby'])
            self.hatch_counter = self._row['hatch_counter']
            self.has_gender_differences = bool(self._row['has_gender_differences'])
            self.forms_switchable = bool(self._row['forms_switchable'])
            self.evolution_chain = self.get_submodel(PokeapiModels.EvolutionChain, 'evolution_chain_id')  # type: PokeapiModels.EvolutionChain
            self.generation = self.get_submodel(PokeapiModels.Generation, 'generation_id')  # type: PokeapiModels.Generation
            self.growth_rate = self.get_submodel(PokeapiModels.GrowthRate, 'growth_rate_id')  # type: PokeapiModels.GrowthRate
            self.color = self.pokemon_color = self.get_submodel(PokeapiModels.PokemonColor, 'pokemon_color_id')  # type: PokeapiModels.PokemonColor
            self.habitat = self.pokemon_habitat = self.get_submodel(PokeapiModels.PokemonHabitat, 'pokemon_habitat_id')  # type: PokeapiModels.PokemonHabitat
            self.shape = self.pokemon_shape = self.get_submodel(PokeapiModels.PokemonShape, 'pokemon_shape_id')  # type: PokeapiModels.PokemonShape
            self.is_legendary = bool(self._row['is_legendary'])
            self.is_mythical = bool(self._row['is_mythical'])
            self.preevo = self.evolves_from_species = self.get_submodel(PokeapiModels.PokemonSpecies, 'evolves_from_species_id')  # type: PokeapiModels.PokemonSpecies

    class EvolutionTrigger(NamedPokeapiResource):
        pass

    class Gender(PokeapiResource):
        pass

    class Location(NamedPokeapiResource):
        def __init__(self, cursor: Cursor, row: Tuple[Any]):
            super().__init__(cursor, row)
            self.region = self.get_submodel(PokeapiModels.Region, 'region_id')  # type: PokeapiModels.Region

    class PokemonEvolution(PokeapiResource):
        def __init__(self, cursor: Cursor, row: Tuple[Any]):
            super().__init__(cursor, row)
            self.min_level = self._row['min_level']
            self.time_of_day = self._row['time_of_day']
            self.min_happiness = self._row['min_happiness']
            self.min_beauty = self._row['min_beauty']
            self.min_affection = self._row['min_affection']
            self.relative_physical_stats = self._row['relative_physical_stats']
            self.needs_overworld_rain = bool(self._row['needs_overworld_rain'])
            self.turn_upside_down = bool(self._row['turn_upside_down'])
            self.evolution_trigger = self.get_submodel(PokeapiModels.EvolutionTrigger, 'evolution_trigger_id')  # type: PokeapiModels.EvolutionTrigger
            self.evolved_species = self.get_submodel(PokeapiModels.PokemonSpecies, 'evolved_species_id')  # type: PokeapiModels.PokemonSpecies
            self.gender = self.get_submodel(PokeapiModels.Gender, 'gender_id')  # type: PokeapiModels.Gender
            self.known_move = self.get_submodel(PokeapiModels.Move, 'known_move_id')  # type: PokeapiModels.Move
            self.known_move_type = self.get_submodel(PokeapiModels.Type, 'known_move_type_id')  # type: PokeapiModels.Type
            self.party_species = self.get_submodel(PokeapiModels.PokemonSpecies, 'party_species_id')  # type: PokeapiModels.PokemonSpecies
            self.party_type = self.get_submodel(PokeapiModels.Type, 'party_type_id')  # type: PokeapiModels.Type
            self.trade_species = self.get_submodel(PokeapiModels.PokemonSpecies, 'trade_species_id')  # type: PokeapiModels.PokemonSpecies
            self.evolution_item = self.get_submodel(PokeapiModels.Item, 'evolution_item_id')  # type: PokeapiModels.Item
            self.held_item = self.get_submodel(PokeapiModels.Item, 'held_item_id')  # type: PokeapiModels.Item
            self.location = self.get_submodel(PokeapiModels.Location, 'location_id')  # type: PokeapiModels.Location

    class Pokemon(PokeapiResource):
        def __init__(self, cursor: Cursor, row: Tuple[Any]):
            super().__init__(cursor, row)
            self.order = self._row['order']
            self.height = self._row['height']
            self.weight = self._row['weight']
            self.is_default = bool(self._row['is_default'])
            self.species = self.pokemon_species = self.get_submodel(PokeapiModels.PokemonSpecies, 'pokemon_species_id')  # type: PokeapiModels.PokemonSpecies

    class VersionGroup(PokeapiResource):
        def __init__(self, cursor: Cursor, row: Tuple[Any]):
            super().__init__(cursor, row)
            self.order = self._row['order']
            self.generation = self.get_submodel(PokeapiModels.Generation, 'generation_id')  # type: PokeapiModels.Generation

    class PokemonForm(NamedPokeapiResource):
        def __init__(self, cursor: Cursor, row: Tuple[Any]):
            super().__init__(cursor, row)
            self.order = self._row['order']
            self.form_name = self._row['form_name']
            self.is_default = bool(self._row['is_default'])
            self.is_battle_only = bool(self._row['is_battle_only'])
            self.is_mega = bool(self._row['is_mega'])
            self.version_group = self.get_submodel(PokeapiModels.VersionGroup, 'version_group_id')  # type: PokeapiModels.VersionGroup
            self.pokemon = self.get_submodel(PokeapiModels.Pokemon, 'pokemon_id')  # type: PokeapiModels.Pokemon
            self.form_order = self._row['form_order']

    class Pokedex(NamedPokeapiResource):
        def __init__(self, cursor: Cursor, row: Tuple[Any]):
            super().__init__(cursor, row)
            self.is_main_series = bool(self._row['is_main_series'])
            self.region = self.get_submodel(PokeapiModels.Region, 'region_id')  # type: PokeapiModels.Region

    class Ability(NamedPokeapiResource):
        def __init__(self, cursor: Cursor, row: Tuple[Any]):
            super().__init__(cursor, row)
            self.is_main_series = bool(self._row['is_main_series'])
            self.generation = self.get_submodel(PokeapiModels.Generation, 'generation_id')  # type: PokeapiModels.Generation

    class PokemonAbility(PokeapiResource):
        def __init__(self, cursor: Cursor, row: Tuple[Any]):
            super().__init__(cursor, row)
            self.is_hidden = bool(self._row['is_hidden'])
            self.slot = self._row['slot']
            self.ability = self.get_submodel(PokeapiModels.Ability, 'ability_id')  # type: PokeapiModels.Ability
            self.pokemon = self.get_submodel(PokeapiModels.Pokemon, 'pokemon_id')  # type: PokeapiModels.Pokemon

    class PokemonType(PokeapiResource):
        def __init__(self, cursor: Cursor, row: Tuple[Any]):
            super().__init__(cursor, row)
            self.slot = self._row['slot']
            self.pokemon = self.get_submodel(PokeapiModels.Pokemon, 'pokemon_id')  # type: PokeapiModels.Pokemon
            self.type = self.get_submodel(PokeapiModels.Type, 'type_id')  # type: PokeapiModels.Type

    class PokemonDexNumber(PokeapiResource):
        def __init__(self, cursor: Cursor, row: Tuple[Any]):
            super().__init__(cursor, row)
            self.pokedex_number = self._row['pokedex_number']
            self.pokemon = self.species = self.pokemon_species = self.get_submodel(PokeapiModels.PokemonSpecies, 'pokemon_species_id')  # type: PokeapiModels.PokemonSpecies
            self.pokedex = self.get_submodel(PokeapiModels.Pokedex, 'pokedex_id')  # type: PokeapiModels.Pokedex

    class MoveLearnMethod(NamedPokeapiResource):
        pass

    class PokemonMove(PokeapiResource):
        def __init__(self, cursor: Cursor, row: Tuple[Any]):
            super().__init__(cursor, row)
            self.order = self._row['order']
            self.level = self._row['level']
            self.move = self.get_submodel(PokeapiModels.Move, 'move_id')  # type: PokeapiModels.Move
            self.pokemon = self.get_submodel(PokeapiModels.Pokemon, 'pokemon_id')  # type: PokeapiModels.Pokemon
            self.version_group = self.get_submodel(PokeapiModels.VersionGroup, 'version_group_id')  # type: PokeapiModels.VersionGroup
            self.move_learn_method = self.get_submodel(PokeapiModels.MoveLearnMethod, 'move_learn_method_id')  # type: PokeapiModels.MoveLearnMethod

    class TypeEfficacy(PokeapiResource):
        def __init__(self, cursor: Cursor, row: Tuple[Any]):
            super().__init__(cursor, row)
            self.damage_factor = self._row['damage_factor']
            self.damage_type = self.get_submodel(PokeapiModels.Type, 'damage_type_id')  # type: PokeapiModels.Type
            self.target_type = self.get_submodel(PokeapiModels.Type, 'target_type_id')  # type: PokeapiModels.Type

    class PokemonSprites(PokeapiResource):
        def __init__(self, cursor: Cursor, row: Tuple[Any]):
            super().__init__(cursor, row)
            self.pokemon = self.get_submodel(PokeapiModels.Pokemon, 'pokemon_id')  # type: PokeapiModels.Pokemon
            self.sprites = json.loads(self._row['sprites'])

    class Stat(NamedPokeapiResource):
        def __init__(self, cursor: Cursor, row: Tuple[Any]):
            super().__init__(cursor, row)
            self.is_battle_only = self._row['is_battle_only']
            self.game_index = self._row['game_index']
            self.move_damage_class = self.get_submodel(PokeapiModels.MoveDamageClass, 'move_damage_class_id')  # type: PokeapiModels.MoveDamageClass

    class PokemonStat(PokeapiResource):
        def __init__(self, cursor: Cursor, row: Tuple[Any]):
            super().__init__(cursor, row)
            self.base_stat = self._row['base_stat']
            self.effort = self._row['effort']
            self.pokemon = self.get_submodel(PokeapiModels.Pokemon, 'pokemon_id')  # type: PokeapiModels.Pokemon
            self.stat = self.get_submodel(PokeapiModels.Stat, 'stat_id')  # type: PokeapiModels.Stat

    class EggGroup(NamedPokeapiResource):
        pass

    class PokemonEggGroup(PokeapiResource):
        def __init__(self, cursor: Cursor, row: Tuple[Any]):
            super().__init__(cursor, row)
            self.species = self.pokemon_species = self.get_submodel(PokeapiModels.PokemonSpecies, 'pokemon_species_id')  # type: PokeapiModels.PokemonSpecies
            self.egg_group = self.get_submodel(PokeapiModels.EggGroup, 'egg_group_id')  # type: PokeapiModels.EggGroup

    class Version(NamedPokeapiResource):
        def __init__(self, cursor: Cursor, row: Tuple[Any]):
            super().__init__(cursor, row)
            self.version_group = self.get_submodel(PokeapiModels.VersionGroup, 'version_group_id')  # type: PokeapiModels.VersionGroup

    class PokemonSpeciesFlavorText(PokeapiResource):
        def __init__(self, cursor: Cursor, row: Tuple[Any]):
            super().__init__(cursor, row)
            self.flavor_text = self._row['flavor_text']
            self.language = self.get_submodel(PokeapiModels.Language, 'language_id')  # type: PokeapiModels.Language
            self.pokemon_species = self.get_submodel(PokeapiModels.PokemonSpecies, 'pokemon_species_id')  # type: PokeapiModels.PokemonSpecies
            self.version = self.get_submodel(PokeapiModels.Version, 'version_id')  # type: PokeapiModels.Version
