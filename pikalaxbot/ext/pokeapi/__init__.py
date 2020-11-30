from .database import PokeApi
import aiosqlite
import os
import sqlite3


from .cog import *
from .models import *
from .database import *


def setup(bot):
    cog = PokeApiCog(bot)

    def factory():
        assert not cog._lock.locked(), 'PokeApi is locked'
        db_path = os.path.dirname(__file__) + '/../../../pokeapi/db.sqlite3'

        def connector():
            return sqlite3.connect(db_path)

        return PokeApi(connector, 64)

    bot.pokeapi = factory
    bot.add_cog(cog)


def teardown(bot):
    bot.pokeapi = None
