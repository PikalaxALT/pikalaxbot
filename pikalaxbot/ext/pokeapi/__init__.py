from .database import PokeApi
import aiosqlite
import os


from .cog import *
from .models import *
from .database import *


def setup(bot):
    cog = PokeApiCog(bot)

    def factory():
        assert not cog._lock.locked(), 'PokeApi is locked'
        db_path = os.path.dirname(__file__) + '/../../../pokeapi/db.sqlite3'
        return aiosqlite.connect(db_path, factory=PokeApi)

    bot.pokeapi = factory
    bot.add_cog(cog)


def teardown(bot):
    bot.pokeapi = None
