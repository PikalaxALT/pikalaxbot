import asyncio
import discord
from discord.ext import commands
from utils import sql
from utils.default_cog import Cog


class Leaderboard(Cog):
    @commands.group(pass_context=True, case_insensitive=True)
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
