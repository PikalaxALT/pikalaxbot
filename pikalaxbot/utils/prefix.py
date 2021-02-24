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
from ..bot import PikalaxBOT
from ..context import MyContext
import typing
import asyncstdlib.functools as afunctools
from ..constants import DPY_GUILD_ID
from .pg_orm import *

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import Column, BIGINT, TEXT


__all__ = ('command_prefix', 'set_guild_prefix', 'Prefixes')


class Prefixes(BaseTable):
    guild = Column(BIGINT, nullable=False, primary_key=True)
    prefix = Column(TEXT, nullable=False)


@afunctools.cache
async def _guild_prefix(bot: PikalaxBOT, guild: typing.Optional[discord.Guild]) -> str:
    if guild is None:
        return ''
    async with bot.sql_session as sess:  # type: AsyncSession
        pre = await sess.get(Prefixes, guild.id)
    return pre and pre.prefix or bot.settings.prefix


@afunctools.cache
async def is_owner_in_dpy_guild(bot: PikalaxBOT, guild: typing.Optional[discord.Guild], author: discord.abc.User):
    return guild and guild.id == DPY_GUILD_ID and await bot.is_owner(author)


async def command_prefix(bot: PikalaxBOT, message: discord.Message) -> tuple[str]:
    prefix = await _guild_prefix(bot, message.guild)
    use_blank = await is_owner_in_dpy_guild(bot, message.guild, message.author)
    return (prefix, '') if use_blank else (prefix,)


async def set_guild_prefix(ctx: MyContext, prefix: str):
    async with ctx.bot.sql_session as sess:  # type: AsyncSession
        pre = await sess.get(Prefixes, ctx.guild.id)
        pre.prefix = prefix
    _guild_prefix.cache_clear()
