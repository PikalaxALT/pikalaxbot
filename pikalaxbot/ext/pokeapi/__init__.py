import re
import os
import aiosqlite
import typing


class PokeApi:
    db_path = os.path.dirname(__file__) + '/../../../pokeapi/db.sqlite3'
    language = 9

    def __init__(self, *args, **kwargs):
        self._db: typing.Optional[aiosqlite.Connection] = None
        self._args = args
        self._kwargs = kwargs

    def __repr__(self):
        return f'<{self.__class__.__name__}>'

    async def connect(self, *args, **kwargs):
        if self._db is None:
            self._db = await aiosqlite.connect(PokeApi.db_path, *args, **kwargs)
        return self._db

    async def __aenter__(self):
        await self.connect(*self._args, **self._kwargs)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._db.close()
    
    def execute(self, *args, **kwargs):
        return self._db.execute(*args, **kwargs)

    @staticmethod
    def clean_name(name):
        name = name.replace('♀', '_F').replace('♂', '_m')
        name = re.sub(r'\W+', '_', name).replace('é', 'e').title()
        return name

    async def random_species(self):
        async with self.execute('SELECT * FROM pokemon_v2_pokemonspecies ORDER BY random() LIMIT 1') as cur:
            mon = await cur.fetchone()
        return mon

    random_pokemon = random_species

    async def get_mon_name(self, mon, *, clean=True):
        try:
            async with self.execute('SELECT name FROM pokemon_v2_pokemonspeciesname WHERE language_id = ? AND pokemon_species_id = ? LIMIT 1', (self.language, mon[0])) as cur:  # type: aiosqlite.Cursor
                name, = await cur.fetchone()
            if clean:
                name = PokeApi.clean_name(name)
            return name
        except TypeError:
            return 'Name not found'

    async def random_species_name(self, *, clean=True):
        async with self.execute('SELECT name FROM pokemon_v2_pokemonspeciesname WHERE language_id = ? ORDER BY random() LIMIT 1', (self.language,)) as cur:  # type: aiosqlite.Cursor
            name, = await cur.fetchone()
        if clean:
            name = PokeApi.clean_name(name)
        return name

    random_pokemon_name = random_species_name

    async def random_move(self):
        async with self.execute('SELECT * FROM pokemon_v2_move ORDER BY random() LIMIT 1') as cur:  # type: aiosqlite.Cursor
            move = await cur.fetchone()
        return move

    async def get_move_name(self, move, *, clean=True):
        try:
            async with self.execute('SELECT name FROM pokemon_v2_movename WHERE language_id = ? AND move_id = ? LIMIT 1', (self.language, move[0])) as cur:  # type: aiosqlite.Cursor
                name, = await cur.fetchone()
            if clean:
                name = PokeApi.clean_name(name)
            return name
        except TypeError:
            return 'Name not found'

    async def random_move_name(self, *, clean=True):
        async with self.execute('SELECT name FROM pokemon_v2_movename WHERE language_id = ? ORDER BY random() LIMIT 1',
                                (self.language,)) as cur:  # type: aiosqlite.Cursor
            name, = await cur.fetchone()
        if clean:
            name = PokeApi.clean_name(name)
        return name

    async def lookup_name(self, table, name):
        actual_table = f'pokemon_v2_{table}name'
        statement = f'SELECT name FROM {actual_table} WHERE language_id = ? AND name = ? COLLATE NOCASE'
        try:
            async with self.execute(statement, (self.language, name)) as cur:
                name, = await cur.fetchone()
        except TypeError:
            name = None
        return name

    async def get_mon_types(self, mon):
        """Returns a list of type names for that Pokemon"""
        async with self.execute('SELECT name FROM pokemon_v2_typename WHERE language_id = ? AND type_id IN (SELECT type_id FROM pokemon_v2_pokemontype WHERE pokemon_id = ?)', (self.language, mon[0])) as cur:  # type: aiosqlite.Cursor
            return [name async for name, in cur]

    async def get_mon_learnset(self, mon):
        """Returns a list of move names for that Pokemon"""
        async with self.execute('SELECT name FROM pokemon_v2_movename WHERE language_id = ? AND move_id IN (SELECT move_id FROM pokemon_v2_pokemonmove WHERE pokemon_id = ?)', (self.language, mon[0])) as cur:
            return [name async for name, in cur]

    async def get_mon_abilities(self, mon):
        """Returns a list of ability names for that Pokemon"""
        async with self.execute('SELECT name FROM pokemon_v2_abilityname WHERE language_id = ? AND ability_id IN (SELECT ability_id FROM pokemon_v2_pokemonability WHERE pokemon_id = ?)', (self.language, mon[0])) as cur:
            return [name async for name, in cur]


def setup(bot):
    def factory():
        return PokeApi()
    bot.pokeapi = factory


def teardown(bot):
    bot.pokeapi = None
