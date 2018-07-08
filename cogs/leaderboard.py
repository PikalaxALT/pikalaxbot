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
from discord.ext import commands
from utils import sql
from utils.default_cog import Cog


class Leaderboard(Cog):
    @commands.group(case_insensitive=True)
    async def leaderboard(self, ctx: commands.Context):
        """Commands to check the leaderboard"""
        if ctx.invoked_subcommand is None:
            await ctx.invoke(self.check)

    @leaderboard.command()
    async def check(self, ctx, person: discord.Member = None):
        """Check your leaderboard score, or the leaderboard score of another user"""
        if person is None:
            person = ctx.author
        score = await sql.get_score(person)
        if score is not None:
            rank = await sql.get_leaderboard_rank(person)
            await ctx.send(f'{person.name} has {score:d} point(s) across all games and is #{rank:d} on the leaderboard.')
        else:
            await ctx.send(f'{person.name} is not yet on the leaderboard.')

    @leaderboard.command()
    async def show(self, ctx):
        """Check the top 10 players on the leaderboard"""
        msgs = []
        for _id, name, score in await sql.get_all_scores():
            msgs.append(f'{name}: {score:d}')
        if len(msgs) == 0:
            await ctx.send('The leaderboard is empty. Play some games to get your name up there!')
        else:
            msg = '\n'.join(msgs)
            await ctx.send(f'Leaderboard:\n'
                           f'```\n'
                           f'{msg}\n'
                           f'```')


def setup(bot):
    bot.add_cog(Leaderboard(bot))
