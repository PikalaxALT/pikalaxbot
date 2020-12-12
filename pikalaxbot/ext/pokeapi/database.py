import aiosqlite
import re
from typing import Coroutine, Optional, List, Set, Callable, Tuple, Any, Union, Mapping, AsyncGenerator
import collections
import json
from sqlite3 import Cursor
from .models import *
from contextlib import asynccontextmanager as acm
import difflib
from ... import __dirname__
import asyncio
from operator import attrgetter


__all__ = 'PokeApi',


async def flatten(iterable: AsyncGenerator):
    return [x async for x in iterable]


class PokeApi(aiosqlite.Connection, PokeapiModels):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._lock = asyncio.Lock()

    async def _connect(self) -> "PokeApi":
        differ = difflib.SequenceMatcher()

        def fuzzy_ratio(s):
            differ.set_seq1(s.lower())
            return min(differ.real_quick_ratio(), differ.quick_ratio(), differ.ratio())

        await super()._connect()
        await self.create_function('FUZZY_RATIO', 1, fuzzy_ratio, deterministic=True)
        await self.create_function('SET_FUZZY_SEQ', 1, lambda s: differ.set_seq2(s.lower()), deterministic=True)
        return self

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
        async with self.all_models_cursor(model) as cur:
            result = await cur.fetchall()
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

    async def get_model_named(self, model: Callable[[Cursor, Tuple[Any]], Any], name: str, *, cutoff=0.9) -> Optional[Any]:
        model = self.resolve_model(model)
        statement = """
        SELECT *
        FROM pokemon_v2_{0} pv2t
        INNER JOIN pokemon_v2_{0}name pv2n ON pv2t.id = pv2n.{1}_id
        WHERE FUZZY_RATIO(pv2n.name) > :cutoff
        AND pv2n.language_id = :language
        ORDER BY FUZZY_RATIO(pv2n.name) DESC
        """.format(model.__name__.lower(), re.sub(r'([a-z])([A-Z])', r'\1_\2', model.__name__).lower())
        async with self.replace_row_factory(model) as conn:
            await self.execute('SELECT SET_FUZZY_SEQ(:name)', {'name': name})
            async with conn.execute(statement, {'cutoff': cutoff, 'language': self._conn._default_language}) as cur:
                obj = await cur.fetchone()
        return obj

    async def get_names_from(self, table: Callable[[Cursor, Tuple[Any]], Any], *, clean=False) -> AsyncGenerator[str, None]:
        """Generic method to get a list of all names from a PokeApi table."""
        async with self.all_models_cursor(table) as cur:
            async for obj in cur:
                yield self.get_name(obj, clean=clean)

    def get_name(self, item: NamedPokeapiResource, *, clean=False) -> str:
        return self._clean_name(item.name) if clean else item.name

    async def get_name_by_id(self, model: Callable[[Cursor, Tuple[Any]], Any], id_: int, *, clean=False):
        """Generic method to get the name of a PokeApi object given only its ID."""
        obj = await self.get_model(model, id_)
        return obj and self.get_name(obj, clean=clean)

    async def get_random(self, model: Callable[[Cursor, Tuple[Any]], Any]) -> Optional[Any]:
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
    
    async def get_random_name(self, table: Callable[[Cursor, Tuple[Any]], Any], *, clean=False) -> Optional[str]:
        """Generic method to get a random PokeApi object name."""
        obj = await self.get_random(table)
        return obj and self.get_name(obj, clean=clean)

    # Specific getters, defined for type-hints

    def get_species(self, id_) -> Coroutine[None, None, Optional[PokeapiModels.PokemonSpecies]]:
        """Get a Pokemon species by ID"""
        return self.get_model(PokeapiModels.PokemonSpecies, id_)

    def random_species(self) -> Coroutine[None, None, Optional[PokeapiModels.PokemonSpecies]]:
        """Get a random Pokemon species"""
        return self.get_random(PokeapiModels.PokemonSpecies)

    def get_mon_name(self, mon: PokeapiModels.PokemonSpecies, *, clean=False) -> str:
        """Get the name of a Pokemon species"""
        return self.get_name(mon, clean=clean)

    def random_species_name(self, *, clean=False) -> Coroutine[None, None, str]:
        """Get the name of a random Pokemon species"""
        return self.get_random_name(PokeapiModels.PokemonSpecies, clean=clean)

    def get_species_by_name(self, name: str) -> Coroutine[None, None, Optional[PokeapiModels.PokemonSpecies]]:
        """Get a Pokemon species given its name"""
        return self.get_model_named(PokeapiModels.PokemonSpecies, name)

    def get_forme_name(self, mon: PokeapiModels.PokemonForm, *, clean=False) -> str:
        """Get a Pokemon forme's name"""
        return self.get_name(mon, clean=clean)

    def random_move(self) -> Coroutine[None, None, Optional[PokeapiModels.Move]]:
        """Get a random move"""
        return self.get_random(PokeapiModels.Move)

    def get_move_name(self, move: PokeapiModels.Move, *, clean=False) -> str:
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

    def get_pokemon_color_name(self, color: PokeapiModels.PokemonColor, *, clean=False) -> str:
        """Get the name of a Pokemon color"""
        return self.get_name(color, clean=clean)

    def get_name_of_mon_color(self, mon: PokeapiModels.PokemonSpecies, *, clean=False) -> str:
        """Get the name of a Pokemon species' color"""
        return self.get_name(mon.pokemon_color, clean=clean)

    def get_ability_by_name(self, name: str) -> Coroutine[None, None, Optional[PokeapiModels.Ability]]:
        """Get an ability given its name"""
        return self.get_model_named(PokeapiModels.Ability, name)

    def get_ability_name(self, ability: PokeapiModels.Ability, *, clean=False) -> str:
        """Get the name of an ability"""
        return self.get_name(ability, clean=clean)

    def get_type_by_name(self, name: str) -> Coroutine[None, None, Optional[PokeapiModels.Type]]:
        """Get a Pokemon type given its name"""
        return self.get_model_named(PokeapiModels.Type, name)

    def get_type_name(self, type_: PokeapiModels.Type, *, clean=False) -> str:
        """Get the name of a type"""
        return self.get_name(type_, clean=clean)

    def get_pokedex_by_name(self, name: str) -> Coroutine[None, None, Optional[PokeapiModels.Pokedex]]:
        """Get a Pokedex given its name"""
        return self.get_model_named(PokeapiModels.Pokedex, name)

    def get_pokedex_name(self, dex: PokeapiModels.Pokedex, *, clean=False) -> str:
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
        SELECT damage_factor
        FROM pokemon_v2_typeefficacy
        INNER JOIN pokemon_v2_pokemontype pv2t ON pv2t.type_id = pokemon_v2_typeefficacy.target_type_id
        INNER JOIN pokemon_v2_pokemon pv2p ON pv2p.id = pv2t.pokemon_id
        WHERE pokemon_species_id = :mon_id
        AND damage_type_id = :damage_type
        AND is_default = TRUE
        """
        result = 1

        def factory(_, row):
            nonlocal result
            result *= row[0] / 100

        async with self.replace_row_factory(factory) as conn:
            await conn.execute_fetchall(statement, {'damage_type': type_.id, 'mon_id': mon.id})
        return result

    async def get_mon_matchup_against_move(self, mon: PokeapiModels.PokemonSpecies, move: PokeapiModels.Move) -> float:
        """Calculates whether a move is effective or not against a mon"""
        if move.id == 560:  # Flying Press
            statement = """
            SELECT damage_factor
            FROM pokemon_v2_typeefficacy
            INNER JOIN pokemon_v2_pokemontype pv2t ON pv2t.type_id = pokemon_v2_typeefficacy.target_type_id
            INNER JOIN pokemon_v2_pokemon pv2p ON pv2p.id = pv2t.pokemon_id
            WHERE pokemon_species_id = :mon_id
            AND damage_type_id IN (2, 3)
            AND is_default = TRUE
            """
            result = 1.

            def factory(_, row):
                nonlocal result
                result *= row[0] / 100

            async with self.replace_row_factory(factory) as conn:
                await conn.execute_fetchall(statement, {'mon_id': mon.id})
            result = result and min(max(result, 0.5), 2)
        else:
            result = await self.get_mon_matchup_against_type(mon, move.type)
        return result

    async def get_mon_matchup_against_mon(self, mon: PokeapiModels.PokemonSpecies, mon2: PokeapiModels.PokemonSpecies) -> List[float]:
        """For each type mon2 has, determines its effectiveness against mon"""

        statement = """
        SELECT damage_factor, damage_type_id
        FROM pokemon_v2_typeefficacy
        INNER JOIN pokemon_v2_pokemontype pv2t ON pokemon_v2_typeefficacy.damage_type_id = pv2t.type_id
        INNER JOIN pokemon_v2_pokemontype pv2t2 ON pokemon_v2_typeefficacy.target_type_id = pv2t2.type_id
        INNER JOIN pokemon_v2_pokemon p ON p.id = pv2t.pokemon_id
        INNER JOIN pokemon_v2_pokemon p2 ON p2.id = pv2t2.pokemon_id
        WHERE p.pokemon_species_id = :mon2_id
        AND p.is_default = TRUE
        AND p2.pokemon_species_id = :mon_id
        AND p2.is_default = TRUE
        """
        result = collections.defaultdict(lambda: 1)

        def factory(_, row):
            result[row[1]] *= row[0] / 100
            return row

        async with self.replace_row_factory(factory) as conn:
            await conn.execute_fetchall(statement, {'mon2_id': mon2.id, 'mon_id': mon.id})
        return list(result.values())

    async def get_preevo(self, mon: PokeapiModels.PokemonSpecies) -> PokeapiModels.PokemonSpecies:
        """Get the species the given Pokemon evoles from"""
        return mon.evolves_from_species

    async def get_evos(self, mon: PokeapiModels.PokemonSpecies) -> List[PokeapiModels.PokemonSpecies]:
        """Get all species the given Pokemon evolves into"""
        statement = """
        SELECT *
        FROM pokemon_v2_pokemonspecies
        WHERE evolves_from_species_id = :id
        """
        async with self.replace_row_factory(PokeapiModels.PokemonSpecies) as conn:
            result = await conn.execute_fetchall(statement, {'id': mon.id})
        return result

    async def get_mon_learnset(self, mon: PokeapiModels.PokemonSpecies) -> Set[PokeapiModels.Move]:
        """Returns a list of all the moves the Pokemon can learn"""
        statement = """
        SELECT *
        FROM pokemon_v2_move
        INNER JOIN pokemon_v2_pokemonmove pv2p ON pokemon_v2_move.id = pv2p.move_id
        INNER JOIN pokemon_v2_pokemon pv2p2 ON pv2p.pokemon_id = pv2p2.id
        WHERE pokemon_species_id = :id
        AND is_default = TRUE
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

    async def get_mon_abilities(self, mon: PokeapiModels.PokemonSpecies) -> List[PokeapiModels.Ability]:
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
                result, = await cur.fetchone()
        return bool(result)

    async def get_formes(self, mon: PokeapiModels.PokemonSpecies) -> List[PokeapiModels.PokemonForm]:
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
        INNER JOIN pokemon_v2_pokemon pv2p ON pokemon_v2_pokemonstat.pokemon_id = pv2p.id
        WHERE pokemon_species_id = :id
        AND is_default = TRUE
        """
        async with self.replace_row_factory(PokeapiModels.PokemonStat) as conn:
            async with conn.execute(statement, {'id': mon.id}) as cur:
                return {pstat.stat.name: pstat.base_stat async for pstat in cur}

    async def get_egg_groups(self, mon: PokeapiModels.PokemonSpecies) -> List[PokeapiModels.EggGroup]:
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
            async with conn.execute(statement, {'id': mon.id, 'lang': mon.language.id, 'version': version and version.id}) as cur:
                result, = await cur.fetchone()
        return result

    async def get_mon_evolution_methods(self, mon: PokeapiModels.PokemonSpecies) -> List[PokeapiModels.PokemonEvolution]:
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
