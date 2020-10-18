import aiohttp
import random
import re


class PokeApi:
    url = 'https://pokeapi.co/api/v2'

    def __init__(self, *, cs: aiohttp.ClientSession = None):
        self._natdex = None
        self._movebank = None
        self.cs = cs or aiohttp.ClientSession(raise_for_status=True)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cs.close()

    async def get_json(self, endpoint):
        async with self.cs.get(f'{self.url}/{endpoint}') as res:
            return await res.json()

    def get_pokemon(self, id_or_name):
        return self.get_json(f'pokemon/{id_or_name}/')

    def get_move(self, id_or_name):
        return self.get_json(f'move/{id_or_name}')

    async def init_caches(self):
        init_movebank = self._movebank is None
        init_natdex = self._natdex is None
        if init_movebank or init_natdex:
            gens = [await self.get_json(f'generation/{i + 1}') for i in range(8)]
            if init_movebank:
                self._movebank = []
            if init_natdex:
                self._natdex = []
            for gen in gens:
                if init_movebank:
                    self._movebank += gen['moves']
                if init_natdex:
                    self._natdex += gen['pokemon_species']

    async def random_pokemon(self):
        await self.init_caches()
        return random.choice(self._natdex)

    async def random_pokemon_name(self, *, clean=True):
        mon = await self.random_pokemon()
        name = mon['name']
        if clean:
            name = name.replace('♀', '_F').replace('♂', '_m')
            name = re.sub(r'\W+', '_', name).replace('é', 'e').title()
        return name

    async def random_pokemon_attr(self, attr, default=None):
        mon = await self.random_pokemon()
        return mon.get(attr, default)

    async def random_move(self):
        await self.init_caches()
        return random.choice(self._movebank)

    async def random_move_name(self, *, clean=True):
        move = await self.random_move()
        name = move['name']
        if clean:
            name = name.replace('♀', '_F').replace('♂', '_m')
            name = re.sub(r'\W+', '_', name).replace('é', 'e').title()
        return name

    async def random_move_attr(self, attr, default=None):
        move = await self.random_move()
        return move.get(attr, default)
