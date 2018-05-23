import asyncio
import discord
from discord.ext import commands
from utils import sql


class Leaderboard:
    def __init__(self, bot):
        self.bot = bot

    @commands.group(pass_context=True, case_insensitive=True)
    async def leaderboard(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await ctx.invoke(self.check)

    @leaderboard.command()
    async def check(self, ctx, username=None):
        if username is None:
            person = ctx.author
        else:
            username = username.lower()
            for person in self.bot.get_all_members():
                if username in (person.name.lower(), person.mention.lower(), person.display_name.lower()):
                    break
            else:
                await ctx.send(f'{ctx.author.mention}: User {username} not found.')
                return  # bail early
        score = sql.get_score(person)
        if score is not None:
            await ctx.send(f'{person.name} has {score:d} point(s) across all games.')
        else:
            await ctx.send(f'{person.name} is not yet on the leaderboard.')

    @leaderboard.command()
    async def show(self, ctx):
        msgs = []
        for _id, name, score in sql.get_all_scores():
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
