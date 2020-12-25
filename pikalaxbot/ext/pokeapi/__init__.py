import os
import sqlite3

from ... import __dirname__

from .cog import *
from .models import *
from .database import *


def setup(bot):
    cog = PokeApiCog(bot)

    db_path = os.path.join('file:' + os.path.dirname(__dirname__), 'pokeapi', 'db.sqlite3?mode=ro')

    def connector():
        return sqlite3.connect(db_path, factory=PokeApiConnection, uri=True)

    conn = PokeApi(connector, 64)

    bot.pokeapi = conn
    bot.add_cog(cog)


def teardown(bot):
    bot.pokeapi = None
