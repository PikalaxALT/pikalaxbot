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
import json
import os
from collections import defaultdict


class SettingsCategory:
    def __init__(self):
        self.name = self.__class__.__name__.lower()

    def items(self):
        yield from self.__dict__.items()


class Credentials(SettingsCategory):
    token = None
    owner = None


class Meta(SettingsCategory):
    prefix = '!'


class User(SettingsCategory):
    markov_channels = []
    debug = False
    disabled_commands = []
    voice_chans = {}
    disabled_cogs = []
    help_name = 'pikahelp'
    game = '!pikahelp'
    espeak_kw = {
        'a': 100,
        's': 150,
        'v': 'en-us+f3',
        'p': 75
    }
    banlist = []
    roles = {}


class Settings:
    credentials = Credentials()
    meta = Meta()
    user = User()
    categories = credentials, meta, user

    def __init__(self, fname='settings.json'):
        self.fname = fname
        self.fetch()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.commit()

    def commit(self):
        data = defaultdict(dict)
        for cat in self.categories:
            for key, value in cat.items():
                if key == cat:
                    continue
                if isinstance(value, set):
                    value = list(value)
                data[cat.name][key] = value
        with open(self.fname, 'w') as fp:
            json.dump(data, fp, separators=(', ', ': '), indent=4)

    def fetch(self):
        mode = 'r' if os.path.exists(self.fname) else 'w+'
        if os.path.dirname(self.fname) and not os.path.exists(os.path.dirname(self.fname)):
            os.makedirs(os.path.dirname(self.fname), exist_ok=True)
        with open(self.fname, mode=mode) as fp:
            data = json.load(fp)
        for cat, grp in data.items():
            obj = getattr(self, cat)
            for key, value in grp.items():
                setattr(obj, key, value)
