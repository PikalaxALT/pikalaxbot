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
from . import *
import contextlib


@contextlib.asynccontextmanager
async def transform_context(ctx: MyContext, user: discord.Member, content: str):
    old_content = ctx.message.content
    old_author = ctx.author
    ctx.message.author = user
    prefix, *_ = await ctx.bot.get_prefix(ctx.message)
    ctx.message.content = prefix + content
    yield ctx.message
    ctx.message.content = old_content
    ctx.message.author = old_author


class Sudo(BaseCog):
    """Commands for executing a command as someone else."""

    @commands.is_owner()
    @commands.command()
    async def su(self, ctx: MyContext, user: discord.Member, *, content: str):
        """Run as someone else"""
        try:
            async with transform_context(ctx, user, content) as message:  # type: discord.Message
                await self.bot.process_commands(message)
        except commands.CommandError:
            pass
