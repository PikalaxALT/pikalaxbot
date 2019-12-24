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

from collections import defaultdict

import discord
from discord.ext import commands

from . import BaseCog


class MemberWatchError(commands.CommandError):
    pass


class MemberWatch(BaseCog):
    config_attrs = 'watches',

    def __init__(self, bot):
        super().__init__(bot)
        self.watches = defaultdict(dict)

    @commands.group()
    async def watch(self, ctx: commands.Context):
        """Commands to manage member watches"""

    @watch.command(name='add')
    async def add_watch(self, ctx: commands.Context, user: discord.User):
        self.watches = defaultdict(dict, **self.watches)
        if user.id in self.watches[ctx.guild.id]:
            raise MemberWatchError(f'Already watching {user}')
        self.watches[ctx.guild.id][user.id] = ctx.channel.id
        await ctx.send(f'Added a watch for {user} in this channel.')

    @watch.command(name='del')
    async def del_watch(self, ctx: commands.Context, user: discord.User):
        self.watches = defaultdict(dict, **self.watches)
        if user in self.watches[ctx.guild.id]:
            self.watches[ctx.guild.id].pop(user.id)
            await ctx.send(f'Removed the watch for {user} in this channel.')
        else:
            raise MemberWatchError(f'Not watching {user}')

    async def cog_command_error(self, ctx: commands.Context, exc: Exception):
        if isinstance(exc, MemberWatchError):
            await ctx.send(exc)
        else:
            self.log_tb(ctx, exc)

    @commands.Cog.listener()
    async def on_member_add(self, member: discord.Member):
        if member.id in self.watches[member.guild.id]:
            channel = member.guild.get_channel(self.watches[member.guild.id])
            await channel.send(f'{member} has joined the server. Resume normal activities.')

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        if member.id in self.watches[member.guild.id]:
            channel = member.guild.get_channel(self.watches[member.guild.id])
            await channel.send(f'@everyone {member} has left the server. Panic mode!')


def setup(bot):
    bot.add_cog(MemberWatch(bot))
