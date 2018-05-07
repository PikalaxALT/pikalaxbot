import discord
import aiohttp
from discord.ext import commands
from bot import log
import random


class Meme:
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def archeops(self, ctx, subj1: str = '', subj2: str = ''):
        """!archeops <arg1> <arg2>

        Generates a random paragraph using <arg1> and <arg2> as subject keywords, using the WatchOut4Snakes frontend.
        """
        log.info(f'!archeops {subj1} {subj2}')
        data = {'Subject1': subj1, 'Subject2': subj2}
        async with aiohttp.ClientSession() as cs:
            async with cs.post('http://www.watchout4snakes.com/wo4snakes/Random/RandomParagraph', data=data) as r:
                if r.status == 200:
                    res = await r.text()
                    await ctx.send(res)
                else:
                    await ctx.send(f'Do you like vore? I don\'t, but apparently the WatchOut4Snakes server does. '
                                   f'Status code: {r.status}')
                    raise discord.HTTPException(r.status, r.reason)

    @commands.command()
    async def riot(self, ctx, *args):
        """!riot <reason>

        Riots (for some reason)"""
        resp = ' '.join(args).upper()
        await ctx.send(f'ヽ༼ຈل͜ຈ༽ﾉ {resp} RIOT ヽ༼ຈل͜ຈ༽ﾉ')


def setup(bot):
    bot.add_cog(Meme(bot))
