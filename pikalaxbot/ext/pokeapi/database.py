import aiosqlite
import re
import collections
from typing import Coroutine, Optional, List, Set, Callable, Tuple, Any, AsyncGenerator, Union
from sqlite3 import Connection, Cursor, Row
from .models import *
from contextlib import asynccontextmanager as acm
from discord.utils import get
import random


__all__ = 'PokeApi',
__global_cache__ = {}


class PokeApi(aiosqlite.Connection):
    @staticmethod
    def _clean_name(name):
        name = name.replace('♀', '_F').replace('♂', '_m').replace('é', 'e')
        name = re.sub(r'\W+', '_', name).title()
        return name

    # Generic getters

    @acm
    async def replace_row_factory(self, factory: Callable[[Cursor, Tuple[Any]], Any]):
        old_factory = self.row_factory
        self.row_factory = factory
        yield self
        self.row_factory = old_factory

    async def get_model(self, model: Callable[[Cursor, Tuple[Any]], Any], id_: int) -> Optional[Any]:
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

    async def get_all_models(self, model: Callable[[Cursor, Tuple[Any]], Any]) -> List[Any]:
        if model in __global_cache__:
            return __global_cache__[model]
        statement = """
        SELECT *
        FROM pokemon_v2_{}
        """.format(model.__name__.lower())
        async with self.replace_row_factory(model) as conn:
            async with conn.execute(statement) as cur:
                result = await cur.fetchall()
        __global_cache__[model] = result
        return result

    async def get(self, model: Callable[[Cursor, Tuple[Any]], Any], **kwargs) -> Optional[Any]:
        return get(await self.get_all_models(model), **kwargs)

    async def filter(self, model: Callable[[Cursor, Tuple[Any]], Any], **kwargs) -> List[Any]:
        iterable = iter(await self.get_all_models(model))
        results = []
        while (record := get(iterable, **kwargs)) is not None:
            results.append(record)
        return results

    async def get_model_named(self, model: Callable[[Cursor, Tuple[Any]], Any], name: str) -> Optional[Any]:
        obj = await self.get(model, name=name)
        if obj:
            __global_cache__[(model, obj.id)] = obj
        return obj

    async def get_names_from(self, table: Callable[[Cursor, Tuple[Any]], Any], *, clean=False) -> List[str]:
        """Generic method to get a list of all names from a PokeApi table."""
        names = [await self.get_name(obj, clean=clean) for obj in await self.get_all_models(table)]
        return names

    async def get_name(self, item: NamedPokeapiResource, *, clean=False) -> str:
        return self._clean_name(item.name) if clean else item.name

    async def get_name_by_id(self, model: Callable[[Cursor, Tuple[Any]], Any], id_: int, *, clean=False):
        """Generic method to get the name of a PokeApi object given only its ID."""
        obj = await self.get_model(model, id_)
        return obj and await self.get_name(obj, clean=clean)

    async def get_random(self, model: Callable[[Cursor, Tuple[Any]], Any]) -> Optional[Any]:
        """Generic method to get a random PokeApi object."""
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

    def get_species(self, id_) -> Coroutine[None, None, Optional[PokemonSpecies]]:
        """Get a Pokemon species by ID"""
        return self.get_model(PokemonSpecies, id_)

    def random_species(self) -> Coroutine[None, None, Optional[PokemonSpecies]]:
        """Get a random Pokemon species"""
        return self.get_random(PokemonSpecies)

    def get_mon_name(self, mon: PokemonSpecies, *, clean=False) -> Coroutine[None, None, str]:
        """Get the name of a Pokemon species"""
        return self.get_name(mon, clean=clean)

    def random_species_name(self, *, clean=False) -> Coroutine[None, None, str]:
        """Get the name of a random Pokemon species"""
        return self.get_random_name(PokemonSpecies, clean=clean)

    def get_species_by_name(self, name: str) -> Coroutine[None, None, Optional[PokemonSpecies]]:
        """Get a Pokemon species given its name"""
        return self.get_model_named(PokemonSpecies, name)

    def get_forme_name(self, mon: PokemonForm, *, clean=False) -> Coroutine[None, None, str]:
        """Get a Pokemon forme's name"""
        return self.get_name(mon, clean=clean)

    def random_move(self) -> Coroutine[None, None, Optional[Move]]:
        """Get a random move"""
        return self.get_random(Move)

    def get_move_name(self, move: Move, *, clean=False) -> Coroutine[None, None, str]:
        """Get a move's name"""
        return self.get_name(move, clean=clean)

    def random_move_name(self, *, clean=False) -> Coroutine[None, None, str]:
        """Get a random move's name"""
        return self.get_random_name(Move, clean=clean)

    def get_move_by_name(self, name: str) -> Coroutine[None, None, Optional[Move]]:
        """Get a move given its name"""
        return self.get_model_named(Move, name)

    def get_mon_color(self, mon: PokemonSpecies) -> PokemonColor:
        """Get the object representing the Pokemon species' color"""
        return mon.pokemon_color

    def get_pokemon_color_by_name(self, name: str) -> Coroutine[None, None, Optional[PokemonColor]]:
        """Get a Pokemon color given its name"""
        return self.get_model_named(PokemonColor, name)

    def get_pokemon_color_name(self, color: PokemonColor, *, clean=False) -> Coroutine[None, None, str]:
        """Get the name of a Pokemon color"""
        return self.get_name(color, clean=clean)

    def get_name_of_mon_color(self, mon: PokemonSpecies, *, clean=False) -> Coroutine[None, None, str]:
        """Get the name of a Pokemon species' color"""
        return self.get_name(mon.pokemon_color, clean=clean)

    def get_ability_by_name(self, name: str) -> Coroutine[None, None, Optional[Ability]]:
        """Get an ability given its name"""
        return self.get_model_named(Ability, name)

    def get_ability_name(self, ability: Ability, *, clean=False) -> Coroutine[None, None, str]:
        """Get the name of an ability"""
        return self.get_name(ability, clean=clean)

    def get_type_by_name(self, name: str) -> Coroutine[None, None, Optional[Type]]:
        """Get a Pokemon type given its name"""
        return self.get_model_named(Type, name)

    def get_type_name(self, type_: Type, *, clean=False) -> Coroutine[None, None, str]:
        """Get the name of a type"""
        return self.get_name(type_, clean=clean)

    def get_pokedex_by_name(self, name: str) -> Coroutine[None, None, Optional[Pokedex]]:
        """Get a Pokedex given its name"""
        return self.get_model_named(Pokedex, name)

    def get_pokedex_name(self, dex: Pokedex, *, clean=False) -> Coroutine[None, None, str]:
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

    async def get_mon_types(self, mon: PokemonSpecies) -> List[Type]:
        """Returns a list of types for that Pokemon"""
        result = [montype.type for montype in await self.filter(PokemonType, pokemon__pokemon_species=mon, pokemon__is_default=True)]
        return result

    async def get_mon_matchup_against_type(self, mon: PokemonSpecies, type_: Type) -> float:
        """Calculates whether a type is effective or not against a mon"""
        result = 1
        for target_type in await self.filter(PokemonType, pokemon__pokemon_species=mon, pokemon__is_default=True):
            efficacy = await self.get(TypeEfficacy, damage_type=type_, target_type=target_type.type)
            result *= efficacy.damage_factor / 100
        return result

    async def get_mon_matchup_against_move(self, mon: PokemonSpecies, move: Move) -> float:
        """Calculates whether a move is effective or not against a mon"""
        return await self.get_mon_matchup_against_type(mon, move.type)

    async def get_mon_matchup_against_mon(self, mon: PokemonSpecies, mon2: PokemonSpecies) -> List[float]:
        """For each type mon2 has, determines its effectiveness against mon"""
        res = collections.defaultdict(lambda: 1)
        damage_types = await self.filter(PokemonType, pokemon__pokemon_species=mon2, pokemon__is_default=True)
        target_types = await self.filter(PokemonType, pokemon__pokemon_species=mon, pokemon__is_default=True)
        print(damage_types)
        print(target_types)
        for damage_type in damage_types:
            for target_type in target_types:
                efficacy = await self.get(TypeEfficacy, damage_type=damage_type.type, target_type=target_type.type)
                res[damage_type.type] *= efficacy.damage_factor / 100
        return list(res.values())

    async def get_preevo(self, mon: PokemonSpecies) -> PokemonSpecies:
        """Get the species the given Pokemon evoles from"""
        return mon.evolves_from_species

    async def get_evos(self, mon: PokemonSpecies) -> List[PokemonSpecies]:
        """Get all species the given Pokemon evolves into"""
        result = [mon2 for mon2 in await self.filter(PokemonSpecies, evolves_from_species=mon)]
        return result

    async def get_mon_learnset(self, mon: PokemonSpecies) -> Set[Move]:
        """Returns a list of all the moves the Pokemon can learn"""
        result = set(learn.move for learn in await self.filter(PokemonMove, pokemon__pokemon_species=mon, pokemon__is_default=True))
        return result
    
    async def mon_can_learn_move(self, mon: PokemonSpecies, move: Move) -> bool:
        """Returns whether a move is in the Pokemon's learnset"""
        result = await self.get(PokemonMove, move=move, pokemon__pokemon_species=mon, pokemon__is_default=True)
        return result is not None

    async def get_mon_abilities(self, mon: PokemonSpecies) -> List[Ability]:
        """Returns a list of abilities for that Pokemon"""
        result = [ability.ability for ability in await self.filter(PokemonAbility, pokemon__pokemon_species=mon, pokemon__is_default=True)]
        return result

    async def mon_has_ability(self, mon: PokemonSpecies, ability: Ability) -> bool:
        """Returns whether a Pokemon can have a given ability"""
        result = await self.get(PokemonAbility, ability=ability, pokemon__pokemon_species=mon, pokemon__is_default=True)
        return result is not None

    async def mon_has_type(self, mon: PokemonSpecies, type_: Type) -> bool:
        """Returns whether the Pokemon has the given type. Only accounts for base forms."""
        result = await self.get(PokemonType, pokemon__pokemon_species=mon, pokemon__is_default=True, type=type_)
        return result is not None

    async def has_mega_evolution(self, mon: PokemonSpecies) -> bool:
        """Returns whether the Pokemon can Mega Evolve"""
        result = await self.get(PokemonForm, is_mega=True, pokemon__pokemon_species=mon)
        return result is not None
    
    async def get_evo_line(self, mon: PokemonSpecies) -> List[PokemonSpecies]:
        """Returns the set of all Pokemon in the same evolution family as the given species."""
        result = [mon2 for mon2 in await self.filter(PokemonSpecies, evolution_chain=mon.evolution_chain)]
        return result

    async def mon_is_in_dex(self, mon: PokemonSpecies, dex: Pokedex) -> bool:
        """Returns whether a Pokemon is in the given pokedex."""
        result = await self.get(PokemonDexNumber, pokemon_species=mon, pokedex=dex)
        return result is not None

    async def get_formes(self, mon: PokemonSpecies) -> List[PokemonForm]:
        result = [form for form in await self.filter(PokemonForm, pokemon__pokemon_species=mon)]
        return result

    async def get_default_forme(self, mon: PokemonSpecies) -> PokemonForm:
        result = await self.get(PokemonForm, pokemon__pokemon_species=mon, is_default=True)
        return result
