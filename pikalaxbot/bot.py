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
from discord.ext import commands, menus
import typing
import os
import asyncpg
import aiohttp
import asyncio
import datetime
import traceback
from .utils.logging_mixin import BotLogger
from .context import MyContext, FakeContext
from .utils.config_io import Settings
import asyncstdlib.functools as afunctools
from .pokeapi import *


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
        self.guild_prefixes: dict[int, str] = {}
        self._sql = 'postgres://{username}:{password}@{host}/{dbname}'.format(**self.settings.database)

        async def init_client_session():
            self.client_session = aiohttp.ClientSession(raise_for_status=True)
            try:
                self._pool = await asyncpg.create_pool(self._sql)
            except Exception:
                await self.client_session.close()
                raise

        self.log_info('Creating aiohttp session and connecting database')
        self.client_session: typing.Optional[aiohttp.ClientSession] = None
        self._pool: typing.Optional[asyncpg.pool.Pool] = None
        self.loop.run_until_complete(init_client_session())

        # Reboot handler
        self.reboot_after = True

        # Uptime
        self._alive_since: typing.Optional[datetime.datetime] = None

        # PokeAPI
        self._pokeapi: typing.Optional[PokeApi]
        if pokeapi_file:
            self._pokeapi = PokeApi(
                pokeapi_file,
                factory=PokeApiConnection,
                uri=True
            )
        else:
            self._pokeapi = None

    @property
    def exc_channel(self) -> typing.Optional[discord.TextChannel]:
        try:
            return self.get_channel(self.settings.exc_channel)
        except AttributeError:
            return None

    @property
    def command_error_emoji(self) -> discord.Emoji:
        return discord.utils.get(self.emojis, name=self.settings.error_emoji)

    @property
    def sql(self):
        return self._pool.acquire()

    @property
    def pokeapi(self) -> PokeApi:
        return self._pokeapi

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

    async def send_tb(
            self,
            ctx: typing.Optional[MyContext],
            exc: BaseException,
            *,
            origin: typing.Optional[str] = None,
            embed: typing.Optional[discord.Embed] = None
    ):
        msg = f'Ignoring exception in {origin}' if origin is not None else ''
        channel = self.exc_channel
        if channel is None:
            return
        if ctx is None:
            owner = await self.get_owner()
            if isinstance(owner, set):
                owner = owner.pop()
            ctx = FakeContext(channel.guild, channel, None, owner, self)
        elif embed is None:
            embed = ctx.prepare_command_error_embed()
        paginator = commands.Paginator()
        msg and paginator.add_line(msg)
        for line in traceback.format_exception(exc.__class__, exc, exc.__traceback__):
            paginator.add_line(line.rstrip('\n'))
        self.log_error(msg, exc_info=(exc.__class__, exc, exc.__traceback__))

        class TracebackPageSource(menus.ListPageSource):
            def format_page(self, menu: menus.MenuPages, page: str):
                return {'content': page, 'embed': embed}

        menu_ = menus.MenuPages(TracebackPageSource(paginator.pages, per_page=1))
        await menu_.start(ctx, channel=channel)

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
            await self.client_session.close()
            await self._pool.close()

    async def on_ready(self):
        self.log_info('Logged in as %s', self.user)

    async def get_context(self, message, *, cls=None) -> MyContext:
        ctx: MyContext = await super().get_context(message, cls=cls or MyContext)
        self._ctx_cache[(message.channel.id, message.id)] = [ctx, set()]
        return ctx
