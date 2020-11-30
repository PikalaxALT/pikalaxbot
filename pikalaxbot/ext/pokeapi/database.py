import os
import aiosqlite
import re
import collections
import sqlite3
import typing


__all__ = 'PokeApi', 'PokemonSpecies', 'Move', 'Ability', 'Type', 'PokemonColor'


def prod(iterable):
    res = 1
    for x in iterable:
        res *= x
    return res


PokemonSpecies = collections.namedtuple(
    'PokemonSpecies', 
    'id '
    'name '
    'order '
    'gender_rate '
    'capture_rate '
    'base_happiness '
    'is_baby '
    'hatch_counter '
    'has_gender_differences '
    'forms_switchable '
    'evolution_chain_id '
    'generation_id '
    'growth_rate_id '
    'pokemon_color_id '
    'pokemon_habitat_id '
    'pokemon_shape_id '
    'is_legendary '
    'is_mythical '
    'evolves_from_species_id'
)

Move = collections.namedtuple(
    'Move',
    'id '
    'power '
    'pp '
    'accuracy '
    'priority '
    'move_effect_chance '
    'generation_id '
    'move_damage_class_id '
    'move_effect_id '
    'move_target_id '
    'type_id '
    'contest_effect_id '
    'contest_type_id '
    'super_contest_effect_id '
    'name'
)

Ability = collections.namedtuple(
    'Ability',
    'id '
    'is_main_series '
    'generation_id name'
)

Type = collections.namedtuple(
    'Type',
    'id '
    'generation_id '
    'move_damage_class_id '
    'name'
)

PokemonColor = collections.namedtuple(
    'PokemonColor',
    'id '
    'name'
)


class PokeApi(aiosqlite.Connection):
    _db_path = os.path.dirname(__file__) + '/../../../pokeapi/db.sqlite3'
    _language = 9  # English

    def __init__(self, *, iter_chunk_size=64, **kwargs):
        super().__init__(lambda: sqlite3.connect(PokeApi._db_path, **kwargs), iter_chunk_size)

    @staticmethod
    def _clean_name(name):
        name = name.replace('♀', '_F').replace('♂', '_m')
        name = re.sub(r'\W+', '_', name).replace('é', 'e').title()
        return name

    async def get_species(self, id_) -> typing.Optional[PokemonSpecies]:
        statement = """
        SELECT *
        FROM pokemon_v2_pokemonspecies
        WHERE id = ?
        """
        async with self.execute(statement, (id_,)) as cur:
            mon = await cur.fetchone()
        return mon and PokemonSpecies(*mon)

    get_pokemon = get_species

    async def random_species(self) -> typing.Optional[PokemonSpecies]:
        statement = """
        SELECT *
        FROM pokemon_v2_pokemonspecies
        ORDER BY random()
        """
        async with self.execute(statement) as cur:
            mon = await cur.fetchone()
        return mon and PokemonSpecies(*mon)

    random_pokemon = random_species

    async def get_mon_name(self, mon: PokemonSpecies, *, clean=True) -> str:
        statement = """
        SELECT name
        FROM pokemon_v2_pokemonspeciesname
        WHERE language_id = ?
        AND pokemon_species_id = ?
        """
        async with self.execute(statement, (self._language, mon.id)) as cur:
            name, = await cur.fetchone()
        if clean:
            name = PokeApi._clean_name(name)
        return name

    get_pokemon_name = get_mon_name
    get_species_name = get_mon_name

    async def random_species_name(self, *, clean=True) -> str:
        statement = """
        SELECT name
        FROM pokemon_v2_pokemonspeciesname
        WHERE language_id = ?
        ORDER BY random()
        """
        async with self.execute(statement, (self._language,)) as cur:
            name, = await cur.fetchone()
        if clean:
            name = PokeApi._clean_name(name)
        return name

    random_pokemon_name = random_species_name
    
    async def get_species_by_name(self, name: str) -> typing.Optional[PokemonSpecies]:
        statement = """
        SELECT *
        FROM pokemon_v2_pokemonspecies
        WHERE id = (
            SELECT pokemon_species_id
            FROM pokemon_v2_pokemonspeciesname
            WHERE language_id = ?
            AND name LIKE ?
            COLLATE NOCASE
        )
        """
        async with self.execute(statement, (self._language, name)) as cur:
            mon = await cur.fetchone()
        return mon and PokemonSpecies(*mon)
    
    get_pokemon_by_name = get_species_by_name

    async def random_move(self) -> typing.Optional[Move]:
        statement = """
        SELECT *
        FROM pokemon_v2_pokemonmove
        ORDER BY random()
        """
        async with self.execute(statement) as cur:
            move = await cur.fetchone()
        return move and Move(*move)

    async def get_move_name(self, move: Move, *, clean=True) -> str:
        statement = """
        SELECT name
        FROM pokemon_v2_movename
        WHERE language_id = ?
        AND move_id = ?
        """
        async with self.execute(statement, (self._language, move.id)) as cur:
            name, = await cur.fetchone()
        if clean:
            name = PokeApi._clean_name(name)
        return name

    async def random_move_name(self, *, clean=True) -> str:
        statement = """
        SELECT name
        FROM pokemon_v2_movename
        WHERE language_id = ?
        ORDER BY random()
        """
        async with self.execute(statement, (self._language,)) as cur:
            name, = await cur.fetchone()
        if clean:
            name = PokeApi._clean_name(name)
        return name
    
    async def get_move_by_name(self, name: str) -> typing.Optional[Move]:
        statement = """
        SELECT *
        FROM pokemon_v2_move
        WHERE id = (
            SELECT move_id
            FROM pokemon_v2_movename
            WHERE language_id = ?
            AND name LIKE ?
            COLLATE NOCASE
        )
        """
        async with self.execute(statement, (self._language, name)) as cur:
            move = await cur.fetchone()
        return move and Move(*move)

    async def get_mon_types(self, mon: PokemonSpecies) -> typing.List[Type]:
        """Returns a list of type names for that Pokemon"""
        statement = """
        SELECT * 
        FROM pokemon_v2_pokemontype 
        WHERE pokemon_id = ?
        """
        async with self.execute(statement, (mon.id,)) as cur:
            result = [Type(*row) async for row in cur]
        return result

    async def get_mon_matchup_against_type(self, mon: PokemonSpecies, type_name: str) -> float:
        statement = """
        SELECT damage_factor
        FROM pokemon_v2_typeefficacy
        WHERE damage_type_id = (
            SELECT type_id
            FROM pokemon_v2_typename
            WHERE language_id = ?
            AND name = ?
            COLLATE NOCASE
        )
        AND target_type_id IN (
            SELECT type_id
            FROM pokemon_v2_pokemontype
            WHERE pokemon_id = ?
        )
        """
        async with self.execute(statement, (self._language, type_name, mon.id)) as cur:
            efficacy = prod([damage_factor / 100 async for damage_factor, in cur])
        return efficacy

    async def get_mon_matchup_against_move(self, mon: PokemonSpecies, move: Move) -> float:
        statement = """
        SELECT damage_factor
        FROM pokemon_v2_typeefficacy
        WHERE damage_type_id = (
            SELECT type_id
            FROM pokemon_v2_move
            WHERE id = ?
        )
        AND target_type_id IN (
            SELECT type_id
            FROM pokemon_v2_pokemontype
            WHERE pokemon_id = ?
        )
        """
        async with self.execute(statement, (move.id, mon.id)) as cur:
            efficacy = prod([damage_factor / 100 async for damage_factor, in cur])
        return efficacy

    async def get_mon_matchup_against_mon(self, mon: PokemonSpecies, mon2: PokemonSpecies) -> typing.List[float]:
        statement = """
        SELECT damage_type_id, damage_factor
        FROM pokemon_v2_typeefficacy
        WHERE damage_type_id IN (
            SELECT type_id
            FROM pokemon_v2_pokemontype
            WHERE id = ?
        )
        AND target_type_id IN (
            SELECT type_id
            FROM pokemon_v2_pokemontype
            WHERE pokemon_id = ?
        )
        """
        res = collections.defaultdict(lambda: 1)
        async with self.execute(statement, (mon2.id, mon.id)) as cur:
            async for damage_factor, damage_type_id in cur:
                res[damage_type_id] *= damage_factor / 100
        return list(res.values())

    async def get_mon_color(self, mon: PokemonSpecies) -> PokemonColor:
        statement = """
        SELECT *
        FROM pokemon_v2_pokemoncolorname
        WHERE pokemon_color_id = ?
        """
        async with self.execute(statement, (mon.pokemon_color_id,)) as cur:
            color = await cur.fetchone()
        return PokemonColor(*color)

    async def get_color_by_name(self, name: str) -> typing.Optional[PokemonColor]:
        statement = """
        SELECT *
        FROM pokemon_v2_pokemoncolor
        WHERE id = (
            SELECT pokemon_color_id
            FROM pokemon_v2_pokemoncolorname
            WHERE language_id = ?
            AND name LIKE ?
            COLLATE NOCASE
        )
        """
        async with self.execute(statement, (self._language, name)) as cur:
            result = await cur.fetchone()
        return result and PokemonColor(*result)

    async def get_preevo(self, mon: PokemonSpecies) -> PokemonSpecies:
        statement = """
        SELECT *
        FROM pokemon_v2_pokemonspecies
        WHERE id = ?
        """
        async with self.execute(statement, (mon.evolves_from_species_id,)) as cur:
            result = await cur.fetchone()
        return result and PokemonSpecies(*result)

    async def get_evo(self, mon: PokemonSpecies) -> typing.List[PokemonSpecies]:
        statement = """
        SELECT *
        FROM pokemon_v2_pokemonspecies
        WHERE evolves_from_species_id = ?
        """
        async with self.execute(statement, (mon.id,)) as cur:
            result = [PokemonSpecies(*mon) async for mon in cur]
        return result

    async def get_mon_learnset(self, mon: PokemonSpecies) -> typing.List[Move]:
        """Returns a list of move names for that Pokemon"""
        statement = """
        SELECT *
        FROM pokemon_v2_pokemonmove
        WHERE pokemon_id = ?
        """
        async with self.execute(statement, (mon.id,)) as cur:
            result = [Move(*move) async for move in cur]
        return result
    
    async def mon_can_learn_move(self, mon: PokemonSpecies, move: Move) -> bool:
        statement = """
        SELECT EXISTS(
            SELECT *
            FROM pokemon_v2_pokemonmove
            WHERE pokemon_id = ?
            AND move_id = ?
        )
        """
        async with self.execute(statement, (mon.id, move.id)) as cur:
            response, = await cur.fetchone()
        return bool(response)

    async def get_mon_abilities(self, mon: PokemonSpecies) -> typing.List[Ability]:
        """Returns a list of ability names for that Pokemon"""
        statement = """
        SELECT *
        FROM pokemon_v2_pokemonability
        WHERE pokemon_id = ?
        """
        async with self.execute(statement, (mon.id,)) as cur:
            result = [Ability(*ability) async for ability in cur]
        return result
    
    async def get_ability_by_name(self, name: str) -> typing.Optional[Ability]:
        statement = """
        SELECT *
        FROM pokemon_v2_ability
        WHERE id = (
            SELECT ability_id
            FROM pokemon_v2_abilityname
            WHERE language_id = ?
            AND name LIKE ?
            COLLATE NOCASE
        )
        """
        async with self.execute(statement, (self._language, name)) as cur:
            ability = await cur.fetchone()
        return ability and Ability(*ability)

    async def get_ability_name(self, ability: Ability, *, clean=True) -> str:
        statement = """
        SELECT name
        FROM pokemon_v2_abilityname
        WHERE language_id = ?
        AND ability_id = ?
        """
        async with self.execute(statement, (self._language, ability.id)) as cur:
            name, = await cur.fetchone()
        if clean:
            name = self._clean_name(name)
        return name

    async def mon_has_ability(self, mon: PokemonSpecies, ability: Ability) -> bool:
        statement = """
        SELECT EXISTS(
            SELECT *
            FROM pokemon_v2_pokemonability
            WHERE pokemon_id = ?
            AND ability_id = ?
        )
        """
        async with self.execute(statement, (mon.id, ability.id)) as cur:
            result, = await cur.fetchone()
        return bool(result)

    async def get_type_by_name(self, name: str) -> typing.Optional[Type]:
        statement = """
        SELECT *
        FROM pokemon_v2_type
        WHERE id = (
            SELECT type_id
            FROM pokemon_v2_typename
            WHERE language_id = ?
            AND name LIKE ?
            COLLATE NOCASE
        )
        """
        async with self.execute(statement, (self._language, name)) as cur:
            result = await cur.fetchone()
        return result and Type(*result)

    async def mon_has_type(self, mon: PokemonSpecies, type_: Type) -> bool:
        statement = """
        SELECT EXISTS(
            SELECT *
            FROM pokemon_v2_pokemontype
            WHERE pokemon_id = ?
            AND type_id = ?
        )
        """
        async with self.execute(statement, (mon.id, type_.id)) as cur:
            result, = await cur.fetchone()
        return bool(result)
