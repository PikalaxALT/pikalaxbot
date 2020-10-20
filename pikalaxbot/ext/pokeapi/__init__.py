import random
import re
import aiofile
import io
import csv
import os
import discord
import glob


class AsyncDictReader:
    def __init__(self, afp, **kwargs):
        self.buffer = io.BytesIO()
        self.file_reader = aiofile.LineReader(
            afp, line_sep=kwargs.pop('line_sep', '\n'),
            chunk_size=kwargs.pop('chunk_size', 4096),
            offset=kwargs.pop('offset', 0),
        )
        self.reader = csv.DictReader(
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
        self._ready = False
        self._bot.loop.create_task(self.__ainit__())

    async def __ainit__(self):
        for file in glob.glob(f'{PokeApi.path}/*.csv'):
            attrname = os.path.splitext(os.path.basename(file))[0]
            async with aiofile.AIOFile(file, 'rb') as fp:
                setattr(self, attrname, [row async for row in AsyncDictReader(fp)])
        self._ready = True
        self._bot.dispatch('pokeapi_ready')

    @property
    def ready(self):
        return self._ready

    def __repr__(self):
        return f'<{self.__class__.__name__}>'

    @staticmethod
    def clean_name(name):
        name = name.replace('♀', '_F').replace('♂', '_m')
        name = re.sub(r'\W+', '_', name).replace('é', 'e').title()
        return name

    def random_pokemon(self):
        return random.choice(self.pokemon)

    def random_pokemon_name(self, *, clean=True):
        def find_cb(row):
            return row['pokemon_species_id'] == mon['id'] and row['local_language_id'] == PokeApi.language

        mon = self.random_pokemon()
        mon_names = self.pokemon_species_names + self.pokemon_form_names
        name = discord.utils.find(find_cb, mon_names)['name']
        if clean:
            name = self.clean_name(name)
        return name

    def random_move(self):
        return random.choice(self.moves)

    def random_move_name(self, *, clean=True):
        def find_cb(row):
            return row['move_id'] == move['id'] and row['local_language_id'] == PokeApi.language

        move = self.random_move()
        name = discord.utils.find(find_cb, self.move_names)['name']
        if clean:
            name = self.clean_name(name)
        return name


def setup(bot):
    bot.pokeapi = PokeApi(bot=bot)


def teardown(bot):
    bot.pokeapi = None
