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

from discord.ext import commands
from cogs import BaseCog
from utils.game import find_emoji


class Bag(BaseCog):
    @commands.group()
    async def bag(self, ctx):
        """Get in the bag, Nebby."""
        if ctx.invoked_subcommand is None:
            async with self.bot.sql as sql:
                message = await sql.read_bag()
            if message is None:
                emoji = find_emoji(ctx.bot, 'BibleThump', case_sensitive=False)
                await ctx.send(f'*cannot find the bag {emoji}*')
            else:
                await ctx.send(f'*{message}*')

    @bag.command()
    async def add(self, ctx, *, fmtstr):
        """Add a message to the bag."""
        async with self.bot.sql as sql:
            res = await sql.add_bag(fmtstr)
        if res:
            await ctx.send('Message was successfully placed in the bag')
        else:
            await ctx.send('That message is already in the bag')

    @bag.command(name='remove')
    @commands.is_owner()
    async def remove_bag(self, ctx, *, msg):
        """Remove a phrase from the bag"""
        async with self.bot.sql as sql:
            res = await sql.remove_bag(msg)
        if res:
            await ctx.send('Removed message from bag')
        else:
            await ctx.send('Cannot remove default message from bag')

    @bag.command(name='reset')
    @commands.is_owner()
    async def reset_bag(self, ctx):
        """Reset the bag"""
        async with self.bot.sql as sql:
            await sql.reset_bag()
        await ctx.send('Reset the bag')


def setup(bot):
    bot.add_cog(Bag(bot))
