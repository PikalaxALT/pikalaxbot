from sqlite3 import Connection, Row, Cursor
from typing import Optional, Callable, Tuple, Any
from contextlib import contextmanager
from re import sub, split
from discord.utils import find, get
import random


__all__ = (
    'PokeApiConnection',
    'PokeapiResource',
    'NamedPokeapiResource',
    'Pokemon',
    'PokemonHabitat',
    'PokemonShape',
    'PokemonColor',
    'PokemonSpecies',
    'ItemPocket',
    'ContestType',
    'SuperContestEffect',
    'Type',
    'Item',
    'ItemCategory',
    'ItemFlingEffect',
    'EvolutionChain',
    'Generation',
    'Region',
    'GrowthRate',
    'Move',
    'MoveTarget',
    'MoveEffect',
    'MoveDamageClass',
    'Language',
    'ContestEffect',
    'Pokedex',
    'Ability',
    'PokemonAbility',
    'PokemonForm',
    'VersionGroup',
    'PokemonType',
    'PokemonDexNumber',
    'PokemonMove',
    'MoveLearnMethod',
    'TypeEfficacy',
)


__global_cache__ = {}


class PokeApiConnection(Connection):
    @contextmanager
    def replace_row_factory(self, factory: Optional[Callable[[Cursor, Tuple[Any]], Any]]):
        old_factory = self.row_factory
        self.row_factory = factory
        yield self
        self.row_factory = old_factory

    def get_model(self, model: Callable[[Cursor, Tuple[Any]], Any], id_: Optional[int]):
        if id_ is None:
            return
        if (model, id_) in __global_cache__:
            return __global_cache__[(model, id_)]
        statement = """
        SELECT *
        FROM pokemon_v2_{}
        WHERE id = :id
        """.format(model.__name__.lower())
        with self.replace_row_factory(model) as conn:
            cur = conn.execute(statement, {'id': id_})
            result = cur.fetchone()
        return result

    def get_model_named(self, model: Callable[[Cursor, Tuple[Any]], Any], name: str, *, suffix='name', namecol='name'):
        result = find(lambda k: k[1].name == name, __global_cache__.items())
        if result:
            return result[1]
        clsname = model.__name__
        idcol = sub(r'([a-z])([A-Z])', r'\1_\2', clsname).lower()
        statement = """
        SELECT *
        FROM pokemon_v2_{0}
        WHERE id = (
            SELECT {1}_id
            FROM pokemon_v2_{0}{2}
            WHERE {3}
        )
        """.format(
            model.__name__.lower(),
            idcol,
            suffix,
            ' OR '.join('{} = \'{}\''.format(field, name) for field in split(r'[, ]+', namecol))
        )
        with self.replace_row_factory(model) as conn:
            cur = conn.execute(statement)
            result = cur.fetchone()
        return result

    def get_random_model(self, model):
        if model in __global_cache__:
            return random.choice(__global_cache__[model])
        statement = """
        SELECT *
        FROM pokemon_v2_{}
        ORDER BY random()
        """.format(model.__name__.lower())
        with self.replace_row_factory(model) as conn:
            cur = conn.execute(statement)
            result = cur.fetchone()
        return result

    def get_all_models(self, model):
        if model in __global_cache__:
            return __global_cache__[model]
        statement = """
        SELECT *
        FROM pokemon_v2_{}
        """.format(model.__name__.lower())
        with self.replace_row_factory(model) as conn:
            __global_cache__[model] = result = list(conn.execute(statement))
        return result

    def get(self, model, **kwargs):
        if model in __global_cache__:
            return get(__global_cache__[model], **kwargs)
        else:
            statement = """
            SELECT *
            FROM pokemon_v2_{}
            """.format(model.__name__.lower())
            with self.replace_row_factory(model) as conn:
                return get(conn.execute(statement), **kwargs)

    def filter(self, model, **kwargs):
        iterable = iter(self.get_all_models(model))
        while (result := get(iterable, **kwargs)) is not None:
            yield result


class PokeapiResource:
    def __init__(self, cursor: Cursor, row: Tuple[Any]):
        self._cursor: Cursor = cursor
        self._row: Row = Row(cursor, row)
        self._connection: PokeApiConnection = cursor.connection
        self.id = self._row['id']
        if 'name' in self._row:
            self._name = self._row['name']
        __global_cache__[(self.__class__, self.id)] = self

    def __eq__(self, other):
        return isinstance(other, self.__class__) and other.id == self.id

    def __hash__(self):
        return hash((self.__class__, self.id))

    def __repr__(self):
        return '<{0.__class__.__name__} id={0.id}>'.format(self)

    def get_submodel(self, model, field):
        return self._connection.get_model(model, self._row[field])


class NamedPokeapiResource(PokeapiResource):
    _language = 9

    def __init__(self, cursor: Cursor, row: Tuple[Any], *, suffix='name', namecol='name'):
        super().__init__(cursor, row)
        if isinstance(self, Language):
            self.language = self
        else:
            self.language = self._connection.get_model(Language, self._language)
        clsname = self.__class__.__name__
        idcol = sub(r'([a-z])([A-Z])', r'\1_\2', clsname).lower()
        statement = """
        SELECT {}
        FROM pokemon_v2_{}{}
        WHERE language_id = {}
        AND {}_id = :id
        """.format(namecol, clsname.lower(), suffix, self._language, idcol)
        self._columns = columns = split(r'[, ]+', namecol)
        with self._connection.replace_row_factory(None) as conn:
            cur = conn.execute(statement, {'id': self.id})
            row = cur.fetchone()
            self.name = ' | '.join(row)
            for name, value in zip(columns, row):
                setattr(self, name, value)
        results = cur.fetchone()

    def __repr__(self):
        return '<{0.__class__.__name__} id={0.id} name={0.name!r} language={0.language.name}>'.format(self)

    def __str__(self):
        return self.name


class Language(NamedPokeapiResource):
    def __init__(self, cursor: Cursor, row: Tuple[Any]):
        super().__init__(cursor, row)
        self.iso3166 = self._row['iso3166']
        self.official = bool(self._row['official'])
        self.order = self._row['order']
        self.iso639 = self._row['iso639']


class ItemFlingEffect(NamedPokeapiResource):
    def __init__(self, cursor: Cursor, row: Tuple[Any]):
        super().__init__(cursor, row, suffix='effecttext', namecol='effect')


class ItemPocket(NamedPokeapiResource):
    pass


class ItemCategory(NamedPokeapiResource):
    def __init__(self, cursor: Cursor, row: Tuple[Any]):
        super().__init__(cursor, row)
        self.item_pocket = self.get_submodel(ItemPocket, 'item_pocket_id')


class Item(NamedPokeapiResource):
    def __init__(self, cursor: Cursor, row: Tuple[Any]):
        super().__init__(cursor, row)
        self.cost = self._row['cost']
        self.fling_power = self._row['fling_power']
        self.item_category = self.get_submodel(ItemCategory, 'item_category_id')
        self.item_fling_effect = self.get_submodel(ItemFlingEffect, 'item_fling_effect_id')


class EvolutionChain(PokeapiResource):
    def __init__(self, cursor: Cursor, row: Tuple[Any]):
        super().__init__(cursor, row)
        self.baby_trigger_item = self.get_submodel(Item, 'baby_trigger_item_id')


class Region(NamedPokeapiResource):
    pass


class Generation(NamedPokeapiResource):
    def __init__(self, cursor: Cursor, row: Tuple[Any]):
        super().__init__(cursor, row)
        self.region = self.get_submodel(Region, 'region_id')


class PokemonColor(NamedPokeapiResource):
    pass


class PokemonHabitat(NamedPokeapiResource):
    pass


class PokemonShape(NamedPokeapiResource):
    pass


class GrowthRate(NamedPokeapiResource):
    def __init__(self, cursor: Cursor, row: Tuple[Any]):
        super().__init__(cursor, row, suffix='description', namecol='description')
        self.formula = self._row['formula']


class MoveDamageClass(NamedPokeapiResource):
    pass


class MoveEffect(NamedPokeapiResource):
    def __init__(self, cursor: Cursor, row: Tuple[Any]):
        super().__init__(cursor, row, suffix='effecttext', namecol='effect, short_effect')


class MoveTarget(NamedPokeapiResource):
    pass


class Type(NamedPokeapiResource):
    def __init__(self, cursor: Cursor, row: Tuple[Any]):
        super().__init__(cursor, row)
        self.generation = self.get_submodel(Generation, 'generation_id')
        self.damage_class = self.move_damage_class = self.get_submodel(MoveDamageClass, 'move_damage_class_id')


class ContestEffect(NamedPokeapiResource):
    def __init__(self, cursor: Cursor, row: Tuple[Any]):
        super().__init__(cursor, row, suffix='effecttext', namecol='effect')
        self.appeal = self._row['appeal']
        self.jam = self._row['jam']


class ContestType(NamedPokeapiResource):
    pass


class SuperContestEffect(NamedPokeapiResource):
    def __init__(self, cursor: Cursor, row: Tuple[Any]):
        super().__init__(cursor, row, suffix='flavortext', namecol='flavor_text')
        self.appeal = self._row['appeal']


class Move(NamedPokeapiResource):
    def __init__(self, cursor: Cursor, row: Tuple[Any]):
        super().__init__(cursor, row)
        self.power = self._row['power']
        self.pp = self._row['pp']
        self.accuracy = self._row['accuracy']
        self.priority = self._row['priority']
        self.effect_chance = self.move_effect_chance = self._row['move_effect_chance']
        self.generation = self.get_submodel(Generation, 'generation_id')
        self.damage_class = self.move_damage_class = self.get_submodel(MoveDamageClass, 'move_damage_class_id')
        self.effect = self.move_effect = self.get_submodel(MoveEffect, 'move_effect_id')
        self.target = self.move_target = self.get_submodel(MoveTarget, 'move_target_id')
        self.type = self.get_submodel(Type, 'type_id')
        self.contest_effect = self.get_submodel(ContestEffect, 'contest_effect_id')
        self.contest_type = self.get_submodel(ContestType, 'contest_type_id')
        self.super_contest_effect = self.get_submodel(SuperContestEffect, 'super_contest_effect_id')


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
        self.evolution_chain = self.get_submodel(EvolutionChain, 'evolution_chain_id')
        self.generation = self.get_submodel(Generation, 'generation_id')
        self.growth_rate = self.get_submodel(GrowthRate, 'growth_rate_id')
        self.color = self.pokemon_color = self.get_submodel(PokemonColor, 'pokemon_color_id')
        self.habitat = self.pokemon_habitat = self.get_submodel(PokemonHabitat, 'pokemon_habitat_id')
        self.shape = self.pokemon_shape = self.get_submodel(PokemonShape, 'pokemon_shape_id')
        self.is_legendary = bool(self._row['is_legendary'])
        self.is_mythical = bool(self._row['is_mythical'])
        self.preevo = self.evolves_from_species = self.get_submodel(PokemonSpecies, 'evolves_from_species_id')


class Pokemon(PokeapiResource):
    def __init__(self, cursor: Cursor, row: Tuple[Any]):
        super().__init__(cursor, row)
        self.order = self._row['order']
        self.height = self._row['height']
        self.weight = self._row['weight']
        self.is_default = bool(self._row['is_default'])
        self.species = self.pokemon_species = self.get_submodel(PokemonSpecies, 'pokemon_species_id')


class VersionGroup(PokeapiResource):
    def __init__(self, cursor: Cursor, row: Tuple[Any]):
        super().__init__(cursor, row)
        self.order = self._row['order']
        self.generation = self.get_submodel(Generation, 'generation_id')


class PokemonForm(NamedPokeapiResource):
    def __init__(self, cursor: Cursor, row: Tuple[Any]):
        super().__init__(cursor, row)
        self.order = self._row['order']
        self.form_name = self._row['form_name']
        self.is_default = bool(self._row['is_default'])
        self.is_battle_only = bool(self._row['is_battle_only'])
        self.is_mega = bool(self._row['is_mega'])
        self.version_group = self.get_submodel(VersionGroup, 'version_group_id')
        self.pokemon = self.get_submodel(Pokemon, 'pokemon_id')
        self.form_order = self._row['form_order']


class Pokedex(NamedPokeapiResource):
    def __init__(self, cursor: Cursor, row: Tuple[Any]):
        super().__init__(cursor, row)
        self.is_main_series = bool(self._row['is_main_series'])
        self.region = self.get_submodel(Region, 'region_id')


class Ability(NamedPokeapiResource):
    def __init__(self, cursor: Cursor, row: Tuple[Any]):
        super().__init__(cursor, row)
        self.is_main_series = bool(self._row['is_main_series'])
        self.generation = self.get_submodel(Generation, 'generation_id')


class PokemonAbility(PokeapiResource):
    def __init__(self, cursor: Cursor, row: Tuple[Any]):
        super().__init__(cursor, row)
        self.is_hidden = bool(self._row['is_hidden'])
        self.slot = self._row['slot']
        self.ability = self.get_submodel(Ability, 'ability_id')
        self.pokemon = self.get_submodel(Pokemon, 'pokemon_id')


class PokemonType(PokeapiResource):
    def __init__(self, cursor: Cursor, row: Tuple[Any]):
        super().__init__(cursor, row)
        self.slot = self._row['slot']
        self.pokemon = self.get_submodel(Pokemon, 'pokemon_id')
        self.type = self.get_submodel(Type, 'type_id')


class PokemonDexNumber(PokeapiResource):
    def __init__(self, cursor: Cursor, row: Tuple[Any]):
        super().__init__(cursor, row)
        self.pokedex_number = self._row['pokedex_number']
        self.pokemon = self.species = self.pokemon_species = self.get_submodel(PokemonSpecies, 'pokemon_species_id')
        self.pokedex = self.get_submodel(Pokedex, 'pokedex_id')


class MoveLearnMethod(NamedPokeapiResource):
    pass


class PokemonMove(PokeapiResource):
    def __init__(self, cursor: Cursor, row: Tuple[Any]):
        super().__init__(cursor, row)
        self.order = self._row['order']
        self.level = self._row['level']
        self.move = self.get_submodel(Move, 'move_id')
        self.pokemon = self.get_submodel(Pokemon, 'pokemon_id')
        self.version_group = self.get_submodel(VersionGroup, 'version_group_id')
        self.move_learn_method = self.get_submodel(MoveLearnMethod, 'move_learn_method_id')


class TypeEfficacy(PokeapiResource):
    def __init__(self, cursor: Cursor, row: Tuple[Any]):
        super().__init__(cursor, row)
        self.damage_factor = self._row['damage_factor']
        self.damage_type = self.get_submodel(Type, 'damage_type_id')
        self.target_type = self.get_submodel(Type, 'target_type_id')
