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
import asyncpg
import asyncstdlib.functools as afunctools


__all__ = ('command_prefix', 'set_guild_prefix')


@afunctools.cache
async def _guild_prefix(bot: PikalaxBOT, guild: typing.Optional[discord.Guild]) -> typing.Union[str, list[str]]:
    if guild is None:
        return ''
    async with bot.sql as sql:  # type: asyncpg.Connection
        prefix = await sql.fetchval(
            'select prefix '
            'from prefixes '
            'where guild = $1',
            guild.id
        )
    return prefix or bot.settings.prefix


def command_prefix(bot: PikalaxBOT, message: discord.Message):
    return _guild_prefix(bot, message.guild)


async def set_guild_prefix(ctx: MyContext, prefix: str):
    async with ctx.bot.sql as sql:  # type: asyncpg.Connection
        async with sql.transaction():
            await sql.execute(
                'insert into prefixes '
                'values ($1, $2) '
                'on conflict (guild) '
                'do update '
                'set prefix = $2',
                ctx.guild.id,
                prefix
            )
    _guild_prefix.cache_clear()
