import os

from ... import __dirname__

from .cog import *
from .models import *
from .database import *


def setup(bot):
    db_path = os.path.join('file:' + os.path.dirname(__dirname__), 'pokeapi', 'db.sqlite3?mode=ro')
    bot.pokeapi = PokeApi(db_path, factory=PokeApiConnection, uri=True)
    bot.add_cog(PokeApiCog(bot))


def teardown(bot):
    bot.pokeapi._conn.interrupt()
    bot.pokeapi = None
