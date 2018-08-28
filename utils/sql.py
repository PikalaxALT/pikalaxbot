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

import glob
import os
import shutil
import sqlite3
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
            self._connection.commit()
            self._connection.execute("vacuum")
            self._connection.commit()
            self._connection.close()
            self._connection = None

    def execute(self, script, args=()):
        return self._connection.execute(script, args)

    def db_init(self):
        exists, = self.execute("select count(*) from sqlite_master where type='table' and name='meme'").fetchone()
        self.execute("create table if not exists meme (bag text primary key)")
        if not exists:
            for line in default_bag:
                self.execute("insert into meme(bag) values (?)", (line,))
        self.execute("create table if not exists game (id integer primary key, name text, score integer default 0)")
        self.execute("create table if not exists voltorb (id integer primary key, level integer default 1)")
        self.execute("create table if not exists puppy (uranium integer default 0, score_puppy integer default 0, score_dead integer default 0)")

    def db_clear(self):
        self.execute("drop table if exists meme")
        self.execute("drop table if exists game")
        self.execute("drop table if exists voltorb")
        self.execute("drop table if exists puppy")

    def get_score(self, author):
        try:
            score, = self.execute("select score from game where id = ?", (author.id,)).fetchone()
        except ValueError:
            score = None
        return score

    def increment_score(self, player, by=1):
        try:
            self.execute("insert into game values (?, ?, ?)", (player.id, player.name, by))
        except sqlite3.IntegrityError:
            self.execute("update game set score = score + ? where id = ?", (by, player.id))

    def get_all_scores(self):
        yield from self.execute("select * from game order by score desc limit 10")

    def add_bag(self, text):
        try:
            self.execute("insert into meme(bag) values (?)", (text,))
        except sqlite3.IntegrityError:
            return False
        else:
            return True

    def read_bag(self):
        c = self.execute("select bag from meme order by random() limit 1")
        msg = c.fetchone()
        if msg is not None:
            return msg[0]

    def get_voltorb_level(self, channel):
        c = self.execute("select level from voltorb where id = ?", (channel.id,))
        level = c.fetchone()
        if level is None:
            self.execute("insert into voltorb values (?, 1)", (channel.id,))
            level = 1
        else:
            level, = level
        return level

    def set_voltorb_level(self, channel, new_level):
        try:
            self.execute("insert into voltorb values (?, ?)", (channel.id, new_level))
        except sqlite3.IntegrityError:
            self.execute("update voltorb set level = ? where id = ?", (new_level, channel.id))

    def get_leaderboard_rank(self, player):
        c = self.execute("select id from game order by score desc")
        for i, row in enumerate(c.fetchall()):
            id_, = row
            if id_ == player.id:
                return i + 1
        return -1

    def reset_leaderboard(self):
        self.execute("delete from game")

    def remove_bag(self, msg):
        if msg in default_bag:
            return False
        self.execute("delete from meme where bag = ?", (msg,))
        return True

    def reset_bag(self):
        self.execute("delete from meme")
        for msg in default_bag:
            self.execute("insert into meme values (?)", (msg,))

    def puppy_add_uranium(self):
        self.execute("update puppy set uranium = uranium + 1")

    def update_puppy_score(self, by):
        self.execute("update puppy set score_puppy = score_puppy + ?", (by,))

    def update_dead_score(self, by):
        self.execute("update puppy set score_dead = score_dead + ?", (by,))

    def get_uranium(self):
        c = self.execute("select uranium from puppy")
        uranium, = c.fetchone()
        return uranium

    def get_puppy_score(self):
        c = self.execute("select score_puppy from puppy")
        score, = c.fetchone()
        return score

    def get_dead_score(self):
        c = self.execute("select score_dead from puppy")
        score, = c.fetchone()
        return score

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
        return self._connection.executescript(script)
