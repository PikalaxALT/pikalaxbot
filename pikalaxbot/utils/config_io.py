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
import typing
from ..constants import *

__all__ = ('Settings',)


class Settings:
    token: str = None
    prefix: str = 'p!'
    markov_channels: list[int] = []
    debug: bool = False
    disabled_commands: list[str] = []
    disabled_cogs: list[str] = []
    help_name: str = 'help'
    game: str = 'Q20, Anagram, Hangman'
    espeak_kw: dict[str, typing.Union[str, int]] = {
        'a': 100,
        's': 150,
        'v': 'en-us+f3',
        'p': 75,
        'g': 1,
        'k': 2,
    }
    banlist: list[int] = []
    error_emoji: str = 'pikalaOwO'
    exc_channel: int = EXC_CHANNEL_ID
    banned_guilds: list[int] = []
    database: dict[str, str] = {
        'username': 'root',
        'password': 'raspberrypi',
        'host': 'localhost',
        'dbname': 'pikalaxbot'
    }
    json_keys = 'token', 'prefix', 'markov_channels', 'debug', 'disabled_commands', 'disabled_cogs', 'help_name', \
                'game', 'espeak_kw', 'banlist', 'error_emoji', 'exc_channel', 'banned_guilds', 'database'

    def __init__(self, fname='settings.json'):
        self._fname = fname
        self.__loop = None
        self._changed = False
        self._lock = asyncio.Lock()
        try:
            with open(fname) as fp:
                self.update(json.load(fp))
        except FileNotFoundError:
            print('Creating new configuration')
            with open(fname, 'w') as fp:
                json.dump(self, fp, indent=4, separators=(', ', ': '))
        if self.token is None:
            raise ValueError(f'Please set your bot\'s token in {fname}')
        self._mtime = os.path.getmtime(fname)

    def update(self, data: dict[str, typing.Any]):
        for key, value in data.items():
            setattr(self, key, value)

    @property
    def _loop(self):
        if self.__loop is None:
            self.__loop = asyncio.get_running_loop()
        return self.__loop

    def __enter__(self):
        if os.path.getmtime(self._fname) > self._mtime:
            with self._fname as fp:
                data = json.load(fp)
            self.update(data)
            self._mtime = os.path.getmtime(self._fname)
        return self

    async def __aenter__(self):
        await self._lock.acquire()
        await self._loop.run_in_executor(None, self.__enter__)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._changed:
            data = {key: getattr(self, key) for key in self.json_keys}
            with open(self._fname, 'w') as fp:
                json.dump(data, fp, indent=4)
            self._changed = False
            self._mtime = os.path.getmtime(self._fname)

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        try:
            self._loop.run_in_executor(None, self.__exit__, exc_type, exc_val, exc_tb)
        finally:
            self._lock.release()

    def __setattr__(self, key, value):
        super().__setattr__(key, value)
        if key in self.json_keys:
            super().__setattr__('_changed', True)
