import aiosqlite
import re
from typing import Coroutine, Optional, List, Set, Callable, Tuple, Any, Union, Mapping, AsyncGenerator
import collections
import json
from sqlite3 import Cursor
from .models import *
from contextlib import asynccontextmanager as acm
import random
import difflib
from ... import __dirname__
import asyncio
from operator import attrgetter


__all__ = 'PokeApi',
__global_cache__ = {}


async def flatten(iterable: AsyncGenerator):
    return [x async for x in iterable]


class PokeApi(aiosqlite.Connection, PokeapiModels):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._lock = asyncio.Lock()

    @staticmethod
    def _clean_name(name):
        name = name.replace('♀', '_F').replace('♂', '_m').replace('é', 'e')
        name = re.sub(r'\W+', '_', name).title()
        return name

    # Generic getters

    @acm
    async def replace_row_factory(self, factory: Optional[Callable[[Cursor, Tuple[Any]], Any]]) -> 'PokeApi':
        if self._connection is None:
            await self._connect()
        async with self._lock:
            old_factory = self.row_factory
            self.row_factory = factory
            yield self
            self.row_factory = old_factory

    def resolve_model(self, model: Union[str, Callable[[Cursor, Tuple[Any]], Any]]) -> Callable[[Cursor, Tuple[Any]], Any]:
        if isinstance(model, str):
            model = getattr(self, model)
        assert issubclass(model, PokeapiResource)
        return model

    async def get_model(self, model: Callable[[Cursor, Tuple[Any]], Any], id_: int) -> Optional[Any]:
        model = self.resolve_model(model)
        if id_ is None:
            return
        if (model, id_) in __global_cache__:
            return __global_cache__[(model, id_)]
        statement = """
        SELECT *
        FROM pokemon_v2_{}
        WHERE id = :id
        """.format(model.__name__.lower())
        async with self.replace_row_factory(model) as conn:
            async with conn.execute(statement, {'id': id_}) as cur:
                result = await cur.fetchone()
        __global_cache__[(model, id_)] = result
        return result

    @acm
    async def all_models_cursor(self, model: Callable[[Cursor, Tuple[Any]], Any]) -> aiosqlite.Cursor:
        model = self.resolve_model(model)
        statement = """
        SELECT *
        FROM pokemon_v2_{}
        """.format(model.__name__.lower())
        async with self.replace_row_factory(model) as conn:
            async with conn.execute(statement) as cur:
                yield cur

    async def get_all_models(self, model: Callable[[Cursor, Tuple[Any]], Any]) -> List[Any]:
        model = self.resolve_model(model)
        if model in __global_cache__:
            return __global_cache__[model]
        async with self.all_models_cursor(model) as cur:
            result = await cur.fetchall()
        __global_cache__[model] = result
        return result

    async def find(self, predicate: Callable[[Any], bool], model: Callable[[Cursor, Tuple[Any]], Any]) -> Optional[PokeapiResource]:
        async with self.all_models_cursor(model) as seq:
            async for element in seq:  # type: PokeapiResource
                if predicate(element):
                    return element
            return None

    async def filter(self, model: Callable[[Cursor, Tuple[Any]], Any], **attrs) -> AsyncGenerator[Any, None]:
        _all = all
        attrget = attrgetter
        async with self.all_models_cursor(model) as iterable:

            if len(attrs) == 1:
                k, v = attrs.popitem()
                pred = attrget(k.replace('__', '.'))
                async for elem in iterable:
                    if pred(elem) == v:
                        yield elem

            converted = [
                (attrget(attr.replace('__', '.')), value)
                for attr, value in attrs.items()
            ]

            async for elem in iterable:
                if _all(pred(elem) == value for pred, value in converted):
                    yield elem

    async def get(self, model: Callable[[Cursor, Tuple[Any]], Any], **attrs) -> Optional[Any]:
        async for item in self.filter(model, **attrs):
            return item

    async def get_model_named(self, model: Callable[[Cursor, Tuple[Any]], Any], name: str) -> Optional[Any]:
        differ = difflib.SequenceMatcher()
        differ.set_seq2(name.lower())

        def predicate(x: NamedPokeapiResource):
            differ.set_seq1(x.name.lower())
            return differ.real_quick_ratio() > 0.9 and differ.quick_ratio() > 0.9 and differ.ratio() > 0.9

        obj = await self.find(predicate, model)  # type: PokeapiResource
        if obj:
            __global_cache__[(model, obj.id)] = obj
        return obj

    async def get_names_from(self, table: Callable[[Cursor, Tuple[Any]], Any], *, clean=False) -> List[str]:
        """Generic method to get a list of all names from a PokeApi table."""
        async with self.all_models_cursor(table) as cur:
            names = [await self.get_name(obj, clean=clean) async for obj in cur]
        return names

    async def get_name(self, item: NamedPokeapiResource, *, clean=False) -> str:
        return self._clean_name(item.name) if clean else item.name

    async def get_name_by_id(self, model: Callable[[Cursor, Tuple[Any]], Any], id_: int, *, clean=False):
        """Generic method to get the name of a PokeApi object given only its ID."""
        obj = await self.get_model(model, id_)
        return obj and await self.get_name(obj, clean=clean)

    async def get_random(self, model: Callable[[Cursor, Tuple[Any]], Any]) -> Optional[Any]:
        """Generic method to get a random PokeApi object."""
        model = self.resolve_model(model)
        if model in __global_cache__:
            return random.choice(__global_cache__[model])
        statement = """
        SELECT *
        FROM pokemon_v2_{}
        ORDER BY random()
        """.format(model.__name__.lower())
        async with self.replace_row_factory(model) as conn:
            async with conn.execute(statement) as cur:
                obj = await cur.fetchone()
        __global_cache__[(model, obj.id)] = obj
        return obj
    
    async def get_random_name(self, table: Callable[[Cursor, Tuple[Any]], Any], *, clean=False) -> Optional[str]:
        """Generic method to get a random PokeApi object name."""
        obj = await self.get_random(table)
        return obj and await self.get_name(obj, clean=clean)

    # Specific getters, defined for type-hints

    def get_species(self, id_) -> Coroutine[None, None, Optional[PokeapiModels.PokemonSpecies]]:
        """Get a Pokemon species by ID"""
        return self.get_model(PokeapiModels.PokemonSpecies, id_)

    def random_species(self) -> Coroutine[None, None, Optional[PokeapiModels.PokemonSpecies]]:
        """Get a random Pokemon species"""
        return self.get_random(PokeapiModels.PokemonSpecies)

    def get_mon_name(self, mon: PokeapiModels.PokemonSpecies, *, clean=False) -> Coroutine[None, None, str]:
        """Get the name of a Pokemon species"""
        return self.get_name(mon, clean=clean)

    def random_species_name(self, *, clean=False) -> Coroutine[None, None, str]:
        """Get the name of a random Pokemon species"""
        return self.get_random_name(PokeapiModels.PokemonSpecies, clean=clean)

    def get_species_by_name(self, name: str) -> Coroutine[None, None, Optional[PokeapiModels.PokemonSpecies]]:
        """Get a Pokemon species given its name"""
        return self.get_model_named(PokeapiModels.PokemonSpecies, name)

    def get_forme_name(self, mon: PokeapiModels.PokemonForm, *, clean=False) -> Coroutine[None, None, str]:
        """Get a Pokemon forme's name"""
        return self.get_name(mon, clean=clean)

    def random_move(self) -> Coroutine[None, None, Optional[PokeapiModels.Move]]:
        """Get a random move"""
        return self.get_random(PokeapiModels.Move)

    def get_move_name(self, move: PokeapiModels.Move, *, clean=False) -> Coroutine[None, None, str]:
        """Get a move's name"""
        return self.get_name(move, clean=clean)

    def random_move_name(self, *, clean=False) -> Coroutine[None, None, str]:
        """Get a random move's name"""
        return self.get_random_name(PokeapiModels.Move, clean=clean)

    def get_move_by_name(self, name: str) -> Coroutine[None, None, Optional[PokeapiModels.Move]]:
        """Get a move given its name"""
        return self.get_model_named(PokeapiModels.Move, name)

    def get_mon_color(self, mon: PokeapiModels.PokemonSpecies) -> PokeapiModels.PokemonColor:
        """Get the object representing the Pokemon species' color"""
        return mon.pokemon_color

    def get_pokemon_color_by_name(self, name: str) -> Coroutine[None, None, Optional[PokeapiModels.PokemonColor]]:
        """Get a Pokemon color given its name"""
        return self.get_model_named(PokeapiModels.PokemonColor, name)

    def get_pokemon_color_name(self, color: PokeapiModels.PokemonColor, *, clean=False) -> Coroutine[None, None, str]:
        """Get the name of a Pokemon color"""
        return self.get_name(color, clean=clean)

    def get_name_of_mon_color(self, mon: PokeapiModels.PokemonSpecies, *, clean=False) -> Coroutine[None, None, str]:
        """Get the name of a Pokemon species' color"""
        return self.get_name(mon.pokemon_color, clean=clean)

    def get_ability_by_name(self, name: str) -> Coroutine[None, None, Optional[PokeapiModels.Ability]]:
        """Get an ability given its name"""
        return self.get_model_named(PokeapiModels.Ability, name)

    def get_ability_name(self, ability: PokeapiModels.Ability, *, clean=False) -> Coroutine[None, None, str]:
        """Get the name of an ability"""
        return self.get_name(ability, clean=clean)

    def get_type_by_name(self, name: str) -> Coroutine[None, None, Optional[PokeapiModels.Type]]:
        """Get a Pokemon type given its name"""
        return self.get_model_named(PokeapiModels.Type, name)

    def get_type_name(self, type_: PokeapiModels.Type, *, clean=False) -> Coroutine[None, None, str]:
        """Get the name of a type"""
        return self.get_name(type_, clean=clean)

    def get_pokedex_by_name(self, name: str) -> Coroutine[None, None, Optional[PokeapiModels.Pokedex]]:
        """Get a Pokedex given its name"""
        return self.get_model_named(PokeapiModels.Pokedex, name)

    def get_pokedex_name(self, dex: PokeapiModels.Pokedex, *, clean=False) -> Coroutine[None, None, str]:
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

    async def get_mon_types(self, mon: PokeapiModels.PokemonSpecies) -> List[PokeapiModels.Type]:
        """Returns a list of types for that Pokemon"""
        statement = """
        SELECT *
        FROM pokemon_v2_type
        WHERE id IN (
            SELECT type_id
            FROM pokemon_v2_pokemontype
            WHERE pokemon_id IN (
                SELECT id
                FROM pokemon_v2_pokemon
                WHERE pokemon_species_id = :id
                AND is_default = TRUE
            )
        )
        """
        async with self.replace_row_factory(PokeapiModels.Type) as conn:
            result = await conn.execute_fetchall(statement, {'id': mon.id})
        return result

    async def get_mon_matchup_against_type(self, mon: PokeapiModels.PokemonSpecies, type_: PokeapiModels.Type) -> float:
        """Calculates whether a type is effective or not against a mon"""
        result = 1
        statement = """
        SELECT damage_factor
        FROM pokemon_v2_typeefficacy
        WHERE damage_type_id = :damage_type
        AND target_type_id IN (
            SELECT type_id
            FROM pokemon_v2_pokemontype
            WHERE pokemon_id IN (
                SELECT id
                FROM pokemon_v2_pokemon
                WHERE pokemon_species_id = :mon_id
                AND is_default = TRUE
            )
        )
        """
        async with self.replace_row_factory(None) as conn:
            async with conn.execute(statement, {'damage_type': type_.id, 'mon_id': mon.id}) as cur:
                async for damage_factor, in cur:
                    result *= damage_factor / 100
        return result

    async def get_mon_matchup_against_move(self, mon: PokeapiModels.PokemonSpecies, move: PokeapiModels.Move) -> float:
        """Calculates whether a move is effective or not against a mon"""
        return await self.get_mon_matchup_against_type(mon, move.type)

    async def get_mon_matchup_against_mon(self, mon: PokeapiModels.PokemonSpecies, mon2: PokeapiModels.PokemonSpecies) -> List[float]:
        """For each type mon2 has, determines its effectiveness against mon"""

        statement = """
        SELECT damage_factor, damage_type_id
        FROM pokemon_v2_typeefficacy
        WHERE damage_type_id IN (
            SELECT type_id
            FROM pokemon_v2_pokemontype
            WHERE pokemon_id = (
                SELECT id
                FROM pokemon_v2_pokemon
                WHERE pokemon_species_id = :mon2_id
                AND is_default = TRUE
            )
        )
        AND target_type_id IN (
            SELECT type_id
            FROM pokemon_v2_pokemontype
            WHERE pokemon_id = (
                SELECT id
                FROM pokemon_v2_pokemon
                WHERE pokemon_species_id = :mon_id
                AND is_default = TRUE
            )
        )
        """
        result = collections.defaultdict(lambda: 1)
        async with self.replace_row_factory(None) as conn:
            async with conn.execute(statement, {'mon2_id': mon2.id, 'mon_id': mon.id}) as cur:
                async for damage_factor, damage_type_id in cur:
                    result[damage_type_id] *= damage_factor / 100
        return list(result.values())

    async def get_preevo(self, mon: PokeapiModels.PokemonSpecies) -> PokeapiModels.PokemonSpecies:
        """Get the species the given Pokemon evoles from"""
        return mon.evolves_from_species

    async def get_evos(self, mon: PokeapiModels.PokemonSpecies) -> List[PokeapiModels.PokemonSpecies]:
        """Get all species the given Pokemon evolves into"""
        statement = """
        SELECT *
        FROM pokemon_v2_pokemonspecies
        WHERE evolves_from_species_id IN (
            SELECT id
            FROM pokemon_v2_pokemonspecies
            WHERE evolves_from_species_id = :id
        )
        """
        async with self.replace_row_factory(PokeapiModels.PokemonSpecies) as conn:
            result = await conn.execute_fetchall(statement, {'id': mon.id})
        return result

    async def get_mon_learnset(self, mon: PokeapiModels.PokemonSpecies) -> Set[PokeapiModels.Move]:
        """Returns a list of all the moves the Pokemon can learn"""
        statement = """
        SELECT *
        FROM pokemon_v2_move
        WHERE id IN (
            SELECT move_id
            FROM pokemon_v2_pokemonmove
            WHERE pokemon_id = (
                SELECT id
                FROM pokemon_v2_pokemon
                WHERE pokemon_species_id = :id
                AND is_default = TRUE
            )
        )
        """
        async with self.replace_row_factory(PokeapiModels.Move) as conn:
            result = await conn.execute_fetchall(statement, {'id': mon.id})
        return set(result)
    
    async def mon_can_learn_move(self, mon: PokeapiModels.PokemonSpecies, move: PokeapiModels.Move) -> bool:
        """Returns whether a move is in the Pokemon's learnset"""
        statement = """
        SELECT EXISTS (
            SELECT *
            FROM pokemon_v2_pokemonmove
            WHERE move_id = :move_id
            AND pokemon_id = (
                SELECT id
                FROM pokemon_v2_pokemon
                WHERE pokemon_species_id = :mon_id
                AND is_default = TRUE
            )
        )
        """
        async with self.replace_row_factory(None) as conn:
            async with conn.execute(statement, {'mon_id': mon.id, 'move_id': move.id}) as cur:
                result, = await cur.fetchone()
        return bool(result)

    async def get_mon_abilities(self, mon: PokeapiModels.PokemonSpecies) -> List[PokeapiModels.Ability]:
        """Returns a list of abilities for that Pokemon"""
        statement = """
        SELECT *
        FROM pokemon_v2_ability
        WHERE id IN (
            SELECT ability_id
            FROM pokemon_v2_pokemonability
            WHERE pokemon_id = (
                SELECT id
                FROM pokemon_v2_pokemon
                WHERE pokemon_species_id = :id
                AND is_default = TRUE
            )
        )
        """
        async with self.replace_row_factory(PokeapiModels.Ability) as conn:
            result = await conn.execute_fetchall(statement, {'id': mon.id})
        return result

    async def mon_has_ability(self, mon: PokeapiModels.PokemonSpecies, ability: PokeapiModels.Ability) -> bool:
        """Returns whether a Pokemon can have a given ability"""
        statement = """
        SELECT EXISTS (
            SELECT *
            FROM pokemon_v2_ability
            WHERE id IN (
                SELECT ability_id
                FROM pokemon_v2_pokemonability
                WHERE pokemon_id = (
                    SELECT id
                    FROM pokemon_v2_pokemon
                    WHERE pokemon_species_id = :id
                    AND is_default = TRUE
                )
            )
        )
        """
        async with self.replace_row_factory(None) as conn:
            async with conn.execute(statement, {'id': mon.id}) as cur:
                result = await cur.fetchone()
        return bool(result)

    async def mon_has_type(self, mon: PokeapiModels.PokemonSpecies, type_: PokeapiModels.Type) -> bool:
        """Returns whether the Pokemon has the given type. Only accounts for base forms."""
        statement = """
        SELECT EXISTS (
            SELECT *
            FROM pokemon_v2_type
            WHERE id IN (
                SELECT type_id
                FROM pokemon_v2_pokemontype
                WHERE pokemon_id = (
                    SELECT id
                    FROM pokemon_v2_pokemon
                    WHERE pokemon_species_id = :id
                    AND is_default = TRUE
                )
            )
        )
        """
        async with self.replace_row_factory(None) as conn:
            async with conn.execute(statement, {'id': mon.id}) as cur:
                result = await cur.fetchone()
        return bool(result)

    async def has_mega_evolution(self, mon: PokeapiModels.PokemonSpecies) -> bool:
        """Returns whether the Pokemon can Mega Evolve"""
        statement = """
        SELECT EXISTS (
            SELECT *
            FROM pokemon_v2_pokemonform
            WHERE pokemon_id IN (
                SELECT id
                FROM pokemon_v2_pokemon
                WHERE pokemon_species_id = :id
            )
            AND is_mega = TRUE
        )
        """
        async with self.replace_row_factory(None) as conn:
            async with conn.execute(statement, {'id': mon.id}) as cur:
                result = await cur.fetchone()
        return bool(result)
    
    async def get_evo_line(self, mon: PokeapiModels.PokemonSpecies) -> List[PokeapiModels.PokemonSpecies]:
        """Returns the set of all Pokemon in the same evolution family as the given species."""
        statement = """
        SELECT *
        FROM pokemon_v2_pokemonspecies
        WHERE evolution_chain_id = :evo_chain
        """
        async with self.replace_row_factory(PokeapiModels.PokemonSpecies) as conn:
            result = await conn.execute_fetchall(statement, {'evo_chain': mon.evolution_chain.id})
        result = await flatten(self.filter(PokeapiModels.PokemonSpecies, evolution_chain=mon.evolution_chain))
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
                result = await cur.fetchone()
        return bool(result)

    async def get_formes(self, mon: PokeapiModels.PokemonSpecies) -> List[PokeapiModels.PokemonForm]:
        statement = """
        SELECT *
        FROM pokemon_v2_pokemonform
        WHERE pokemon_id IN (
            SELECT id
            FROM pokemon_v2_pokemon
            WHERE pokemon_species_id = :id
        )
        """
        async with self.replace_row_factory(PokeapiModels.PokemonForm) as conn:
            result = await conn.execute_fetchall(statement, {'id': mon.id})
        return result

    async def get_default_forme(self, mon: PokeapiModels.PokemonSpecies) -> PokeapiModels.PokemonForm:
        statement = """
        SELECT *
        FROM pokemon_v2_pokemonform
        WHERE pokemon_id = (
            SELECT id
            FROM pokemon_v2_pokemon
            WHERE pokemon_species_id = :id
            AND is_default = TRUE
        )
        """
        async with self.replace_row_factory(PokeapiModels.PokemonForm) as conn:
            async with conn.execute(statement, {'id': mon.id}) as cur:
                result = await cur.fetchone()
        return result

    async def get_sprite_path(self, mon: PokeapiModels.Pokemon, name: str) -> Optional[str]:
        statement = """
        SELECT sprites
        FROM pokemon_v2_pokemonsprites
        WHERE pokemon_id = :id
        """
        async with self.replace_row_factory(None) as conn:
            async with conn.execute(statement, {'id': mon.id}) as cur:
                path = json.loads(*(await cur.fetchone()))
        for entry in name.split('/'):
            try:
                path = path[entry]
            except (KeyError, TypeError):
                return None
        if isinstance(path, (dict, list)):
            path = None
        return path

    async def get_sprite_local_path(self, mon: PokeapiModels.Pokemon, name: str) -> Optional[str]:
        path = await self.get_sprite_path(mon, name)
        if path:
            path = re.sub(r'^/media/', f'{__dirname__}/../pokeapi/data/v2/sprites/', path)
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
            'front_default',
            'versions/generation-vii/ultra-sun-ultra-moon/front_default',
            'versions/generation-viii/icons/front_default',
        ]
        for name in attempts:
            if path := await self.get_sprite_url(poke, name):
                return path

    async def get_base_stats(self, mon: PokeapiModels.PokemonSpecies) -> Mapping[str, int]:
        statement = """
        SELECT *
        FROM pokemon_v2_pokemonstat
        WHERE pokemon_id = (
            SELECT id
            FROM pokemon_v2_pokemon
            WHERE pokemon_species_id = :id
            AND is_default = TRUE
        )
        """
        async with self.replace_row_factory(PokeapiModels.PokemonStat) as conn:
            async with conn.execute(statement, {'id': mon.id}) as cur:
                return {pstat.stat.name: pstat.base_stat async for pstat in cur}

    async def get_egg_groups(self, mon: PokeapiModels.PokemonSpecies) -> List[PokeapiModels.EggGroup]:
        statement = """
        SELECT *
        FROM pokemon_v2_egggroup
        WHERE id IN (
            SELECT egg_group_id
            FROM pokemon_v2_pokemonegggroup
            WHERE pokemon_species_id = :id
        )
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
        if mon.is_baby or mate.is_baby:
            return False
        if mon.id == mate.id:
            if mon.id == 132:
                return False
            statement = """
            SELECT EXISTS (
                SELECT *
                FROM pokemon_v2_pokemonegggroup
                WHERE pokemon_species_id = :id
                AND egg_group_id = 15
            )
            """
            async with self.replace_row_factory(None) as conn:
                async with conn.execute(statement, {'id': mon.id}) as cur:
                    result, = await cur.fetchone()
            return not result
        if mon.id == 132 or mate.id == 132:
            if mon.id == 132:
                mon = mate
            statement = """
            SELECT EXISTS (
                SELECT *
                FROM pokemon_v2_pokemonegggroup
                WHERE pokemon_species_id = :id
                AND egg_group_id = 15
            )
            """
            async with self.replace_row_factory(None) as conn:
                async with conn.execute(statement, {'id': mon.id}) as cur:
                    result, = await cur.fetchone()
            return not result

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

    async def get_mon_flavor_text(self, mon: PokeapiModels.PokemonSpecies, version: Optional[PokeapiModels.Version] = None) -> PokeapiModels.PokemonSpeciesFlavorText:
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
            async with conn.execute(statement, {'id': mon.id, 'lang': mon.language.id, 'version': version.id}) as cur:
                result, = await cur.fetchone()
        return result

    async def get_mon_evolution_methods(self, mon: PokeapiModels.PokemonSpecies) -> List[PokeapiModels.PokemonEvolution]:
        statement = """
        SELECT *
        FROM pokemon_v2_pokemonevolution
        WHERE evolved_species_id IN (
            SELECT id
            FROM pokemon_v2_pokemonspecies
            WHERE evolves_from_species_id = :id
        )
        """
        async with self.replace_row_factory(PokeapiModels.PokemonEvolution) as conn:
            result = await conn.execute_fetchall(statement, {'id': mon.id})
        return result
