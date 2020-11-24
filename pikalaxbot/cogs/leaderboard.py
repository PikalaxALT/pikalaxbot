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

import discord
from discord.ext import commands

from . import BaseCog
from .utils.game import increment_score


class Leaderboard(BaseCog):
    """Commands for viewing and managing the shared leaderboard for games."""

    @commands.group(case_insensitive=True)
    async def leaderboard(self, ctx: commands.Context):
        """Commands to check the leaderboard"""
        if ctx.invoked_subcommand is None:
            await self.check(ctx)

    @leaderboard.command()
    async def check(self, ctx, person: discord.Member = None):
        """Check your leaderboard score, or the leaderboard score of another user"""
        person = person or ctx.author

        async with self.bot.sql as sql:
            for score, rank in await sql.fetch('select score, rank () over (order by score desc) ranking from game where id = $1', person.id):
                msg = f'{person.name} has {score:d} point(s) across all games ' \
                      f'and is #{rank:d} on the leaderboard.'
                break
            else:
                msg = f'{person.name} is not yet on the leaderboard.'
        await ctx.send(msg)

    @leaderboard.command()
    async def show(self, ctx):
        """Check the top 10 players on the leaderboard"""
        async with self.bot.sql as sql:
            msgs = [f'{name}: {score:d}' for _id, name, score in await sql.fetch('select * from game order by score desc limit 10')] or ['Wumpus: 0']
        msg = '\n'.join(msgs)
        await ctx.send(f'Leaderboard:\n'
                       f'```\n'
                       f'{msg}\n'
                       f'```')

    @leaderboard.command(name='clear')
    @commands.is_owner()
    async def clear_leaderboard(self, ctx):
        """Reset the leaderboard"""
        async with self.bot.sql as sql:
            await sql.execute('delete from game')
            await sql.execute('vacuum')
        await ctx.send('Leaderboard reset')

    @leaderboard.command(name='give')
    @commands.is_owner()
    async def give_points(self, ctx, person: discord.Member, score: int):
        """Give points to a player"""
        async with self.bot.sql as sql:
            await increment_score(sql, person, by=score)
        await ctx.send(f'Gave {score:d} points to {person.name}')


def setup(bot):
    bot.add_cog(Leaderboard(bot))
