from .database import PokeApi
import aiosqlite
import os
import sqlite3


from .cog import *
from .models import *
from .database import *


def setup(bot):
    cog = PokeApiCog(bot)

    def factory(*, iter_chunk_size=64, **kwargs):
        assert not cog._lock.locked(), 'PokeApi is locked'
        db_path = os.path.dirname(__file__) + '/../../../pokeapi/db.sqlite3'

        def connector():
            return sqlite3.connect(db_path, **kwargs)

        return PokeApi(connector, iter_chunk_size)

    bot.pokeapi = factory
    bot.add_cog(cog)


def teardown(bot):
    bot.pokeapi = None
