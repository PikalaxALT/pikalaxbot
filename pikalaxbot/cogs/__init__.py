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

import collections
import asyncio
import inspect
from typing import Optional
from contextlib import asynccontextmanager as acm, AbstractAsyncContextManager as Aacm

import discord
from discord.ext import commands, tasks
from ..utils.logging_mixin import LoggingMixin
from .. import *
from ..utils.pg_orm import BaseTable

from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession


__all__ = ('BaseCog', 'PikalaxBOT', 'MyContext', 'BaseTable')


def _cog_special_method(func):
    func.__cog_special_method__ = None
    return func


class BaseCog(LoggingMixin, commands.Cog):
    """
    Base class for all cog files.  Inherits :class:LoggingMixin

    __init__ params:
        bot: PikalaxBOT - The instance of the bot.

    Class Attributes:
        config_attrs: tuple - Names of attributes to fetch from the bot's
        settings.  When subclassing BaseCog, define this at the class level.
    """
    config_attrs: tuple[str] = tuple()
    __abstract__ = True

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if not cls.__dict__.get('__abstract__', False):
            module = inspect.getmodule(cls)

            def setup(bot: PikalaxBOT):
                bot.add_cog(cls(bot))

            module.__dict__.setdefault('setup', setup)

    def __init__(self, bot: PikalaxBOT):
        super().__init__()
        self.bot = bot
        self._sql_session = AsyncSession(self.bot.engine, expire_on_commit=False)
        self._dirty = False
        self._txn_lock = asyncio.Lock()
        self._ready = asyncio.Event()
        # Use bot.loop explicitly because it might not be running yet
        # such as when the bot is first started. Avoids RuntimeError.

        if not self.__class__.__dict__.get('__abstract__', False):
            module = inspect.getmodule(self.__class__)
            self.__tables__: tuple[type[BaseTable]] = module.__dict__.get('__tables__', ())

            bot.loop.create_task(self.prepare())

            self.__loops__ = [
                getattr(self, key)
                for key, value in self.__class__.__dict__.items()
                if isinstance(value, tasks.Loop)
            ]

    @property
    def sql(self):
        return self.bot.sql

    @property
    def sql_session(self) -> Aacm[AsyncSession]:
        @acm
        async def begin():
            async with self._txn_lock:
                async with self._sql_session.begin():
                    yield self._sql_session

        return begin()

    async def wait_until_ready(self):
        await asyncio.wait({self._ready.wait(), self.bot.wait_until_ready()})

    async def init_db(self, sql: AsyncConnection):
        for table in self.__tables__:
            await table.create(sql)

    def cog_unload(self):
        for loop in self.__loops__:
            loop.cancel()
        for table in reversed(self.__tables__):
            table.unlink()

    async def fetch(self):
        """
        Loads local attributes from the bot's settings
        """
        self.log_debug('Fetching %s', self.__class__.__name__)
        async with self.bot.settings:
            for attr in self.config_attrs:
                self.log_debug(attr)
                try:
                    val = getattr(self.bot.settings, attr)
                except AttributeError:
                    continue
                if isinstance(val, list):
                    val = set(val)
                old_attr = getattr(self, attr)
                if isinstance(old_attr, collections.defaultdict):
                    old_attr.clear()
                    old_attr.update(val)
                    val = old_attr
                setattr(self, attr, val)

    async def prepare_once(self):
        if self.__tables__:
            self.bot.dispatch('cog_db_init', self)
            try:
                async with self.sql as sql:  # type: AsyncConnection
                    await self.init_db(sql)
            except Exception as e:
                e.__suppress_context__ = True
                self.bot.dispatch('cog_db_init_error', self, e)
            else:
                self.bot.dispatch('cog_db_init_complete', self)
        for loop in self.__loops__:
            loop.start()
        self._ready.set()

    async def prepare(self):
        """Async init"""
        await self.fetch()
        try:
            _ = self.__prepared
        except AttributeError:
            await self.prepare_once()
            self.__prepared = True

    async def cog_before_invoke(self, ctx):
        await self.prepare()

    async def commit(self):
        """
        Commits local attributes to the bot's settings file
        """
        async with self.bot.settings as settings:
            for attr in self.config_attrs:
                self.log_debug(attr)
                val = getattr(self, attr)
                if isinstance(val, set):
                    val = list(val)
                setattr(settings, attr, val)

    def __setattr__(self, key, value):
        super().__setattr__(key, value)
        if key in self.config_attrs:
            super().__setattr__('_dirty', True)

    async def cog_after_invoke(self, ctx: MyContext):
        if self._dirty:
            await self.commit()

    @_cog_special_method
    async def send_tb(self, ctx: Optional[MyContext], error: BaseException, *, origin: str = None, embed: discord.Embed = None):
        await self.bot.get_cog('ErrorHandling').send_tb(ctx, error, origin=origin, embed=embed)
