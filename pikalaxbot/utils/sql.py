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
    default_bag = (
        ('happily jumped into the bag!',),
        ('reluctantly clambored into the bag.',),
        ('turned away!',),
        ('let out a cry in protest!',)
    )

    def __init__(self, database, iter_chunk_size, *, loop=None, **kwargs):
        def connector():
            return sqlite3.connect(database, **kwargs)

        loop = loop or asyncio.get_event_loop()
        super().__init__(connector, iter_chunk_size, loop=loop)
        self.database = database

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.commit()
        await super().__aexit__(exc_type, exc_val, exc_tb)

    async def db_init(self, bot):
        for name, cog in bot.cogs.items():
            if hasattr(cog, 'init_db'):
                bot.log_info(f'Init db start: {name}')
                try:
                    await cog.init_db(self)
                except sqlite3.Error as e:
                    bot.log_error(f'Init db FAIL: {name}: {e}')
                else:
                    bot.log_info(f'Init db done: {name}')

    async def db_clear(self):
        await self.execute("select 'drop table ' || name || ';' from sqlite_master where type = 'table'")
        await self.execute('vacuum')

    async def increment_score(self, player, by=1):
        await self.execute('insert into game values (?, ?, ?) on conflict(id) do update set score = score + ?', (player.id, player.name, by, by))

    async def get_voltorb_level(self, channel):
        c = await self.execute("select level from voltorb where id = ?", (channel.id,))
        try:
            level, = await c.fetchone()
        except TypeError:
            level = 1
        return level

    async def set_voltorb_level(self, channel, new_level):
        await self.execute("replace into voltorb values (?, ?) on conflict (id) do update set level = ?", (channel.id, new_level, new_level))


def connect(database, *, iter_chunk_size=64, loop=None, **kwargs):
    """Create and return a connection proxy to the sqlite database."""
    return Sql(database, iter_chunk_size, loop=loop, **kwargs)
