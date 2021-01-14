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

import typing
import collections
import asyncpg

from discord.ext import commands
from ..utils.logging_mixin import LoggingMixin
from .. import *


__all__ = ('BaseCog', 'PikalaxBOT', 'MyContext')


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
    config_attrs: typing.Tuple[str] = tuple()

    def __init__(self, bot: PikalaxBOT):
        super().__init__()
        self.bot = bot
        self._dirty = False
        bot.loop.create_task(self.prepare())

    @_cog_special_method
    async def init_db(self, sql: asyncpg.Connection):
        """Override this"""
        pass

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
        if BaseCog._get_overridden_method(self.init_db) is not None:
            async with self.bot.sql as sql:
                await self.init_db(sql)

    async def prepare(self):
        """Async init"""
        try:
            _ = self.__prepared
        except AttributeError:
            await self.prepare_once()
            self.__prepared = True
        await self.fetch()

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
