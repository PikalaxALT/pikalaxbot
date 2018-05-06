import discord
import aiohttp
from discord.ext import commands
import random


class Meme:
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def archeops(self, ctx, subj1='', subj2=''):
        """!archeops <arg1> <arg2>

        Generates a random paragraph using <arg1> and <arg2> as subject keywords, using the WatchOut4Snakes frontend.
        """
        cleaner = commands.clean_content()
        subj1 = await cleaner.convert(ctx, subj1)
        subj2 = await cleaner.convert(ctx. subj2)
        data = {'Subject1': subj1, 'Subject2': subj2}
        async with aiohttp.ClientSession() as cs:
            async with cs.post('http://www.watchout4snakes.com/wo4snakes/Random/RandomParagraph', data=data) as r:
                if r.status == 200:
                    res = await r.text()
                    await ctx.send(res)
                else:
                    status_code = r.status
                    await ctx.send(f'Do you like vore? I don\'t, but apparently the WatchOut4Snakes server does.  '
                                   f'Status code: {status_code}')

    async def on_command_error(self, ctx, error):
        if isinstance(error, discord.HTTPException):
            await ctx.send('I tried to reply, but my response was vored.')


def setup(bot):
    bot.add_cog(Meme(bot))
