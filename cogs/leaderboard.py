import asyncio
import discord
from discord.ext import commands
from bot import bot, PikalaxBOT
from utils import sql


class Leaderboard:
    def __init__(self, bot):
        self.bot = bot  # type: PikalaxBOT

    @commands.group(pass_context=True)
    async def leaderboard(self, ctx):
        pass

    @leaderboard.command()
    async def check(self, ctx):
        score = sql.get_score(ctx)
        if score is None:
            await ctx.send(f'{ctx.author.mention} has {score:d} point(s) across all games.')
        else:
            await ctx.send(f'{ctx.author.mention} is not yet on the leaderboard.')

    @leaderboard.command()
    async def show(self, ctx):
        scores = list(sql.get_all_scores())
        scores.sort(key=lambda row: row[2], reverse=True)
        if len(scores) == 0:
            await ctx.send('The leaderboard is empty. Play some games to get your name up there!')
        else:
            msgs = []
            for id, name, score in scores[:10]:
                user = await self.bot.get_user(id)
                if user is not None:
                    name = user.mention
                msgs.append(f'{name}: {score:d}')
            msg = '\n'.join(msgs)
            await ctx.send(f'Leaderboard:\n'
                           f'```\n'
                           f'{msg}\n'
                           f'```')
