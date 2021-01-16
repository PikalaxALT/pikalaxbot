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

import asqlite3
import re
from typing import Optional, Callable, Union, TYPE_CHECKING
from .models import *
from .errors import *
from contextlib import asynccontextmanager as acm
import difflib
import os
import asyncio
from operator import attrgetter
import functools
if TYPE_CHECKING:
    from .types import *


__all__ = 'PokeApi',


class PokeApi(asqlite3.Connection, PokeapiModels):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._lock = asyncio.Lock()
        self._enabled = True

        _garbage_pat = re.compile(r'[. \t-\'"]')

        self.differ = difflib.SequenceMatcher(lambda s: _garbage_pat.match(s) is not None)
        self._connection: Optional[PokeApiConnection]

    async def _execute(self, fn, *args, **kwargs):
        if not self._enabled:
            raise PokeapiDisabled('PokeAPI resource is disabled')
        return await super()._execute(fn, *args, **kwargs)

    async def _connect(self) -> "PokeApi":
        class Product:
            def __init__(self):
                self.result = 1.0

            def step(self, value):
                self.result *= value

            def finalize(self):
                return self.result

        await super()._connect()
        await self.create_function(
            'FUZZY_RATIO',
            2,
            lambda a, b: difflib.SequenceMatcher(a=a.lower(), b=b.lower()).ratio(),
            deterministic=True
        )
        await self.create_aggregate('PRODUCT', 1, Product)
        return self

    @staticmethod
    def _clean_name(name):
        name = name.replace('♀', '_F').replace('♂', '_M').replace('é', 'e')
        name = re.sub(r'\W+', '_', name).title()
        return name

    # Generic getters

    @acm
    async def replace_row_factory(self, factory: Optional['RowFactory']) -> 'PokeApi':
        if self._connection is None:
            await self._connect()
        async with self._lock:
            old_factory = self.row_factory
            self.row_factory = factory
            yield self
            self.row_factory = old_factory

    @functools.cache
    def resolve_model(self, model: Union[str, 'ModelType']) -> 'ModelType':
        if isinstance(model, str):
            model = getattr(PokeapiModels, model)
        if not issubclass(model, PokeapiResource):
            raise TypeError('Expected PokeapiResource or NamedPokeapiResource, got {0.__name__}'.format(model))
        return model

    async def get_model(self, model: Union[str, 'ModelType'], id_: int) -> Optional['Model']:
        model = self.resolve_model(model)
        if id_ is None:
            return
        statement = """
        SELECT *
        FROM pokemon_v2_{}
        WHERE id = :id
        """.format(model.__name__.lower())
        async with self.replace_row_factory(model) as conn:
            async with conn.execute(statement, {'id': id_}) as cur:
                result = await cur.fetchone()
        return result

    @acm
    async def all_models_cursor(self, model: Union[str, 'ModelType']) -> asqlite3.Cursor:
        model = self.resolve_model(model)
        statement = """
        SELECT *
        FROM pokemon_v2_{}
        """.format(model.__name__.lower())
        async with self.replace_row_factory(model) as conn:
            async with conn.execute(statement) as cur:
                yield cur

    async def get_all_models(self, model: Union[str, 'ModelType']) -> list['Model']:
        async with self.all_models_cursor(model) as cur:
            result = await cur.fetchall()
        return result

    async def find(self, predicate: Callable[..., bool], model: Union[str, 'ModelType']) -> Optional['Model']:
        async with self.all_models_cursor(model) as seq:
            async for element in seq:  # type: PokeapiResource
                if predicate(element):
                    return element
            return None

    async def filter(self, model: Union[str, 'ModelType'], **attrs):
        _all = all
        attrget = attrgetter
        async with self.all_models_cursor(model) as iterable:

            if len(attrs) == 1:
                k, v = attrs.popitem()
                pred = attrget(k.replace('__', '.'))
                async for elem in iterable:
                    if pred(elem) == v:
                        yield elem
            else:
                converted = [
                    (attrget(attr.replace('__', '.')), value)
                    for attr, value in attrs.items()
                ]

                async for elem in iterable:  # type: Model
                    if _all(pred(elem) == value for pred, value in converted):
                        yield elem

    async def get(self, model: Union[str, 'ModelType'], **attrs) -> Optional['Model']:
        async for item in self.filter(model, **attrs):
            return item

    async def get_model_named(self, model: Union[str, 'ModelType'], name: str, *, cutoff=0.9) -> Optional['Model']:
        model = self.resolve_model(model)
        statement = """
        SELECT *, CASE
            WHEN EXISTS(
                SELECT *
                FROM pragma_table_info('pokemon_v2_{0}')
                WHERE name = 'name'
            ) THEN FUZZY_RATIO(pv2t.name, :name)
            ELSE FUZZY_RATIO(pv2n.name, :name)
        END ratio
        FROM pokemon_v2_{0} pv2t
        INNER JOIN pokemon_v2_{0}name pv2n ON pv2t.id = pv2n.{1}_id
        WHERE ratio > :cutoff
        AND pv2n.language_id = :language
        ORDER BY ratio DESC
        """.format(model.__name__.lower(), re.sub(r'([a-z])([A-Z])', r'\1_\2', model.__name__).lower())
        async with self.replace_row_factory(model) as conn:
            async with conn.execute(
                    statement,
                    {
                        'cutoff': cutoff,
                        'language': self._conn._default_language,
                        'name': name
                    }
            ) as cur:
                obj = await cur.fetchone()
        return obj

    async def get_names_from(self, table: Union[str, 'ModelType'], *, clean=False):
        """Generic method to get a list of all names from a PokeApi table."""
        async with self.all_models_cursor(table) as cur:
            async for obj in cur:
                yield self.get_name(obj, clean=clean)

    def get_name(self, item: NamedPokeapiResource, *, clean=False) -> str:
        return self._clean_name(item.name) if clean else item.name

    async def get_name_by_id(self, model: Union[str, 'ModelType'], id_: int, *, clean=False):
        """Generic method to get the name of a PokeApi object given only its ID."""
        obj = await self.get_model(model, id_)
        return obj and self.get_name(obj, clean=clean)

    async def get_random(self, model: Union[str, 'ModelType']) -> Optional['Model']:
        """Generic method to get a random PokeApi object."""
        model = self.resolve_model(model)
        statement = """
        SELECT *
        FROM pokemon_v2_{}
        ORDER BY random()
        """.format(model.__name__.lower())
        async with self.replace_row_factory(model) as conn:
            async with conn.execute(statement) as cur:
                obj = await cur.fetchone()
        return obj
    
    async def get_random_name(self, table: Union[str, 'ModelType'], *, clean=False) -> Optional[str]:
        """Generic method to get a random PokeApi object name."""
        obj = await self.get_random(table)
        return obj and self.get_name(obj, clean=clean)

    # Specific getters, defined for type-hints

    def get_species(self, id_):
        """Get a Pokemon species by ID"""
        return self.get_model(PokeapiModels.PokemonSpecies, id_)

    def random_species(self):
        """Get a random Pokemon species"""
        return self.get_random(PokeapiModels.PokemonSpecies)

    def get_mon_name(self, mon: PokeapiModels.PokemonSpecies, *, clean=False):
        """Get the name of a Pokemon species"""
        return self.get_name(mon, clean=clean)

    def random_species_name(self, *, clean=False):
        """Get the name of a random Pokemon species"""
        return self.get_random_name(PokeapiModels.PokemonSpecies, clean=clean)

    def get_species_by_name(self, name: str):
        """Get a Pokemon species given its name"""
        return self.get_model_named(PokeapiModels.PokemonSpecies, name)

    def get_forme_name(self, mon: PokeapiModels.PokemonForm, *, clean=False):
        """Get a Pokemon forme's name"""
        return self.get_name(mon, clean=clean)

    def random_move(self):
        """Get a random move"""
        return self.get_random(PokeapiModels.Move)

    def get_move_name(self, move: PokeapiModels.Move, *, clean=False):
        """Get a move's name"""
        return self.get_name(move, clean=clean)

    def random_move_name(self, *, clean=False):
        """Get a random move's name"""
        return self.get_random_name(PokeapiModels.Move, clean=clean)

    def get_move_by_name(self, name: str):
        """Get a move given its name"""
        return self.get_model_named(PokeapiModels.Move, name)

    def get_mon_color(self, mon: PokeapiModels.PokemonSpecies):
        """Get the object representing the Pokemon species' color"""
        return mon.pokemon_color

    def get_pokemon_color_by_name(self, name: str):
        """Get a Pokemon color given its name"""
        return self.get_model_named(PokeapiModels.PokemonColor, name)

    def get_pokemon_color_name(self, color: PokeapiModels.PokemonColor, *, clean=False):
        """Get the name of a Pokemon color"""
        return self.get_name(color, clean=clean)

    def get_name_of_mon_color(self, mon: PokeapiModels.PokemonSpecies, *, clean=False):
        """Get the name of a Pokemon species' color"""
        return self.get_name(mon.pokemon_color, clean=clean)

    def get_ability_by_name(self, name: str):
        """Get an ability given its name"""
        return self.get_model_named(PokeapiModels.Ability, name)

    def get_ability_name(self, ability: PokeapiModels.Ability, *, clean=False):
        """Get the name of an ability"""
        return self.get_name(ability, clean=clean)

    def get_type_by_name(self, name: str):
        """Get a Pokemon type given its name"""
        return self.get_model_named(PokeapiModels.Type, name)

    def get_type_name(self, type_: PokeapiModels.Type, *, clean=False):
        """Get the name of a type"""
        return self.get_name(type_, clean=clean)

    def get_pokedex_by_name(self, name: str):
        """Get a Pokedex given its name"""
        return self.get_model_named(PokeapiModels.Pokedex, name)

    def get_pokedex_name(self, dex: PokeapiModels.Pokedex, *, clean=False):
        """Get the name of a pokedex"""
        return self.get_name(dex, clean=clean)

    # Aliases

    get_pokemon = get_species
    random_pokemon = random_species
    get_pokemon_name = get_mon_name
    get_species_name = get_mon_name
    get_pokemon_species_name = get_mon_name
    random_pokemon_name = random_species_name
    get_pokemon_by_name = get_species_by_name
    get_pokemon_species_by_name = get_species_by_name
    get_color_by_name = get_pokemon_color_by_name
    get_color_name = get_pokemon_color_name

    # Nonstandard methods

    async def get_mon_types(self, mon: PokeapiModels.PokemonSpecies) -> list[PokeapiModels.Type]:
        """Returns a list of types for that Pokemon"""
        statement = """
        SELECT *
        FROM pokemon_v2_type
        INNER JOIN pokemon_v2_pokemontype ON pokemon_v2_type.id = pokemon_v2_pokemontype.type_id
        INNER JOIN pokemon_v2_pokemon ON pokemon_v2_pokemontype.pokemon_id = pokemon_v2_pokemon.id
        WHERE pokemon_species_id = :id
        AND is_default = TRUE
        """
        async with self.replace_row_factory(PokeapiModels.Type) as conn:
            result = await conn.execute_fetchall(statement, {'id': mon.id})
        return result

    async def get_mon_matchup_against_type(self, mon: PokeapiModels.PokemonSpecies, type_: PokeapiModels.Type) -> float:
        """Calculates whether a type is effective or not against a mon"""
        statement = """
        SELECT PRODUCT(damage_factor / 100.0)
        FROM pokemon_v2_typeefficacy
        INNER JOIN pokemon_v2_pokemontype pv2t ON pv2t.type_id = pokemon_v2_typeefficacy.target_type_id
        INNER JOIN pokemon_v2_pokemon pv2p ON pv2p.id = pv2t.pokemon_id
        WHERE pokemon_species_id = :mon_id
        AND damage_type_id = :damage_type
        AND is_default = TRUE
        """

        async with self.replace_row_factory(None) as conn:
            async with conn.execute(statement, {'damage_type': type_.id, 'mon_id': mon.id}) as cur:
                result, = await cur.fetchone()
        return result

    async def get_mon_matchup_against_move(self, mon: PokeapiModels.PokemonSpecies, move: PokeapiModels.Move) -> float:
        """Calculates whether a move is effective or not against a mon"""
        if move.id == 560:  # Flying Press
            statement = """
            SELECT PRODUCT(damage_factor / 100.0)
            FROM pokemon_v2_typeefficacy
            INNER JOIN pokemon_v2_pokemontype pv2t ON pv2t.type_id = pokemon_v2_typeefficacy.target_type_id
            INNER JOIN pokemon_v2_pokemon pv2p ON pv2p.id = pv2t.pokemon_id
            WHERE pokemon_species_id = :mon_id
            AND damage_type_id IN (2, 3)
            AND is_default = TRUE
            """
            async with self.replace_row_factory(None) as conn:
                async with conn.execute(statement, {'mon_id': mon.id}) as cur:
                    result, = await cur.fetchone()
            result = result and min(max(result, 0.5), 2)
        else:
            result = await self.get_mon_matchup_against_type(mon, move.type)
        return result

    async def get_mon_matchup_against_mon(
            self,
            mon: PokeapiModels.PokemonSpecies,
            mon2: PokeapiModels.PokemonSpecies
    ) -> list[float]:
        """For each type mon2 has, determines its effectiveness against mon"""

        statement = """
        SELECT pokemon_v2_typeefficacy.damage_type_id, PRODUCT(damage_factor / 100.0)
        FROM pokemon_v2_typeefficacy
        INNER JOIN pokemon_v2_pokemontype pv2t ON pokemon_v2_typeefficacy.damage_type_id = pv2t.type_id
        INNER JOIN pokemon_v2_pokemontype pv2t2 ON pokemon_v2_typeefficacy.target_type_id = pv2t2.type_id
        INNER JOIN pokemon_v2_pokemon p ON p.id = pv2t.pokemon_id
        INNER JOIN pokemon_v2_pokemon p2 ON p2.id = pv2t2.pokemon_id
        WHERE p.pokemon_species_id = :mon2_id
        AND p.is_default = TRUE
        AND p2.pokemon_species_id = :mon_id
        AND p2.is_default = TRUE
        GROUP BY pokemon_v2_typeefficacy.damage_type_id
        """

        async with self.replace_row_factory(None) as conn:
            result = dict(await conn.execute_fetchall(statement, {'mon2_id': mon2.id, 'mon_id': mon.id}))

        return list(result.values())

    async def get_preevo(self, mon: PokeapiModels.PokemonSpecies):
        """Get the species the given Pokemon evoles from"""
        return mon.evolves_from_species

    async def get_evos(self, mon: PokeapiModels.PokemonSpecies) -> list[PokeapiModels.PokemonSpecies]:
        """Get all species the given Pokemon evolves into"""
        statement = """
        SELECT *
        FROM pokemon_v2_pokemonspecies
        WHERE evolves_from_species_id = :id
        """
        async with self.replace_row_factory(PokeapiModels.PokemonSpecies) as conn:
            result = await conn.execute_fetchall(statement, {'id': mon.id})
        return result

    async def get_mon_learnset(self, mon: PokeapiModels.PokemonSpecies) -> list[PokeapiModels.Move]:
        """Returns a list of all the moves the Pokemon can learn"""
        statement = """
        SELECT DISTINCT *
        FROM pokemon_v2_move
        INNER JOIN pokemon_v2_pokemonmove pv2p ON pokemon_v2_move.id = pv2p.move_id
        INNER JOIN pokemon_v2_pokemon pv2p2 ON pv2p.pokemon_id = pv2p2.id
        WHERE pokemon_species_id = :id
        AND is_default = TRUE
        """
        async with self.replace_row_factory(PokeapiModels.Move) as conn:
            result = await conn.execute_fetchall(statement, {'id': mon.id})
        return result
    
    async def mon_can_learn_move(self, mon: PokeapiModels.PokemonSpecies, move: PokeapiModels.Move) -> bool:
        """Returns whether a move is in the Pokemon's learnset"""
        statement = """
        SELECT EXISTS (
            SELECT *
            FROM pokemon_v2_pokemonmove
            INNER JOIN pokemon_v2_pokemon pv2p ON pv2p.id = pokemon_v2_pokemonmove.pokemon_id
            WHERE move_id = :move_id
            AND pokemon_species_id = :mon_id
            AND is_default = TRUE
        )
        """
        async with self.replace_row_factory(None) as conn:
            async with conn.execute(statement, {'mon_id': mon.id, 'move_id': move.id}) as cur:
                result, = await cur.fetchone()
        return bool(result)

    async def get_mon_abilities(self, mon: PokeapiModels.PokemonSpecies) -> list[PokeapiModels.Ability]:
        """Returns a list of abilities for that Pokemon"""
        statement = """
        SELECT *
        FROM pokemon_v2_ability
        INNER JOIN pokemon_v2_pokemonability p ON pokemon_v2_ability.id = p.ability_id
        INNER JOIN pokemon_v2_pokemon pv2p ON p.pokemon_id = pv2p.id
        WHERE pokemon_species_id = :id
        AND is_default = TRUE
        """
        async with self.replace_row_factory(PokeapiModels.Ability) as conn:
            result = await conn.execute_fetchall(statement, {'id': mon.id})
        return result

    async def get_mon_abilities_with_flags(
            self,
            mon: PokeapiModels.PokemonSpecies
    ) -> list[PokeapiModels.PokemonAbility]:
        statement = """
        SELECT *
        FROM pokemon_v2_pokemonability p
        INNER JOIN pokemon_v2_pokemon pv2p ON p.pokemon_id = pv2p.id
        WHERE pv2p.pokemon_species_id = :id
        AND pv2p.is_default = TRUE
        """
        async with self.replace_row_factory(PokeapiModels.PokemonAbility) as conn:
            result = await conn.execute_fetchall(statement, {'id': mon.id})
        return result

    async def mon_has_ability(self, mon: PokeapiModels.PokemonSpecies, ability: PokeapiModels.Ability) -> bool:
        """Returns whether a Pokemon can have a given ability"""
        statement = """
        SELECT EXISTS (
            SELECT *
            FROM pokemon_v2_pokemonability
            INNER JOIN pokemon_v2_ability pv2a ON pokemon_v2_pokemonability.ability_id = pv2a.id
            INNER JOIN pokemon_v2_pokemon ON pokemon_v2_pokemonability.pokemon_id = pokemon_v2_pokemon.id
            WHERE ability_id = :ability_id
            AND pokemon_species_id = :id
            AND is_default = TRUE
        )
        """
        async with self.replace_row_factory(None) as conn:
            async with conn.execute(statement, {'id': mon.id, 'ability_id': ability.id}) as cur:
                result, = await cur.fetchone()
        return bool(result)

    async def mon_has_type(self, mon: PokeapiModels.PokemonSpecies, type_: PokeapiModels.Type) -> bool:
        """Returns whether the Pokemon has the given type. Only accounts for base forms."""
        statement = """
        SELECT EXISTS (
            SELECT *
            FROM pokemon_v2_pokemontype
            INNER JOIN pokemon_v2_pokemon pv2p ON pv2p.id = pokemon_v2_pokemontype.pokemon_id
            WHERE pokemon_species_id = :id
            AND type_id = :type_id
            AND is_default = TRUE
        )
        """
        async with self.replace_row_factory(None) as conn:
            async with conn.execute(statement, {'id': mon.id, 'type_id': type_.id}) as cur:
                result, = await cur.fetchone()
        return bool(result)

    async def has_mega_evolution(self, mon: PokeapiModels.PokemonSpecies) -> bool:
        """Returns whether the Pokemon can Mega Evolve"""
        statement = """
        SELECT EXISTS (
            SELECT *
            FROM pokemon_v2_pokemonform
            INNER JOIN pokemon_v2_pokemon pv2p ON pokemon_v2_pokemonform.pokemon_id = pv2p.id
            WHERE pokemon_species_id = :id
            AND is_mega = TRUE
        )
        """
        async with self.replace_row_factory(None) as conn:
            async with conn.execute(statement, {'id': mon.id}) as cur:
                result, = await cur.fetchone()
        return bool(result)
    
    async def get_evo_line(self, mon: PokeapiModels.PokemonSpecies) -> list[PokeapiModels.PokemonSpecies]:
        """Returns the set of all Pokemon in the same evolution family as the given species."""
        statement = """
        SELECT *
        FROM pokemon_v2_pokemonspecies
        WHERE evolution_chain_id = :evo_chain
        """
        async with self.replace_row_factory(PokeapiModels.PokemonSpecies) as conn:
            result = await conn.execute_fetchall(statement, {'evo_chain': mon.evolution_chain.id})
        return result

    async def has_evos(self, mon: PokeapiModels.PokemonSpecies) -> bool:
        statement = """
        SELECT COUNT(*) > 1
        FROM pokemon_v2_pokemonspecies
        WHERE evolution_chain_id = :evo_chain
        """
        async with self.replace_row_factory(None) as conn:
            async with conn.execute(statement, {'evo_chain': mon.evolution_chain.id}) as cur:
                result, = await cur.fetchone()
        return result

    async def is_in_evo_line(
            self,
            needle: PokeapiModels.PokemonSpecies,
            haystack: PokeapiModels.PokemonSpecies
    ) -> bool:
        statement = """
        SELECT EXISTS(
            SELECT *
            FROM pokemon_v2_pokemonspecies
            WHERE evolution_chain_id = :evo_chain
            AND id = :needle
        )
        """
        async with self.replace_row_factory(None) as conn:
            async with conn.execute(statement, {'evo_chain': haystack.evolution_chain.id, 'needle': needle.id}) as cur:
                result, = await cur.fetchone()
        return result

    async def has_branching_evos(self, mon: PokeapiModels.PokemonSpecies) -> bool:
        statement = """
        SELECT EXISTS (
            SELECT *
            FROM pokemon_v2_pokemonspecies
            WHERE evolution_chain_id = :evo_chain
            GROUP BY evolves_from_species_id
            HAVING COUNT(*) > 1
        )
        """
        async with self.replace_row_factory(None) as conn:
            async with conn.execute(statement, {'evo_chain': mon.evolution_chain.id}) as cur:
                result, = await cur.fetchone()
        return result

    async def mon_is_in_dex(self, mon: PokeapiModels.PokemonSpecies, dex: PokeapiModels.Pokedex) -> bool:
        """Returns whether a Pokemon is in the given pokedex."""
        statement = """
        SELECT EXISTS (
            SELECT *
            FROM pokemon_v2_pokemondexnumber
            WHERE pokemon_species_id = :mon_id
            AND pokedex_id = :dex_id
        )
        """
        async with self.replace_row_factory(None) as conn:
            async with conn.execute(statement, {'mon_id': mon.id, 'dex_id': dex.id}) as cur:
                result, = await cur.fetchone()
        return bool(result)

    async def get_formes(self, mon: PokeapiModels.PokemonSpecies) -> list[PokeapiModels.PokemonForm]:
        statement = """
        SELECT *
        FROM pokemon_v2_pokemonform
        INNER JOIN pokemon_v2_pokemon pv2p ON pokemon_v2_pokemonform.pokemon_id = pv2p.id
        WHERE pokemon_species_id = :id
        """
        async with self.replace_row_factory(PokeapiModels.PokemonForm) as conn:
            result = await conn.execute_fetchall(statement, {'id': mon.id})
        return result

    async def get_default_forme(self, mon: PokeapiModels.PokemonSpecies) -> PokeapiModels.PokemonForm:
        statement = """
        SELECT *
        FROM pokemon_v2_pokemonform
        INNER JOIN pokemon_v2_pokemon pv2p ON pv2p.id = pokemon_v2_pokemonform.pokemon_id
        WHERE pokemon_species_id = :id
        AND pv2p.is_default = TRUE
        """
        async with self.replace_row_factory(PokeapiModels.PokemonForm) as conn:
            async with conn.execute(statement, {'id': mon.id}) as cur:
                result = await cur.fetchone()
        return result

    async def get_sprite_path(self, mon: PokeapiModels.Pokemon, name: str) -> Optional[str]:
        statement = """
        SELECT JSON_EXTRACT(sprites, :path)
        FROM pokemon_v2_pokemonsprites
        WHERE pokemon_id = :id
        """
        async with self.replace_row_factory(None) as conn:
            async with conn.execute(statement, {'id': mon.id, 'path': name}) as cur:
                path, = await cur.fetchone()
        return path

    async def get_sprite_local_path(self, mon: PokeapiModels.Pokemon, name: str) -> Optional[str]:
        pokeapi_path = os.path.dirname(self._db_path)
        path = await self.get_sprite_path(mon, name)
        if path:
            path = re.sub(r'^/media/', f'{pokeapi_path}/data/v2/sprites/', path)
        return path

    async def get_sprite_url(self, mon: PokeapiModels.Pokemon, name: str) -> Optional[str]:
        path = await self.get_sprite_path(mon, name)
        if path:
            path = re.sub(r'^/media/', 'https://raw.githubusercontent.com/PokeAPI/sprites/master/', path)
        return path

    async def get_species_sprite_url(self, mon: PokeapiModels.PokemonSpecies) -> Optional[str]:
        forme = await self.get_default_forme(mon)
        poke = forme.pokemon
        attempts = [
            '$.front_default',
            '$.versions.generation-vii.ultra-sun-ultra-moon.front_default',
            '$.versions.generation-viii.icons.front_default',
        ]
        for name in attempts:
            if path := await self.get_sprite_url(poke, name):
                return path

    async def get_base_stats(self, mon: PokeapiModels.PokemonSpecies) -> dict[str, int]:
        statement = """
        SELECT pv2sn.name, pv2ps.base_stat
        FROM pokemon_v2_pokemonstat pv2ps
        INNER JOIN pokemon_v2_pokemon pv2p ON pv2ps.pokemon_id = pv2p.id
        INNER JOIN pokemon_v2_statname pv2sn ON pv2ps.stat_id = pv2sn.stat_id
        WHERE pv2p.pokemon_species_id = :id
        AND pv2p.is_default = TRUE
        AND pv2sn.language_id = 9
        """
        async with self.replace_row_factory(None) as conn:
            result = await conn.execute_fetchall(statement, {'id': mon.id})
        return dict(result)

    async def get_egg_groups(self, mon: PokeapiModels.PokemonSpecies) -> list[PokeapiModels.EggGroup]:
        statement = """
        SELECT *
        FROM pokemon_v2_egggroup
        INNER JOIN pokemon_v2_pokemonegggroup pv2p ON pokemon_v2_egggroup.id = pv2p.egg_group_id
        WHERE pokemon_species_id = :id
        """
        async with self.replace_row_factory(PokeapiModels.EggGroup) as conn:
            result = await conn.execute_fetchall(statement, {'id': mon.id})
        return result

    async def mon_is_in_egg_group(self, mon: PokeapiModels.PokemonSpecies, egg_group: PokeapiModels.EggGroup) -> bool:
        statement = """
        SELECT EXISTS (
            SELECT *
            FROM pokemon_v2_pokemonegggroup
            WHERE pokemon_species_id = :id
            AND egg_group_id = :egg_id
        )
        """
        async with self.replace_row_factory(None) as conn:
            async with conn.execute(statement, {'id': mon.id, 'egg_id': egg_group.id}) as cur:
                result, = await cur.fetchone()
        return bool(result)

    async def mon_can_mate_with(self, mon: PokeapiModels.PokemonSpecies, mate: PokeapiModels.PokemonSpecies) -> bool:
        # Babies can't breed
        if mon.is_baby or mate.is_baby:
            return False

        # Undiscovered can't breed together, and Ditto can't breed Ditto
        # Other than that, same species can breed together.
        if mon.id == mate.id:
            return mon.id != 132 \
                    and mon.gender_rate not in {0, 8, -1} \
                    and not await self.mon_is_in_undiscovered_egg_group(mon)

        # Anything that's not undiscovered can breed with Ditto
        if mon.id == 132 or mate.id == 132:
            if mon.id == 132:
                mon = mate
            return not await self.mon_is_in_undiscovered_egg_group(mon)

        if mon.gender_rate == mate.gender_rate == 0 \
                or mon.gender_rate == mate.gender_rate == 8 \
                or -1 in {mon.gender_rate, mate.gender_rate}:
            return False

        statement = """
        SELECT EXISTS (
            SELECT *
            FROM pokemon_v2_pokemonegggroup
            WHERE pokemon_species_id IN (:id, :id2)
            AND egg_group_id != 15
            GROUP BY egg_group_id
            HAVING COUNT(*) = 2
        )
        """
        async with self.replace_row_factory(None) as conn:
            async with conn.execute(statement, {'id': mon.id, 'id2':  mate.id}) as cur:
                result, = await cur.fetchone()
        return bool(result)

    async def get_mon_flavor_text(
            self,
            mon: PokeapiModels.PokemonSpecies,
            version: Optional[PokeapiModels.Version] = None
    ) -> str:
        statement = """
        SELECT flavor_text
        FROM pokemon_v2_pokemonspeciesflavortext
        WHERE pokemon_species_id = :id
        AND language_id = :lang
        """
        if version is None:
            statement += ' ORDER BY random()'
        else:
            statement += ' AND version_id = :version'
        async with self.replace_row_factory(None) as conn:
            async with conn.execute(
                    statement, {
                        'id': mon.id,
                        'lang': mon.language.id,
                        'version': version and version.id
                    }
            ) as cur:
                result, = await cur.fetchone()
        return result

    async def get_mon_evolution_methods(
            self,
            mon: PokeapiModels.PokemonSpecies
    ) -> list[PokeapiModels.PokemonEvolution]:
        statement = """
        SELECT *
        FROM pokemon_v2_pokemonevolution
        INNER JOIN pokemon_v2_pokemonspecies pv2p ON pokemon_v2_pokemonevolution.evolved_species_id = pv2p.id
        WHERE evolves_from_species_id = :id
        """
        async with self.replace_row_factory(PokeapiModels.PokemonEvolution) as conn:
            result = await conn.execute_fetchall(statement, {'id': mon.id})
        return result

    async def mon_is_in_undiscovered_egg_group(self, mon: PokeapiModels.PokemonSpecies) -> bool:
        statement = """
        SELECT EXISTS (
            SELECT *
            FROM pokemon_v2_pokemonegggroup
            WHERE egg_group_id = 15
            AND pokemon_species_id = :id
        )
        """
        async with self.replace_row_factory(None) as conn:
            async with conn.execute(statement, {'id': mon.id}) as cur:
                result, = await cur.fetchone()
        return bool(result)

    async def get_versions_in_group(self, grp: PokeapiModels.VersionGroup) -> list[PokeapiModels.Version]:
        statement = """
        SELECT *
        FROM pokemon_v2_version
        WHERE version_group_id = :vgid
        """
        async with self.replace_row_factory(PokeapiModels.Version) as conn:
            result = await conn.execute_fetchall(statement, {'vgid': grp.id})
        return result

    async def get_move_attrs(self, move: PokeapiModels.Move) -> list[PokeapiModels.MoveAttribute]:
        statement = """
        SELECT *
        FROM pokemon_v2_moveattribute
        INNER JOIN pokemon_v2_moveattributemap pv2m on pokemon_v2_moveattribute.id = pv2m.move_attribute_id
        WHERE move_id = :move_id
        """
        async with self.replace_row_factory(PokeapiModels.MoveAttribute) as conn:
            result = await conn.execute_fetchall(statement, {'move_id': move.id})
        return result

    async def get_move_description(
            self,
            move: PokeapiModels.Move,
            version: Optional[PokeapiModels.Version] = None
    ) -> Optional[str]:
        statement = """
        SELECT flavor_text
        FROM pokemon_v2_moveflavortext
        WHERE language_id = :language_id
        AND move_id = :move_id
        """
        kwargs = {'language_id': move.language.id, 'move_id': move.id}
        if version:
            statement += ' AND version_group_id = :version_group_id'
            kwargs['version_group_id'] = version.version_group.id
        else:
            statement += ' ORDER BY random()'
        try:
            async with self.replace_row_factory(None) as conn:
                async with conn.execute(statement, kwargs) as cur:
                    result, = await cur.fetchone()
        except TypeError:
            result = None
        return result

    async def get_machines_teaching_move(self, move: PokeapiModels.Move) -> list[PokeapiModels.Machine]:
        statement = """
        SELECT *
        FROM pokemon_v2_machine
        WHERE move_id = :move_id
        """
        async with self.replace_row_factory(PokeapiModels.Machine) as conn:
            result = await conn.execute_fetchall(statement, {'move_id': move.id})
        return result

    async def get_version_group_name(self, version_group: PokeapiModels.VersionGroup) -> str:
        *versions, last = await self.get_versions_in_group(version_group)
        if versions:
            if len(versions) == 1:
                return f'{versions[0].name} and {last.name}'
            return ', '.join(v.name for v in versions) + ', and ' + last.name
        return last.name

    async def get_item_icon(self, item: PokeapiModels.Item, path='$.default') -> Optional[str]:
        statement = """
        SELECT JSON_EXTRACT(sprites, :path)
        FROM pokemon_v2_itemsprites
        WHERE item_id = :id
        """
        async with self.replace_row_factory(None) as conn:
            async with conn.execute(statement, {'path': path, 'id': item.id}) as cur:
                result, = await cur.fetchone()
        return result

    async def get_item_icon_url(self, item: PokeapiModels.Item, path='$.default') -> Optional[str]:
        result = await self.get_item_icon(item, path)
        if result:
            result = re.sub(r'^/media/', 'https://raw.githubusercontent.com/PokeAPI/sprites/master/', result)
        return result
