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


_defaults = {
    'token': None,
    'prefix': 'p!',
    'markov_channels': [],
    'debug': False,
    'disabled_commands': [],
    'voice_chans': {},
    'disabled_cogs': [],
    'help_name': 'help',
    'game': 'p!help',
    'espeak_kw': {
        'a': 100,
        's': 150,
        'v': 'en-us+f3',
        'p': 75,
        'g': 1,
        'k': 2
    },
    'banlist': [],
    'roles': {}
}


class Settings:
    def __init__(self, fname='settings.json'):
        self._fname = fname
        self._container = _defaults
        with open(fname) as fp:
            self._container.update(json.load(fp))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.commit()

    def commit(self):
        with open(self._fname, 'w') as fp:
            json.dump(self._container, fp, indent=4, separators=(', ', ': '))

    def __getattr__(self, item):
        return self._container.get(item)

    def __setattr__(self, key, value):
        if key.startswith('_'):
            super().__setattr__(key, value)
        else:
            self._container[key] = value
