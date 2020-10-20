import random
import re
import io
from csv import DictReader
import os
import discord
from aiofile import AIOFile, LineReader


# Copied from aiofile readme
class AsyncDictReader:
    def __init__(self, afp, **kwargs):
        self.buffer = io.BytesIO()
        self.file_reader = LineReader(
            afp, line_sep=kwargs.pop('line_sep', '\n'),
            chunk_size=kwargs.pop('chunk_size', 4096),
            offset=kwargs.pop('offset', 0),
        )
        self.reader = DictReader(
            io.TextIOWrapper(
                self.buffer,
                encoding=kwargs.pop('encoding', 'utf-8'),
                errors=kwargs.pop('errors', 'replace'),
            ), **kwargs,
        )
        self.line_num = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.line_num == 0:
            header = await self.file_reader.readline()
            self.buffer.write(header)

        line = await self.file_reader.readline()

        if not line:
            raise StopAsyncIteration

        self.buffer.write(line)
        self.buffer.seek(0)

        try:
            result = next(self.reader)
        except StopIteration as e:
            raise StopAsyncIteration from e

        self.buffer.seek(0)
        self.buffer.truncate(0)
        self.line_num = self.reader.line_num

        return result


class PokeApi:
    path = os.path.dirname(__file__) + '/../../../pokeapi/data/v2/csv'
    language = '9'

    def __init__(self, *, bot):
        self._bot = bot
        self._loaded_csvs = {}

    def __repr__(self):
        return f'<PokeApi with {len(self._loaded_csvs)} table(s) cached>'

    @staticmethod
    def clean_name(name):
        name = name.replace('♀', '_F').replace('♂', '_m')
        name = re.sub(r'\W+', '_', name).replace('é', 'e').title()
        return name

    async def get(self, item):
        if item not in self._loaded_csvs:
            path = f'{PokeApi.path}/{item}.csv'
            if not os.path.exists(path):
                raise AttributeError(f'Object of type {self.__class__.__name__} has no attribute \'{item}\'')
            async with AIOFile(path) as fp:
                self._loaded_csvs[item] = [row async for row in AsyncDictReader(fp)]
        return self._loaded_csvs[item]

    async def random_pokemon(self):
        pokemon = await(self.get('pokemon'))
        return random.choice(pokemon)

    async def random_pokemon_name(self, *, clean=True):
        def find_cb(row):
            return row['pokemon_species_id'] == mon['id'] and row['local_language_id'] == PokeApi.language

        mon = await self.random_pokemon()
        mon_names = await(self.get('pokemon_species_names'))
        mon_names += await(self.get('pokemon_form_names'))
        name = discord.utils.find(find_cb, mon_names)['name']
        if clean:
            name = self.clean_name(name)
        return name

    async def random_move(self):
        moves = await self.get('moves')
        return random.choice(moves)

    async def random_move_name(self, *, clean=True):
        def find_cb(row):
            return row['move_id'] == move['id'] and row['local_language_id'] == PokeApi.language

        move = await self.random_move()
        move_names = await self.get('move_names')
        name = discord.utils.find(find_cb, move_names)['name']
        if clean:
            name = self.clean_name(name)
        return name


def setup(bot):
    bot.pokeapi = PokeApi(bot=bot)


def teardown(bot):
    bot.pokeapi = None
