# PikalaxBOT - A Discord bot in discord.py
# Copyright (C) 2018  PikalaxALT
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import aiosqlite
import sqlite3
import asyncio


class Sql(aiosqlite.Connection):
    def __init__(self, database, iter_chunk_size, *, loop=None, **kwargs):
        def connector():
            return sqlite3.connect(database, **kwargs)

        loop = loop or asyncio.get_event_loop()
        super().__init__(connector, iter_chunk_size, loop=loop)
        self.database = database

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.commit()
        await super().__aexit__(exc_type, exc_val, exc_tb)


def connect(database, *, iter_chunk_size=64, loop=None, **kwargs):
    """Create and return a connection proxy to the sqlite database."""
    return Sql(database, iter_chunk_size, loop=loop, **kwargs)
