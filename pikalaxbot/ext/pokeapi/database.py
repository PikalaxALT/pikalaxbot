import aiosqlite
import re
import collections
import typing
from .models import *


__all__ = 'PokeApi',


def prod(iterable):
    res = 1
    for x in iterable:
        res *= x
    return res


class PokeApi(aiosqlite.Connection):
    _language = 9  # English

    def __init__(self, cog, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cog = cog

    async def __aenter__(self):
        assert not self._cog._lock.locked(), 'PokeApi is locked'
        return await super().__aenter__()

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
        self.row_factory = lambda c, r: PokemonSpecies(*r)
        async with self.execute(statement, (id_,)) as cur:
            mon = await cur.fetchone()
        return mon

    get_pokemon = get_species

    async def random_species(self) -> typing.Optional[PokemonSpecies]:
        statement = """
        SELECT *
        FROM pokemon_v2_pokemonspecies
        ORDER BY random()
        """
        self.row_factory = lambda c, r: PokemonSpecies(*r)
        async with self.execute(statement) as cur:  # type: aiosqlite.Cursor
            mon = await cur.fetchone()
        return mon

    random_pokemon = random_species

    async def get_mon_name(self, mon: PokemonSpecies, *, clean=True) -> str:
        statement = """
        SELECT name
        FROM pokemon_v2_pokemonspeciesname
        WHERE language_id = ?
        AND pokemon_species_id = ?
        """
        self.row_factory = lambda c, r: (PokeApi._clean_name if clean else str)(*r)
        async with self.execute(statement, (self._language, mon.id)) as cur:
            name = await cur.fetchone()
        return name

    get_pokemon_name = get_mon_name
    get_species_name = get_mon_name
    get_pokemon_species_name = get_mon_name

    async def random_species_name(self, *, clean=True) -> str:
        statement = """
        SELECT name
        FROM pokemon_v2_pokemonspeciesname
        WHERE language_id = ?
        ORDER BY random()
        """
        self.row_factory = lambda c, r: (PokeApi._clean_name if clean else str)(*r)
        async with self.execute(statement, (self._language,)) as cur:
            name = await cur.fetchone()
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
            AND name = ?
            COLLATE NOCASE
        )
        """
        self.row_factory = lambda c, r: PokemonSpecies(*r)
        async with self.execute(statement, (self._language, name)) as cur:
            mon = await cur.fetchone()
        if not mon:
            statement = """
            SELECT *
            FROM pokemon_v2_pokemonspecies
            WHERE name = ?
            """
            async with self.execute(statement, (self._language, name)) as cur:
                mon = await cur.fetchone()
        return mon

    get_pokemon_by_name = get_species_by_name
    get_pokemon_species_by_name = get_species_by_name

    async def random_move(self) -> typing.Optional[Move]:
        statement = """
        SELECT *
        FROM pokemon_v2_pokemonmove
        ORDER BY random()
        """
        self.row_factory = lambda c, r: Move(*r)
        async with self.execute(statement) as cur:
            move = await cur.fetchone()
        return move

    async def get_move_name(self, move: Move, *, clean=True) -> str:
        statement = """
        SELECT name
        FROM pokemon_v2_movename
        WHERE language_id = ?
        AND move_id = ?
        """
        self.row_factory = lambda c, r: (PokeApi._clean_name if clean else str)(*r)
        async with self.execute(statement, (self._language, move.id)) as cur:
            name = await cur.fetchone()
        return name

    async def random_move_name(self, *, clean=True) -> str:
        statement = """
        SELECT name
        FROM pokemon_v2_movename
        WHERE language_id = ?
        ORDER BY random()
        """
        self.row_factory = lambda c, r: (PokeApi._clean_name if clean else str)(*r)
        async with self.execute(statement, (self._language,)) as cur:
            name = await cur.fetchone()
        return name

    async def get_move_by_name(self, name: str) -> typing.Optional[Move]:
        statement = """
        SELECT *
        FROM pokemon_v2_move
        WHERE id = (
            SELECT move_id
            FROM pokemon_v2_movename
            WHERE language_id = ?
            AND name = ?
            COLLATE NOCASE
        )
        """
        self.row_factory = lambda c, r: Move(*r)
        async with self.execute(statement, (self._language, name)) as cur:
            move = await cur.fetchone()
        return move

    async def get_mon_types(self, mon: PokemonSpecies) -> typing.List[Type]:
        """Returns a list of type names for that Pokemon"""
        statement = """
        SELECT * 
        FROM pokemon_v2_pokemontype 
        WHERE pokemon_id = ?
        """
        self.row_factory = lambda c, r: Type(*r)
        async with self.execute(statement, (mon.id,)) as cur:
            result = await cur.fetchall()
        return result

    async def get_mon_matchup_against_type(self, mon: PokemonSpecies, type_: Type) -> float:
        statement = """
        SELECT damage_factor
        FROM pokemon_v2_typeefficacy
        WHERE damage_type_id = ?
        AND target_type_id IN (
            SELECT type_id
            FROM pokemon_v2_pokemontype
            WHERE pokemon_id = ?
        )
        """
        self.row_factory = lambda c, r: r[0] / 100
        async with self.execute(statement, (type_.id, mon.id)) as cur:
            efficacy = prod(await cur.fetchall())
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
        self.row_factory = lambda c, r: r[0] / 100
        async with self.execute(statement, (move.id, mon.id)) as cur:
            efficacy = prod(await cur.fetchall())
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

        def row_factory(c, r):
            res[r[0]] *= r[1] / 100
            return r

        self.row_factory = row_factory
        async with self.execute(statement, (mon2.id, mon.id)) as cur:
            await cur.fetchall()
        return list(res.values())

    async def get_mon_color(self, mon: PokemonSpecies) -> PokemonColor:
        statement = """
        SELECT *
        FROM pokemon_v2_pokemoncolorname
        WHERE pokemon_color_id = ?
        """
        self.row_factory = lambda c, r: PokemonColor(*r)
        async with self.execute(statement, (mon.pokemon_color_id,)) as cur:
            color = await cur.fetchone()
        return color

    async def get_color_by_name(self, name: str) -> typing.Optional[PokemonColor]:
        statement = """
        SELECT *
        FROM pokemon_v2_pokemoncolor
        WHERE id = (
            SELECT pokemon_color_id
            FROM pokemon_v2_pokemoncolorname
            WHERE language_id = ?
            AND name = ?
            COLLATE NOCASE
        )
        """
        self.row_factory = lambda c, r: PokemonColor(*r)
        async with self.execute(statement, (self._language, name)) as cur:
            result = await cur.fetchone()
        return result

    async def get_preevo(self, mon: PokemonSpecies) -> PokemonSpecies:
        statement = """
        SELECT *
        FROM pokemon_v2_pokemonspecies
        WHERE id = ?
        """
        self.row_factory = lambda c, r: PokemonSpecies(*r)
        async with self.execute(statement, (mon.evolves_from_species_id,)) as cur:
            result = await cur.fetchone()
        return result

    async def get_evos(self, mon: PokemonSpecies) -> typing.List[PokemonSpecies]:
        statement = """
        SELECT *
        FROM pokemon_v2_pokemonspecies
        WHERE evolves_from_species_id = ?
        """
        self.row_factory = lambda c, r: PokemonSpecies(*r)
        async with self.execute(statement, (mon.id,)) as cur:
            result = await cur.fetchall()
        return result

    async def get_mon_learnset(self, mon: PokemonSpecies) -> typing.List[Move]:
        """Returns a list of move names for that Pokemon"""
        statement = """
        SELECT *
        FROM pokemon_v2_pokemonmove
        WHERE pokemon_id = ?
        """
        self.row_factory = lambda c, r: Move(*r)
        async with self.execute(statement, (mon.id,)) as cur:
            result = await cur.fetchall()
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
        self.row_factory = lambda c, r: bool(*r)
        async with self.execute(statement, (mon.id, move.id)) as cur:
            response = await cur.fetchone()
        return response

    async def get_mon_abilities(self, mon: PokemonSpecies) -> typing.List[Ability]:
        """Returns a list of ability names for that Pokemon"""
        statement = """
        SELECT *
        FROM pokemon_v2_pokemonability
        WHERE pokemon_id = ?
        """
        self.row_factory = lambda c, r: Ability(*r)
        async with self.execute(statement, (mon.id,)) as cur:
            result = await cur.fetchall()
        return result
    
    async def get_ability_by_name(self, name: str) -> typing.Optional[Ability]:
        statement = """
        SELECT *
        FROM pokemon_v2_ability
        WHERE id = (
            SELECT ability_id
            FROM pokemon_v2_abilityname
            WHERE language_id = ?
            AND name = ?
            COLLATE NOCASE
        )
        """
        self.row_factory = lambda c, r: Ability(*r)
        async with self.execute(statement, (self._language, name)) as cur:
            ability = await cur.fetchone()
        return ability

    async def get_ability_name(self, ability: Ability, *, clean=True) -> str:
        statement = """
        SELECT name
        FROM pokemon_v2_abilityname
        WHERE language_id = ?
        AND ability_id = ?
        """
        self.row_factory = lambda c, r: (PokeApi._clean_name if clean else str)(*r)
        async with self.execute(statement, (self._language, ability.id)) as cur:
            name = await cur.fetchone()
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
        self.row_factory = lambda c, r: bool(*r)
        async with self.execute(statement, (mon.id, ability.id)) as cur:
            result = await cur.fetchone()
        return result

    async def get_type_by_name(self, name: str) -> typing.Optional[Type]:
        statement = """
        SELECT *
        FROM pokemon_v2_type
        WHERE id = (
            SELECT type_id
            FROM pokemon_v2_typename
            WHERE language_id = ?
            AND name = ?
            COLLATE NOCASE
        )
        """
        self.row_factory = lambda c, r: Type(*r)
        async with self.execute(statement, (self._language, name)) as cur:
            result = await cur.fetchone()
        return result

    async def mon_has_type(self, mon: PokemonSpecies, type_: Type) -> bool:
        statement = """
        SELECT EXISTS(
            SELECT *
            FROM pokemon_v2_pokemontype
            WHERE pokemon_id = ?
            AND type_id = ?
        )
        """
        self.row_factory = lambda c, r: bool(*r)
        async with self.execute(statement, (mon.id, type_.id)) as cur:
            result = await cur.fetchone()
        return result

    async def get_type_name(self, type_: Type, *, clean=True) -> str:
        statement = """
        SELECT name
        FROM pokemon_v2_typename
        WHERE language_id = ?
        AND type_id = ?
        """
        self.row_factory = lambda c, r: (PokeApi._clean_name if clean else str)(*r)
        async with self.execute(statement, (self._language, type_.id)) as cur:
            result = await cur.fetchone()
        return result

    async def get_color_name(self, color: PokemonColor, *, clean=True) -> str:
        statement = """
        SELECT name
        FROM pokemon_v2_pokemoncolorname
        WHERE language_id = ?
        AND pokemon_color_id = ?
        """
        self.row_factory = lambda c, r: (PokeApi._clean_name if clean else str)(*r)
        async with self.execute(statement, (self._language, color.id)) as cur:
            result = await cur.fetchone()
        return result

    async def has_mega_evolution(self, mon: PokemonSpecies) -> bool:
        statement = """
        SELECT EXISTS(
            SELECT *
            FROM pokemon_v2_pokemonformname
            WHERE name LIKE 'Mega %'
            AND language_id = ?
            AND pokemon_form_id IN (
                SELECT id
                FROM pokemon_v2_pokemon
                WHERE pokemon_species_id = ?
            )
        )
        """
        self.row_factory = lambda c, r: bool(*r)
        async with self.execute(statement, (self._language, mon.id)) as cur:
            result = await cur.fetchone()
        return result
    
    async def get_evo_line(self, mon: PokemonSpecies) -> typing.Set[PokemonSpecies]:
        result = {mon}
        while mon.evolves_from_species_id is not None:
            mon = await self.get_preevo(mon)
            result.add(mon)
        new = set(result)
        while True:
            new_copy = list(new)
            new = []
            for _mon in new_copy:
                new += await self.get_evos(_mon)
            if not new:
                break
            result += new
        return result
