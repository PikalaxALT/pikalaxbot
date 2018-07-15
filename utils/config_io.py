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
import types
from collections import defaultdict


class SettingsContainer:
    token = None
    owner = None
    prefix = '!'
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

    def __init__(self, **kw):
        for key, value in kw.items():
            if hasattr(self, key):
                setattr(self, key, value)

    @classmethod
    def from_json(cls, fname):
        with open(fname) as fp:
            return cls(**json.load(fp))

    def to_json(self, fname):
        with open(fname) as fp:
            data = json.load(fp)
        for key in data:
            if hasattr(self, key):
                data[key] = getattr(self, key)
        with open(fname, 'w') as fp:
            json.dump(data, fp, indent=4, separators=(', ', ': '))


class Settings:
    def __init__(self, fname='settings.json'):
        self.fname = fname
        self.container = SettingsContainer.from_json(fname)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.commit()

    def commit(self):
        self.container.to_json(self.fname)

    def __getattr__(self, item):
        return getattr(self.container, item)
