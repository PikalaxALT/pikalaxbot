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
        await self.execute("drop table if exists meme")
        await self.execute("drop table if exists game")
        await self.execute("drop table if exists voltorb")
        await self.execute("drop table if exists puppy")
        await self.execute("drop table if exists prefixes")

    async def increment_score(self, player, by=1):
        await self.execute('insert into game values (?, ?, ?) on conflict(id) do update set score = score + ?', (player.id, player.name, by, by))

    async def get_all_scores(self):
        c = await self.execute("select * from game order by score desc limit 10")
        for row in await c.fetchall():
            yield row

    async def add_bag(self, text):
        try:
            await self.execute("insert into meme(bag) values (?)", (text,))
        except sqlite3.IntegrityError:
            return False
        else:
            return True

    async def read_bag(self):
        c = await self.execute("select bag from meme order by random() limit 1")
        msg = await c.fetchone()
        if msg is not None:
            return msg[0]

    async def get_voltorb_level(self, channel):
        c = await self.execute("select level from voltorb where id = ?", (channel.id,))
        level = await c.fetchone()
        if level is None:
            await self.execute("insert into voltorb values (?, 1)", (channel.id,))
            level = 1
        else:
            level, = level
        return level

    async def set_voltorb_level(self, channel, new_level):
        await self.execute("replace into voltorb values (?, ?)", (channel.id, new_level))

    async def get_leaderboard_rank(self, player):
        c = await self.execute("select score, rank () over (order by score desc) ranking from game where id = ?", (player.id,))
        record = await c.fetchone()
        return record

    async def reset_leaderboard(self):
        await self.execute("delete from game")

    async def remove_bag(self, msg):
        if (msg,) in self.default_bag:
            return False
        await self.execute("delete from meme where bag = ?", (msg,))
        return True

    async def reset_bag(self):
        await self.execute("delete from meme")
        await self.executemany("insert into meme values(?)", self.default_bag)

    async def puppy_add_uranium(self):
        await self.execute("update puppy set uranium = uranium + 1")

    async def update_puppy_score(self, by):
        await self.execute("update puppy set score_puppy = score_puppy + ?", (by,))

    async def update_dead_score(self, by):
        await self.execute("update puppy set score_dead = score_dead + ?", (by,))

    async def get_uranium(self):
        c = await self.execute("select uranium from puppy")
        uranium, = await c.fetchone()
        return uranium

    async def get_puppy_score(self):
        c = await self.execute("select score_puppy from puppy")
        score, = await c.fetchone()
        return score

    async def get_dead_score(self):
        c = await self.execute("select score_dead from puppy")
        score, = await c.fetchone()
        return score

    async def get_prefix(self, bot, message):
        c = await self.execute("select prefix from prefixes where guild = ?", (message.guild.id,))
        try:
            prefix, = await c.fetchone()
        except TypeError:
            await self.set_prefix(message.guild, prefix=bot.settings.prefix)
            prefix = bot.settings.prefix
        return prefix

    async def set_prefix(self, guild, prefix='p!'):
        await self.execute("replace into prefixes (guild, prefix) values (?, ?)", (guild.id, prefix))


def connect(database, *, iter_chunk_size=64, loop=None, **kwargs):
    """Create and return a connection proxy to the sqlite database."""
    return Sql(database, iter_chunk_size, loop=loop, **kwargs)
