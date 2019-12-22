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
import aiofiles
import functools


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
    'roles': {},
    'watches': {},
    'error_emoji': 'pikalaOwO',
    'exc_channel': 657960851193724960,
}


class Settings(dict):
    def __init__(self, fname='settings.json', *, loop=None):
        super().__init__(**_defaults)
        self._fname = fname
        self._loop = loop or asyncio.get_event_loop()
        self._changed = False
        self._lock = asyncio.Lock()
        with open(fname) as fp:
            self.update(json.load(fp))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.commit()

    async def __aenter__(self):
        await self._lock.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._changed:
            partial = functools.partial(json.dumps, self, indent=4, separators=(', ', ': '))
            s = await self._loop.run_in_executor(None, partial)
            async with aiofiles.open(self._filename, 'w') as fp:
                await fp.write(s)
            self._changed = False
        await self._lock.release()

    def __getattr__(self, item):
        return self.get(item)

    def __setattr__(self, key, value):
        if key.startswith('_'):
            super().__setattr__(key, value)
        elif key not in self or self[key] != value:
            self[key] = value
            self._changed = True
