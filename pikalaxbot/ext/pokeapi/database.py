import aiosqlite
import re
import collections
from typing import Coroutine, Optional, List, Set
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
        name = name.replace('♀', '_F').replace('♂', '_m').replace('é', 'e')
        name = re.sub(r'\W+', '_', name).title()
        return name

    # Generic getters

    async def get_names_from(self, table: str, *, clean=True) -> List[str]:
        """Generic method to get a list of all names from a PokeApi table."""
        statement = """
        SELECT name
        FROM {tablename}
        WHERE language_id = :language
        """.format(
            tablename='pokemon_v2_' + table.replace('_', '') + 'name'
        )
        self.row_factory = lambda c, r: (PokeApi._clean_name if clean else str)(*r)
        async with self.execute(statement, {'language': self._language}) as cur:
            names = await cur.fetchall()
        return names

    async def get_name(self, item: PokeApiModel, *, clean=True) -> str:
        classname = item.__class__.__name__
        if not hasattr(item, 'id'):
            raise TypeError('Object of type {} has no attribute "id"'.format(classname))
        statement = """
        SELECT name
        FROM {nametable}
        WHERE language_id = :language
        AND {idcol} = :id
        """.format(
            nametable=f'pokemon_v2_{classname.lower()}name',
            idcol=re.sub(r'([a-z])([A-Z])', r'\1_\2', classname).lower() + '_id'
        )
        self.row_factory = lambda c, r: (PokeApi._clean_name if clean else str)(*r)
        async with self.execute(statement, {'id': item.id, 'language': self._language}) as cur:
            name = await cur.fetchone()
        return name

    async def get_name_by_id(self, table: str, id_: id, *, clean=True):
        """Generic method to get the name of a PokeApi object given only its ID."""
        nametable = 'pokemon_v2_' + table.replace('_', '') + 'name'
        idcol = table + '_id'
        statement = """
        SELECT name
        FROM {nametable}
        WHERE language_id = :language
        AND {idcol} = :id
        """.format(nametable=nametable, idcol=idcol)
        self.row_factory = lambda c, r: (PokeApi._clean_name if clean else str)(*r)
        async with self.execute(statement, {'id': id_, 'language': self._language}) as cur:
            name = await cur.fetchone()
        return name

    async def get_by_name(self, table: str, name: str) -> Optional[PokeApiModel]:
        """Generic method to get a PokeApi object given its name."""
        cls = eval(table.title().replace('_', ''))
        datatable = 'pokemon_v2_' + table.replace('_', '')
        nametable = datatable + 'name'
        idcol = table + '_id'
        statement = """
        SELECT *
        FROM {datatable}
        WHERE id = (
            SELECT {idcol}
            FROM {nametable}
            WHERE language_id = :language
            AND name = :name
            COLLATE NOCASE
        )
        """.format(
            datatable=datatable,
            nametable=nametable,
            idcol=idcol
        )
        self.row_factory = lambda c, r: cls(*r)
        async with self.execute(statement, {'language': self._language, 'name': name}) as cur:
            result = await cur.fetchone()
        if result is None:
            statement = """
            SELECT *
            FROM {datatable}
            WHERE name = :name
            COLLATE NOCASE
            """.format(datatable=datatable)
            async with self.execute(statement, {'name': name}) as cur:
                result = await cur.fetchone()
        return result

    async def get(self, table: str, _id: int) -> Optional[PokeApiModel]:
        """Generic method to get a PokeApi object given its name."""
        cls = eval(table.title().replace('_', ''))
        datatable = 'pokemon_v2_' + table.replace('_', '')
        statement = """
        SELECT *
        FROM {datatable}
        WHERE id = :id
        """.format(datatable=datatable)
        self.row_factory = lambda c, r: cls(*r)
        async with self.execute(statement, {'id': _id}) as cur:
            row = await cur.fetchone()
        return row

    async def get_random(self, table: str) -> Optional[PokeApiModel]:
        """Generic method to get a random PokeApi object."""
        cls = eval(table.title().replace('_', ''))
        datatable = 'pokemon_v2_' + table.replace('_', '')
        statement = """
        SELECT *
        FROM {datatable}
        ORDER BY random()
        """.format(datatable=datatable)
        self.row_factory = lambda c, r: cls(*r)
        async with self.execute(statement) as cur:
            row = await cur.fetchone()
        return row
    
    async def get_random_name(self, table: str, *, clean=True) -> Optional[str]:
        """Generic method to get a random PokeApi object name."""
        nametable = 'pokemon_v2_' + table.replace('_', '') + 'name'
        statement = """
        SELECT name
        FROM {nametable}
        ORDER BY random()
        """.format(nametable=nametable)
        self.row_factory = lambda c, r: (PokeApi._clean_name if clean else str)(*r)
        async with self.execute(statement) as cur:
            row = await cur.fetchone()
        return row

    # Specific getters, defined for type-hints

    def get_species(self, id_) -> Coroutine[None, None, Optional[PokemonSpecies]]:
        """Get a Pokemon species by ID"""
        return self.get('pokemon_species', id_)

    def random_species(self) -> Coroutine[None, None, Optional[PokemonSpecies]]:
        """Get a random Pokemon species"""
        return self.get_random('pokemon_species')

    def get_mon_name(self, mon: PokemonSpecies, *, clean=True) -> Coroutine[None, None, str]:
        """Get the name of a Pokemon species"""
        return self.get_name(mon, clean=clean)

    def random_species_name(self, *, clean=True) -> Coroutine[None, None, str]:
        """Get the name of a random Pokemon species"""
        return self.get_random_name('pokemon_species', clean=clean)

    def get_species_by_name(self, name: str) -> Coroutine[None, None, Optional[PokemonSpecies]]:
        """Get a Pokemon species given its name"""
        return self.get_by_name('pokemon_species', name)

    def get_forme_name(self, mon: Pokemon, *, clean=True) -> Coroutine[None, None, str]:
        """Get a Pokemon forme's name"""
        return self.get_name(mon, clean=clean)

    def random_move(self) -> Coroutine[None, None, Optional[Move]]:
        """Get a random move"""
        return self.get_random('move')

    def get_move_name(self, move: Move, *, clean=True) -> Coroutine[None, None, str]:
        """Get a move's name"""
        return self.get_name(move, clean=clean)

    def random_move_name(self, *, clean=True) -> Coroutine[None, None, str]:
        """Get a random move's name"""
        return self.get_random_name('move', clean=clean)

    def get_move_by_name(self, name: str) -> Coroutine[None, None, Optional[Move]]:
        """Get a move given its name"""
        return self.get_by_name('move', name)

    def get_mon_color(self, mon: PokemonSpecies) -> Coroutine[None, None, PokemonColor]:
        """Get the object representing the Pokemon species' color"""
        return self.get('pokemon_color', mon.pokemon_color_id)

    def get_pokemon_color_by_name(self, name: str) -> Coroutine[None, None, Optional[PokemonColor]]:
        """Get a Pokemon color given its name"""
        return self.get_by_name('pokemon_color', name)

    def get_pokemon_color_name(self, color: PokemonColor, *, clean=True) -> Coroutine[None, None, str]:
        """Get the name of a Pokemon color"""
        return self.get_name(color, clean=clean)

    def get_name_of_mon_color(self, mon: PokemonSpecies, *, clean=True) -> Coroutine[None, None, str]:
        """Get the name of a Pokemon species' color"""
        return self.get_name_by_id('pokemon_color', mon.pokemon_color_id, clean=clean)

    def get_ability_by_name(self, name: str) -> Coroutine[None, None, Optional[Ability]]:
        """Get an ability given its name"""
        return self.get_by_name('ability', name)

    def get_ability_name(self, ability: Ability, *, clean=True) -> Coroutine[None, None, str]:
        """Get the name of an ability"""
        return self.get_name(ability, clean=clean)

    def get_type_by_name(self, name: str) -> Coroutine[None, None, Optional[Type]]:
        """Get a Pokemon type given its name"""
        return self.get_by_name('type', name)

    def get_type_name(self, type_: Type, *, clean=True) -> Coroutine[None, None, str]:
        """Get the name of a type"""
        return self.get_name(type_, clean=clean)

    def get_pokedex_by_name(self, name: str) -> Coroutine[None, None, Optional[Pokedex]]:
        """Get a Pokedex given its name"""
        return self.get_by_name('pokedex', name)

    def get_pokedex_name(self, dex: Pokedex, *, clean=True) -> Coroutine[None, None, str]:
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
        """Calculates whether a type is effective or not against a mon"""
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
        """Calculates whether a move is effective or not against a mon"""
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

    async def get_mon_matchup_against_mon(self, mon: PokemonSpecies, mon2: PokemonSpecies) -> List[float]:
        """For each type mon2 has, determines its effectiveness against mon"""
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

    async def get_preevo(self, mon: PokemonSpecies) -> PokemonSpecies:
        """Get the species the given Pokemon evoles from"""
        statement = """
        SELECT *
        FROM pokemon_v2_pokemonspecies
        WHERE id = ?
        """
        self.row_factory = lambda c, r: PokemonSpecies(*r)
        async with self.execute(statement, (mon.evolves_from_species_id,)) as cur:
            result = await cur.fetchone()
        return result

    async def get_evos(self, mon: PokemonSpecies) -> List[PokemonSpecies]:
        """Get all species the given Pokemon evolves into"""
        statement = """
        SELECT *
        FROM pokemon_v2_pokemonspecies
        WHERE evolves_from_species_id = ?
        """
        self.row_factory = lambda c, r: PokemonSpecies(*r)
        async with self.execute(statement, (mon.id,)) as cur:
            result = await cur.fetchall()
        return result

    async def get_mon_learnset(self, mon: PokemonSpecies) -> List[Move]:
        """Returns a list of all the moves the Pokemon can learn"""
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
        """Returns whether a move is in the Pokemon's learnset"""
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

    async def get_mon_abilities(self, mon: PokemonSpecies) -> List[Ability]:
        """Returns a list of abilities for that Pokemon"""
        statement = """
        SELECT *
        FROM pokemon_v2_pokemonability
        WHERE pokemon_id = ?
        """
        self.row_factory = lambda c, r: Ability(*r)
        async with self.execute(statement, (mon.id,)) as cur:
            result = await cur.fetchall()
        return result

    async def mon_has_ability(self, mon: PokemonSpecies, ability: Ability) -> bool:
        """Returns whether a Pokemon can have a given ability"""
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

    async def mon_has_type(self, mon: PokemonSpecies, type_: Type) -> bool:
        """Returns whether the Pokemon has the given type. Only accounts for base forms."""
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

    async def has_mega_evolution(self, mon: PokemonSpecies) -> bool:
        """Returns whether the Pokemon can Mega Evolve"""
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
    
    async def get_evo_line(self, mon: PokemonSpecies) -> Set[PokemonSpecies]:
        """Returns the set of all Pokemon in the same evolution family as the given species."""
        result = {mon}
        while mon.evolves_from_species_id is not None:
            mon = await self.get_preevo(mon)
            result.add(mon)
        new = set(result)
        while True:
            new_copy = set(new)
            new = set()
            for _mon in new_copy:
                new.update(await self.get_evos(_mon))
            if not new:
                break
            result.update(new)
        return result

    async def mon_is_in_dex(self, mon: PokemonSpecies, dex: Pokedex) -> bool:
        """Returns whether a Pokemon is in the given pokedex."""
        statement = """
        SELECT EXISTS (
            SELECT *
            FROM pokemon_v2_pokemondexnumber
            WHERE pokemon_species_id = ?
            AND pokedex_id = ?
        )
        """
        self.row_factory = lambda c, r: bool(*r)
        async with self.execute(statement, (mon.id, dex.id)) as cur:
            result = await cur.fetchone()
        return result

    async def get_formes(self, mon: PokemonSpecies) -> List[Pokemon]:
        statement = """
        SELECT *
        FROM pokemon_v2_pokemon
        WHERE pokemon_species_id = ?
        """
        self.row_factory = lambda c, r: Pokemon(*r)
        async with self.execute(statement, (mon.id,)) as cur:
            result = await cur.fetchall()
        return result

    async def get_default_forme(self, mon: PokemonSpecies) -> Pokemon:
        statement = """
        SELECT *
        FROM pokemon_v2_pokemon
        WHERE pokemon_species_id = ?
        AND is_default = TRUE
        """
        self.row_factory = lambda c, r: Pokemon(*r)
        async with self.execute(statement, (mon.id,)) as cur:
            result = await cur.fetchone()
        return result
