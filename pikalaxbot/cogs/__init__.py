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
from pikalaxbot.utils.logging_mixin import LoggingMixin
from .. import PikalaxBOT


__all__ = ('BaseCog',)


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

        async def do_db_init():
            bot.dispatch('cog_db_init', self)
            try:
                async with self.bot.sql as sql:
                    await self.init_db(sql)
            except Exception as e:
                bot.dispatch('cog_db_init_error', self, e)
            else:
                bot.dispatch('cog_db_init_complete', self)

        if BaseCog._get_overridden_method(self.init_db) is not None:
            bot.loop.create_task(do_db_init())

    @_cog_special_method
    async def init_db(self, sql: asyncpg.Connection):
        """Override this"""
        pass

    async def fetch(self):
        """
        Loads local attributes from the bot's settings
        """
        self.log_debug(f'Fetching {self.__class__.__name__}')
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

    async def cog_before_invoke(self, ctx):
        await self.bot.pokeapi
        try:
            await self.fetch()
        except Exception as e:
            await self.bot.send_tb(ctx, e, ignoring=f'Ignoring exception in {self}.cog_before_invoke:')

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

    async def cog_after_invoke(self, ctx):
        try:
            await self.commit()
        except Exception as e:
            await self.bot.send_tb(ctx, e, ignoring=f'Ignoring exception in {self}.cog_after_invoke:')
