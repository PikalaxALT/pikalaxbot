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
from .utils.game import Game


class Leaderboard(BaseCog):
    """Commands for viewing and managing the shared leaderboard for games."""

    @commands.group(case_insensitive=True)
    async def leaderboard(self, ctx: MyContext):
        """Commands to check the leaderboard"""
        if ctx.invoked_subcommand is None:
            await self.check(ctx)

    @leaderboard.command()
    async def check(self, ctx: MyContext, *, person: discord.Member = None):
        """Check your leaderboard score, or the leaderboard score of another user"""
        person = person or ctx.author

        async with self.bot.sql as sql:
            try:
                score, rank = await Game.check_score(sql, person)
            except TypeError:
                msg = f'{person.name} is not yet on the leaderboard.'
            else:
                msg = f'{person.name} has {score:d} point(s) across all games ' \
                      f'and is #{rank:d} on the leaderboard.'
        await ctx.send(msg)

    @leaderboard.command()
    async def show(self, ctx: MyContext):
        """Check the top 10 players on the leaderboard"""
        async with self.bot.sql as sql:
            msg = '\n'.join(
                '{0}: {1:d}'.format(self.bot.get_user(id_), score) for id_, score in await Game.check_all_scores(sql)
            ) or 'Wumpus: 0'
        await ctx.send(f'Leaderboard:\n'
                       f'```\n'
                       f'{msg}\n'
                       f'```')

    @leaderboard.command(name='clear')
    @commands.is_owner()
    async def clear_leaderboard(self, ctx: MyContext):
        """Reset the leaderboard"""
        async with self.bot.sql as sql:
            await Game.clear(sql)
        await ctx.send('Leaderboard reset')

    @leaderboard.command(name='give')
    @commands.is_owner()
    async def give_points(self, ctx: MyContext, person: discord.Member, score: int):
        """Give points to a player"""
        async with self.bot.sql as sql:
            await Game.increment_score(sql, person, by=score)
        await ctx.send(f'Gave {score:d} points to {person.name}')


def setup(bot: PikalaxBOT):
    bot.add_cog(Leaderboard(bot))
