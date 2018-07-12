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

import asyncio
import functools
import os
import shutil
import sqlite3
import glob
import time

default_bag = (
    'happily jumped into the bag!',
    'reluctantly clambored into the bag.',
    'turned away!',
    'let out a cry in protest!'
)


class Sql:
    def __init__(self, fname='data/db.sql'):
        self.fname = fname
        os.makedirs(os.path.dirname(fname), exist_ok=True)
        self._connection: sqlite3.Connection = None

    def __enter__(self):
        if self._connection is None:
            self._connection = sqlite3.connect(self.fname)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._connection is not None:
            self._connection.__exit__(exc_type, exc_val, exc_tb)
            self._connection = None

    def execute(self, script, args=()):
        return self._connection.execute(script, args)

    def db_init(self):
        try:
            self.execute('select * from meme')
        except sqlite3.OperationalError:
            c = self.execute('create table meme (bag text)')
            for line in default_bag:
                c.execute("insert into meme(bag) values (?)", (line,))

        try:
            self.execute('select * from game')
        except sqlite3.OperationalError:
            self.execute('create table game (id integer, name text, score integer)')

        try:
            self.execute('select * from voltorb')
        except sqlite3.OperationalError:
            self.execute('create table voltorb (id integer, level integer)')

    def db_clear(self):
        try:
            self.execute("drop table meme")
        except sqlite3.Error:
            pass
        try:
            self.execute("drop table game")
        except sqlite3.Error:
            pass
        try:
            self.execute('drop table voltorb')
        except sqlite3.Error:
            pass
        self.execute('vacuum')

    def get_score(self, author):
        c = self.execute('select score from game where id = ? limit 1', (author.id,))
        score = c.fetchone()
        if hasattr(score, '__getitem__'):
            score = score[0]
        return score


    def increment_score(self, player, by=1):
        c = self.execute("select score from game where id = ?", (player.id,))
        score = c.fetchone()
        if score is None:
            self.execute("insert into game values (?, ?, ?)", (player.id, player.name, by))
        else:
            self.execute('update game set score = score + ? where id = ?', (by, player.id))


    def get_all_scores(self):
        yield from self.execute('select * from game order by score desc limit 10')


    def add_bag(self, text):
        c = self.execute('select * from meme where bag = ?', (text,))
        res = c.fetchone() is None
        if res:
            self.execute("insert into meme(bag) values (?)", (text,))
        return res


    def read_bag(self):
        c = self.execute('select bag from meme order by random() limit 1')
        msg = c.fetchone()
        if msg is not None:
            return msg[0]


    def get_voltorb_level(self, channel):
        c = self.execute('select level from voltorb where id = ?', (channel.id,))
        level = c.fetchone()
        if level is None:
            self.execute('insert into voltorb values (?, 1)', (channel.id,))
            level = 1
        else:
            level, = level
        return level

    def set_voltorb_level(self, channel, new_level):
        c = self.execute('select level from voltorb where id = ? limit 1', (channel.id,))
        level = c.fetchone()
        if level is None:
            self.execute('insert into voltorb values (?, ?)', (channel.id, new_level))
        else:
            self.execute('update voltorb set level = ? where id = ?', (new_level, channel.id))

    def get_leaderboard_rank(self, player):
        c = self.execute('select id from game order by score desc')
        for i, row in enumerate(c.fetchall()):
            id_, = row
            if id_ == player.id:
                return i + 1
        return -1

    def reset_leaderboard(self):
        self.execute('delete from game')
        self.execute('vacuum')

    def remove_bag(self, msg):
        if msg in default_bag:
            return False
        self.execute('delete from meme where bag = ?', (msg,))
        self.execute('vacuum')
        return True

    def reset_bag(self):
        self.execute('delete from meme')
        self.execute('vacuum')
        for msg in default_bag:
            self.execute('insert into meme values (?)', (msg,))

    def backup_db(self):
        curtime = int(time.time())
        return shutil.copy(self.fname, f'{self.fname}.{curtime:d}.bak')

    def restore_db(self, idx):
        files = glob.glob(f'{self.fname}.*.bak')
        if len(files) == 0:
            return None
        files.sort(reverse=True)
        dbbak = files[(idx - 1) % len(files)]
        shutil.copy(dbbak, self.fname)
        return dbbak

    def call_script(self, script):
        self.execute(script)
