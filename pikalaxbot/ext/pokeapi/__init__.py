import os
import sqlite3

from ... import __dirname__

from .cog import *
from .models import *
from .database import *


def setup(bot):
    cog = PokeApiCog(bot)

    db_path = os.path.join(os.path.dirname(__dirname__), 'pokeapi', 'db.sqlite3')

    def connector():
        return sqlite3.connect(db_path, factory=PokeApiConnection)

    conn = PokeApi(connector, 64)

    bot.pokeapi = conn
    bot.add_cog(cog)


def teardown(bot):
    bot.pokeapi = None
