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
import glob
import shutil
import time

default_bag = (
    'happily jumped into the bag!',
    'reluctantly clambored into the bag.',
    'turned away!',
    'let out a cry in protest!'
)


class Sql(aiosqlite.Connection):
    def __init__(self, database, *, loop=None, **kwargs):
        def connector():
            return sqlite3.connect(database, **kwargs)

        loop = loop or asyncio.get_event_loop()
        super().__init__(connector, loop=loop)
        self.database = database

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.commit()
        await super().__aexit__(exc_type, exc_val, exc_tb)

    async def db_init(self):
        c = await self.execute("select count(*) from sqlite_master where type='table' and name='meme'")
        exists, = await c.fetchone()
        await self.execute("create table if not exists meme (bag text primary key)")
        if not exists:
            for line in default_bag:
                await self.execute("insert into meme(bag) values (?)", (line,))
        await self.execute("create table if not exists game (id integer primary key, name text, score integer default 0)")
        await self.execute("create table if not exists voltorb (id integer primary key, level integer default 1)")
        await self.execute("create table if not exists puppy (sentinel integer primary key, uranium integer default 0, score_puppy integer default 0, score_dead integer default 0)")
        await self.execute("replace into puppy(sentinel) values (66)")
        await self.execute("create table if not exists prefixes (guild integer not null primary key, prefix text not null default \"p!\")")

    async def db_clear(self):
        await self.execute("drop table if exists meme")
        await self.execute("drop table if exists game")
        await self.execute("drop table if exists voltorb")
        await self.execute("drop table if exists puppy")
        await self.execute("drop table if exists prefixes")

    async def get_score(self, author):
        try:
            c = await self.execute("select score from game where id = ?", (author.id,))
            score, = await c.fetchone()
        except ValueError:
            score = None
        return score

    async def increment_score(self, player, by=1):
        try:
            await self.execute("insert into game values (?, ?, ?)", (player.id, player.name, by))
        except sqlite3.IntegrityError:
            await self.execute("update game set score = score + ? where id = ?", (by, player.id))

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
        try:
            await self.execute("insert into voltorb values (?, ?)", (channel.id, new_level))
        except sqlite3.IntegrityError:
            await self.execute("update voltorb set level = ? where id = ?", (new_level, channel.id))

    async def get_leaderboard_rank(self, player):
        c = await self.execute("select id from game order by score desc")
        for i, row in enumerate(await c.fetchall()):
            id_, = row
            if id_ == player.id:
                return i + 1
        return -1

    async def reset_leaderboard(self):
        await self.execute("delete from game")

    async def remove_bag(self, msg):
        if msg in default_bag:
            return False
        await self.execute("delete from meme where bag = ?", (msg,))
        return True

    async def reset_bag(self):
        await self.execute("delete from meme")
        for msg in default_bag:
            await self.execute("insert into meme values (?)", (msg,))

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

    async def backup_db(self):
        curtime = int(time.time())
        dbbak = f'{self.database}.{curtime:d}.bak'
        return await self._loop.run_in_executor(None, shutil.copy, self.database, dbbak)

    async def restore_db(self, idx):
        files = glob.glob(f'{self.database}.*.bak')
        if len(files) == 0:
            return None
        files.sort(reverse=True)
        dbbak = files[(idx - 1) % len(files)]
        await self._loop.run_in_executor(shutil.copy, dbbak, self.database)
        return dbbak

    async def get_prefix(self, guild):
        c = await self.execute("select prefix from prefixes where guild = ?", (guild.id,))
        if c.rowcount == 0:
            await self.set_prefix(guild)
            prefix = 'p!'
        else:
            prefix, = await c.fetchone()
        return prefix

    async def set_prefix(self, guild, prefix='p!'):
        await self.execute("replace into prefixes (guild, prefix) values (?, ?)", (guild.id, prefix))


def connect(database, *, loop=None, **kwargs):
    """Create and return a connection proxy to the sqlite database."""
    return Sql(database, loop=loop, **kwargs)
