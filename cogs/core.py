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
from cogs import Cog
from discord.ext import commands


class Core(Cog):
    disabled_commands = set()
    banlist = set()
    game = '!pikakill'
    config_attrs = 'disabled_commands', 'banlist', 'game'

    async def __global_check(self, ctx: commands.Context):
        if not self.bot.is_ready():
            return False
        if ctx.author.bot:
            return False
        if isinstance(ctx.command, commands.Command):
            if ctx.author == self.bot.user:
                return True
            if ctx.command.name in self.disabled_commands:
                return False
        if ctx.author.id in self.banlist:
            return False
        return ctx.channel.permissions_for(ctx.me).send_messages

    @commands.command(aliases=['pikareboot'])
    @commands.is_owner()
    async def pikakill(self, ctx: commands.Context):
        """Shut down the bot (owner only, manual restart required)"""
        await ctx.send('Rebooting to apply updates')
        await self.bot.close()

    @commands.command()
    @commands.is_owner()
    async def ignore(self, ctx, person: discord.Member):
        """Ban a member :datsheffy:"""
        self.banlist.add(person.id)
        await ctx.send(f'{person.display_name} is now banned from interacting with me.')

    @commands.command()
    @commands.is_owner()
    async def unignore(self, ctx, person: discord.Member):
        """Unban a member"""
        self.banlist.discard(person.id)
        await ctx.send(f'{person.display_name} is no longer banned from interacting with me.')

    async def on_ready(self):
        activity = discord.Game(self.game)
        await self.bot.change_presence(activity=activity)


def setup(bot):
    bot.add_cog(Core(bot))
