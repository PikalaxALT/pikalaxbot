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
import discord
from discord.ext import commands
import logging
from io import StringIO
import aiohttp
import os
import asyncpg
import typing
import pygit2
import collections
from .utils.hastebin import mystbin
from .utils.config_io import Settings
from .utils.logging_mixin import LoggingMixin
if typing.TYPE_CHECKING:
    from .ext.pokeapi import PokeApi

__dirname__ = os.path.dirname(__file__) or '.'

__version__ = '0.2.0a'

if __version__.endswith(('a', 'b', 'rc')):
    try:
        repo = pygit2.Repository(os.path.join(os.path.dirname(__dirname__), '.git'))
    except pygit2.GitError:
        pass
    else:
        __version__ += f'{sum(1 for _ in repo.walk(repo.head.target))}+g{repo.head.target.hex[:7]}'


__all__ = ('PikalaxBOT',)


class PikalaxBOT(LoggingMixin, commands.Bot):
    def __init__(self, settings_file, logfile, **kwargs):
        # Load settings
        loop = kwargs.pop('loop', None) or asyncio.get_event_loop()
        log_level = kwargs.pop('log_level', logging.NOTSET)
        self.settings = Settings(settings_file, loop=loop)
        super().__init__(
            activity=discord.Game(self.settings.game),
            loop=loop,
            **kwargs
        )
        self.guild_prefixes = {}
        self._sql = 'postgres://{username}:{password}@{host}/{dbname}'.format(**self.settings.database)

        # Set up logger
        self.logger.setLevel(log_level)
        handler = logging.FileHandler(logfile, mode='w')
        fmt = logging.Formatter('%(asctime)s (PID:%(process)s) - %(levelname)s - %(message)s')
        handler.setFormatter(fmt)
        self.logger.addHandler(handler)

        async def init_client_session():
            self.client_session = aiohttp.ClientSession()
            try:
                self._pool = await asyncpg.create_pool(self._sql)
            except Exception:
                await self.client_session.close()
                raise

        self.log_info('Creating aiohttp session')
        self.client_session: typing.Optional[aiohttp.ClientSession] = None
        self._pool: typing.Optional[asyncpg.pool.Pool] = None
        self.loop.run_until_complete(init_client_session())

        # Reboot handler
        self.reboot_after = True

        self._alive_since = None
        self._pokeapi_factory: typing.Optional[typing.Callable[[], 'PokeApi']] = None
        self._pokeapi: typing.Optional['PokeApi'] = None

    @property
    def exc_channel(self):
        try:
            return self.get_channel(self.settings.exc_channel)
        except AttributeError:
            return None

    @property
    def command_error_emoji(self):
        return discord.utils.get(self.emojis, name=self.settings.error_emoji)

    @property
    def sql(self) -> asyncpg.Connection:
        return self._pool.acquire()

    @property
    def pokeapi(self) -> typing.Optional['PokeApi']:
        return self._pokeapi

    @pokeapi.setter
    def pokeapi(self, value: 'PokeApi'):
        old_value = self._pokeapi
        close_task = None
        if old_value and old_value._running:
            close_task = self.loop.create_task(old_value.close())
        if value is not None:
            value.start()
            async def connect():
                if close_task:
                    await close_task
                await value._connect()
            self.loop.create_task(connect())
        self._pokeapi = value

    async def send_tb(self, tb, embed=None):
        channel = self.exc_channel
        client_session = self.client_session
        if channel is None:
            return
        if len(tb) < 1990:
            await channel.send(f'```{tb}```', embed=embed)
        else:
            try:
                url = await mystbin(tb, cs=client_session)
            except aiohttp.ClientResponseError:
                await channel.send('An error has occurred', file=discord.File(StringIO(tb)), embed=embed)
            else:
                await channel.send(f'An error has occurred: {url}', embed=embed)

    def run(self):
        self.log_info('Starting bot')
        token = self.settings.token
        super().run(token)

    async def close(self):
        self.log_info('Logout request receeived')
        await asyncio.gather(*(client.disconnect(force=True) for client in self.voice_clients), return_exceptions=True)
        try:
            await super().close()
        finally:
            await self.client_session.close()
            await self._pool.close()

    async def on_ready(self):
        self.log_info(f'Logged in as {self.user}')
