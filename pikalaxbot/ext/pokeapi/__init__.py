import re
import os
import aiosqlite
import typing
import collections
import discord
from discord.ext import commands, tasks
import asyncio
import traceback
import contextlib
import sqlite3


def prod(iterable):
    res = 1
    for x in iterable:
        res *= x
    return res


class PokeApi(aiosqlite.Connection):
    db_path = os.path.dirname(__file__) + '/../../../pokeapi/db.sqlite3'
    language = 9  # English
    PokemonSpecies = collections.namedtuple('PokemonSpecies', 'id name order gender_rate capture_rate base_happiness is_baby hatch_counter has_gender_differences forms_switchable evolution_chain_id generation_id growth_rate_id pokemon_color_id pokemon_habitat_id pokemon_shape_id is_legendary is_mythical evolves_from_species_id')
    Move = collections.namedtuple('Move', 'id power pp accuracy priority move_effect_chance generation_id move_damage_class_id move_effect_id move_target_id type_id contest_effect_id contest_type_id super_contest_effect_id name')

    def __init__(self, *, iter_chunk_size=64, **kwargs):
        super().__init__(lambda: sqlite3.connect(PokeApi.db_path, **kwargs), iter_chunk_size)

    @staticmethod
    def clean_name(name):
        name = name.replace('♀', '_F').replace('♂', '_m')
        name = re.sub(r'\W+', '_', name).replace('é', 'e').title()
        return name

    async def get_species(self, id_) -> PokemonSpecies:
        statement = """
        SELECT *
        FROM pokemon_v2_pokemonspecies
        WHERE id = ?
        """
        async with self.execute(statement, (id_,)) as cur:
            mon = await cur.fetchone()
        return mon and PokeApi.PokemonSpecies(*mon)

    get_pokemon = get_species

    async def random_species(self) -> PokemonSpecies:
        statement = """
        SELECT *
        FROM pokemon_v2_pokemonspecies
        ORDER BY random()
        """
        async with self.execute(statement) as cur:
            mon = await cur.fetchone()
        return mon and PokeApi.PokemonSpecies(*mon)

    random_pokemon = random_species

    async def get_mon_name(self, mon: PokemonSpecies, *, clean=True):
        statement = """
        SELECT name
        FROM pokemon_v2_pokemonspeciesname
        WHERE language_id = ?
        AND pokemon_species_id = ?
        """
        async with self.execute(statement, (self.language, mon.id)) as cur:
            name, = await cur.fetchone()
        if clean:
            name = PokeApi.clean_name(name)
        return name

    async def random_species_name(self, *, clean=True):
        statement = """
        SELECT name
        FROM pokemon_v2_pokemonspeciesname
        WHERE language_id = ?
        ORDER BY random()
        """
        async with self.execute(statement, (self.language,)) as cur:
            name, = await cur.fetchone()
        if clean:
            name = PokeApi.clean_name(name)
        return name

    random_pokemon_name = random_species_name

    async def random_move(self) -> Move:
        async with self.execute('SELECT * FROM pokemon_v2_move ORDER BY random() LIMIT 1') as cur:
            move = await cur.fetchone()
        return move and PokeApi.Move(*move)

    async def get_move_name(self, move, *, clean=True):
        statement = """
        SELECT name
        FROM pokemon_v2_movename
        WHERE language_id = ?
        AND move_id = ?
        """
        async with self.execute(statement, (self.language, move[0])) as cur:
            name, = await cur.fetchone()
        if clean:
            name = PokeApi.clean_name(name)
        return name

    async def random_move_name(self, *, clean=True):
        statement = """
        SELECT name
        FROM pokemon_v2_movename
        WHERE language_id = ?
        ORDER BY random()
        """
        async with self.execute(statement, (self.language,)) as cur:
            name, = await cur.fetchone()
        if clean:
            name = PokeApi.clean_name(name)
        return name

    async def get_mon_types(self, mon: PokemonSpecies):
        """Returns a list of type names for that Pokemon"""
        statement = """
        SELECT name
        FROM pokemon_v2_typename 
        WHERE language_id = ? 
        AND type_id IN (
            SELECT type_id 
            FROM pokemon_v2_pokemontype 
            WHERE pokemon_id = ?
        )
        """
        async with self.execute(statement, (self.language, mon.id)) as cur:
            return [name async for name, in cur]

    async def get_mon_matchup_against_type(self, mon: PokemonSpecies, type_name):
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
        async with self.execute(statement, (self.language, type_name, mon.id)) as cur:
            efficacy = prod([damage_factor async for damage_factor, in cur])
        return efficacy

    async def get_mon_matchup_against_move(self, mon: PokemonSpecies, move_name):
        statement = """
        SELECT damage_factor
        FROM pokemon_v2_typeefficacy
        WHERE damage_type_id = (
            SELECT type_id
            FROM pokemon_v2_move
            WHERE id = (
                SELECT move_id
                FROM pokemon_v2_movename
                WHERE language_id = ?
                AND name = ?
                COLLATE NOCASE
            )
        )
        AND target_type_id IN (
            SELECT type_id
            FROM pokemon_v2_pokemontype
            WHERE pokemon_id = ?
        )
        """
        async with self.execute(statement, (self.language, move_name, mon.id)) as cur:
            efficacy = prod([damage_factor async for damage_factor, in cur])
        return efficacy

    async def get_mon_matchup_against_mon(self, mon: PokemonSpecies, mon_name):
        statement = """
        SELECT damage_type_id, damage_factor
        FROM pokemon_v2_typeefficacy
        WHERE damage_type_id IN (
            SELECT type_id
            FROM pokemon_v2_pokemontype
            WHERE id = (
                SELECT pokemon_species_id
                FROM pokemon_v2_pokemonspeciesname
                WHERE language_id = ?
                AND name = ?
                COLLATE NOCASE
            )
        )
        AND target_type_id IN (
            SELECT type_id
            FROM pokemon_v2_pokemontype
            WHERE pokemon_id = ?
        )
        """
        res = collections.defaultdict(lambda: 1)
        async with self.execute(statement, (self.language, mon_name, mon.id)) as cur:
            async for damage_factor, damage_type_id in cur:
                res[damage_type_id] *= damage_factor
        return list(res.values())

    async def get_mon_color(self, mon: PokemonSpecies):
        statement = """
        SELECT name
        FROM pokemon_v2_pokemoncolorname
        WHERE pokemon_color_id = ?
        """
        async with self.execute(statement, (mon.pokemon_color_id,)) as cur:
            name, = await cur.fetchone()
        return name

    async def get_preevo(self, mon: PokemonSpecies):
        statement = """
        SELECT *
        FROM pokemon_v2_pokemonspecies
        WHERE evolves_from_species_id = ?
        """
        async with self.execute(statement, (mon.id,)) as cur:
            name, = await cur.fetchone()
        return name

    async def get_mon_learnset(self, mon: PokemonSpecies):
        """Returns a list of move names for that Pokemon"""
        statement = """
        SELECT name
        FROM pokemon_v2_movename
        WHERE language_id = ?
        AND move_id IN (
            SELECT move_id
            FROM pokemon_v2_pokemonmove
            WHERE pokemon_id = ?
        )
        """
        async with self.execute(statement, (self.language, mon.id)) as cur:
            return [name async for name, in cur]

    async def get_mon_abilities(self, mon: PokemonSpecies):
        """Returns a list of ability names for that Pokemon"""
        statement = """
        SELECT name
        FROM pokemon_v2_abilityname
        WHERE language_id = ?
        AND ability_id IN (
            SELECT ability_id
            FROM pokemon_v2_pokemonability
            WHERE pokemon_id = ?
        )
        """
        async with self.execute(statement, (self.language, mon.id)) as cur:
            return [name async for name, in cur]


class PokeApiCog(commands.Cog, command_attrs={'hidden': True}):
    def __init__(self, bot):
        self.bot = bot
        self._lock = asyncio.Lock()

    def cog_unload(self):
        if not self._lock.locked():
            raise AssertionError('cannot unload pokeapi while an update is in progress')

    @contextlib.asynccontextmanager
    async def acquire(self):
        await self._lock.acquire()
        factory = self.bot.pokeapi

        class DummyPokeApi:
            async def __aenter__(self):
                return NotImplemented

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return NotImplemented

        self.bot.pokeapi = lambda: DummyPokeApi()
        yield
        self.bot.pokeapi = factory
        self._lock.release()

    @commands.group()
    async def pokeapi(self, ctx):
        """Commands for interfacing with pokeapi"""

    @commands.max_concurrency(1)
    @commands.is_owner()
    @pokeapi.command(name='rebuild', aliases=['update'])
    async def rebuild_pokeapi(self, ctx):
        """Rebuild the pokeapi database"""
        async with self.acquire():
            shell = await asyncio.create_subprocess_shell('../../../setup_pokeapi.sh')
            embed = discord.Embed(title='Updating PokeAPI', description='Started', colour=0xf47fff)
            msg = await ctx.send(embed=embed)

            @tasks.loop(seconds=10)
            async def update_msg():
                elapsed = (update_msg._next_iteration - msg.created_at).total_seconds()
                embed.description = f'Still running... ({elapsed:.0f}s)'
                await msg.edit(embed=embed)

            done, pending = await asyncio.wait({update_msg.start(), self.bot.loop.create_task(shell.wait)}, return_when=asyncio.FIRST_COMPLETED)
        [task.cancel() for task in pending]
        try:
            done.pop().result()
        except Exception as e:
            embed.colour = discord.Colour.red()
            tb = ''.join(traceback.format_exception(e.__class__, e, e.__traceback__))
            if len(tb) > 2040:
                tb = '...\n' + tb[-2036:]
            embed.title = 'Update failed'
            embed.description = f'```\n{tb}\n```'
        else:
            embed.colour = discord.Colour.green()
            embed.title = 'Update succeeded!'
            embed.description = 'You can now use pokeapi again'
        await msg.edit(embed=embed)


def setup(bot):
    def factory():
        return PokeApi()
    bot.pokeapi = factory


def teardown(bot):
    bot.pokeapi = None
