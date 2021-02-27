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

import discord
from discord.ext import commands
import typing
import os
import aiohttp
import asyncio
import datetime
from .utils.logging_mixin import BotLogger
from .context import MyContext
from .utils.config_io import Settings
import asyncstdlib.functools as afunctools
from .pokeapi import methods, PokeapiModel
import asqlite3
from .utils.pg_orm import *
from contextlib import asynccontextmanager as acm

from sqlalchemy.ext.asyncio import AsyncSession


__all__ = ('PikalaxBOT',)


class PikalaxBOT(BotLogger, commands.Bot):
    def __init__(
            self,
            *,
            settings_file: typing.Union[str, os.PathLike],
            pokeapi_file: typing.Union[str, os.PathLike] = None,
            **kwargs
    ):
        # Load settings
        self.settings = Settings(settings_file)
        super().__init__(activity=discord.Game(self.settings.game), **kwargs)
        self._ctx_cache: dict[tuple[int, int], list[MyContext, set[int]]] = {}

        self.log_info('Connecting database')
        self.engine = async_engine_parameterized(**self.settings.database)
        self._sql_session = AsyncSession(self.engine, expire_on_commit=False)

        # Reboot handler
        self.reboot_after = True

        # Uptime
        self._alive_since: typing.Optional[datetime.datetime] = None

        # PokeAPI
        self._pokeapi_file = pokeapi_file
        self._pokeapi: typing.Optional[asqlite3.Connection] = self.loop.run_until_complete(methods.make_pokeapi(self))

    @property
    def command_error_emoji(self) -> discord.Emoji:
        return discord.utils.get(self.emojis, name=self.settings.error_emoji)

    @property
    def sql(self):
        return self.engine.begin()

    @property
    def sql_session(self):
        @acm
        async def begin():
            while self._sql_session.in_transaction():
                await asyncio.sleep(0)
            async with self._sql_session.begin():
                yield self._sql_session

        return begin()

    @property
    def pokeapi(self) -> typing.Optional[asqlite3.Connection]:
        return self._pokeapi

    @pokeapi.setter
    def pokeapi(self, value: typing.Optional[asqlite3.Connection]):
        self._pokeapi = value
        PokeapiModel.__prepared__ = False

    @discord.utils.cached_slot_property('_client_session')
    def client_session(self):
        return aiohttp.ClientSession(raise_for_status=True)

    @afunctools.cache
    async def get_owner(self) -> typing.Union[discord.User, set[discord.TeamMember], None]:
        if self.owner_id is not None:
            return self.get_user(self.owner_id)
        elif self.owner_ids:
            return {self.get_user(owner_id) for owner_id in self.owner_ids}
        else:
            app = await self.application_info()
            if app.team:
                self.owner_ids = {m.id for m in app.team.members}
                return set(app.team.members)
            else:
                self.owner_id = app.owner.id
                return app.owner

    def run(self, *args, **kwargs):
        self.log_info('Starting bot')
        token = self.settings.token
        super().run(token, *args, **kwargs)

    async def close(self):
        self.log_info('Logout request receeived')
        await asyncio.gather(*(client.disconnect(force=True) for client in self.voice_clients), return_exceptions=True)
        try:
            await super().close()
        finally:
            try:
                await self._client_session.close()
            except AttributeError:
                pass
            if self._pokeapi:
                await self._pokeapi.close()

    async def on_ready(self):
        self.log_info('Logged in as %s', self.user)

    async def get_context(self, message, *, cls=None) -> MyContext:
        ctx: MyContext = await super().get_context(message, cls=cls or MyContext)
        self._ctx_cache[(message.channel.id, message.id)] = [ctx, set()]
        return ctx
