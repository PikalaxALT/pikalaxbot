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

from cogs import BaseCog


class Leaderboard(BaseCog):
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
        async with self.bot.sql as sql:
            try:
                score, rank = await sql.get_leaderboard_rank(person)
                await ctx.send(f'{person.name} has {score:d} point(s) across all games '
                               f'and is #{rank:d} on the leaderboard.')
            except TypeError:
                await ctx.send(f'{person.name} is not yet on the leaderboard.')

    @leaderboard.command()
    async def show(self, ctx):
        """Check the top 10 players on the leaderboard"""
        msgs = []
        async with self.bot.sql as sql:
            async for _id, name, score in sql.get_all_scores():
                msgs.append(f'{name}: {score:d}')
        if len(msgs) == 0:
            await ctx.send('The leaderboard is empty. Play some games to get your name up there!')
        else:
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
            await sql.reset_leaderboard()
        await ctx.send('Leaderboard reset')

    @leaderboard.command(name='give')
    @commands.is_owner()
    async def give_points(self, ctx, person: discord.Member, score: int):
        """Give points to a player"""
        if person is None:
            await ctx.send('That person does not exist')
        else:
            async with self.bot.sql as sql:
                await sql.increment_score(person, score)
            await ctx.send(f'Gave {score:d} points to {person.name}')
    #
    # @commands.group()
    # @commands.is_owner()
    # async def database(self, ctx):
    #     """Commands for managing the database file"""
    #
    # @database.command(name='backup')
    # async def backup_database(self, ctx):
    #     """Back up the database"""
    #     async with self.bot.sql as sql:
    #         fname = await sql.backup_db()
    #     await ctx.send(f'Backed up to {fname}')
    #
    # @database.command(name='restore')
    # async def restore_database(self, ctx, *, idx: int = -1):
    #     """Restore the database"""
    #     async with self.bot.sql as sql:
    #         dbbak = await sql.restore_db(idx)
    #     if dbbak is None:
    #         await ctx.send('Unable to restore backup')
    #     else:
    #         await ctx.send(f'Restored backup from {dbbak}')


def setup(bot):
    bot.add_cog(Leaderboard(bot))
