# PikalaxBOT - A Discord bot in discord.py
# Copyright (C) 2018-2021  PikalaxALT
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
from types import TracebackType

__all__ = ('Settings',)


class Settings:
    token: str = None
    prefix = 'p!'
    markov_channels: list[int] = []
    debug = False
    disabled_commands: list[str] = []
    disabled_cogs: list[str] = []
    help_name = 'help'
    game = 'Q20, Anagram, Hangman'
    espeak_kw = {
        'a': 100,
        's': 150,
        'v': 'en-us+f3',
        'p': 75,
        'g': 1,
        'k': 2,
    }
    banlist: list[int] = []
    error_emoji = 'pikalaOwO'
    exc_channel = EXC_CHANNEL_ID
    banned_guilds: list[int] = []
    database = {
        'username': 'root',
        'password': 'raspberrypi',
        'host': 'localhost',
        'dbname': 'pikalaxbot'
    }
    e6_api_auth = {
        'login': '',
        'api_key': ''
    }
    json_keys = 'token', 'prefix', 'markov_channels', 'debug', 'disabled_commands', 'disabled_cogs', 'help_name', \
                'game', 'espeak_kw', 'banlist', 'error_emoji', 'exc_channel', 'banned_guilds', 'database', 'e6_api_auth'

    def __init__(self, fname='settings.json'):
        self._fname = fname
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
        self._changed = False

    def update(self, data: dict[str, ...]):
        for key, value in data.items():
            setattr(self, key, value)

    def __enter__(self):
        if os.path.getmtime(self._fname) > self._mtime:
            with open(self._fname) as fp:
                data = json.load(fp)
            self.update(data)
            self._mtime = os.path.getmtime(self._fname)
        return self

    async def __aenter__(self):
        await self._lock.acquire()
        return await asyncio.to_thread(self.__enter__)

    def __exit__(self, exc_type: typing.Type[BaseException], exc_val: BaseException, exc_tb: TracebackType):
        if self._changed:
            data = {key: getattr(self, key) for key in self.json_keys}
            with open(self._fname, 'w') as fp:
                json.dump(data, fp, indent=4)
            self._changed = False
            self._mtime = os.path.getmtime(self._fname)

    async def __aexit__(self, exc_type: typing.Type[BaseException], exc_val: BaseException, exc_tb: TracebackType):
        try:
            await asyncio.to_thread(self.__exit__, exc_type, exc_val, exc_tb)
        finally:
            self._lock.release()

    def __setattr__(self, key: str, value):
        super().__setattr__(key, value)
        if key in self.json_keys:
            super().__setattr__('_changed', True)
