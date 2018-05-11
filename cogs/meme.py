import discord
import aiohttp
from discord.ext import commands
from bot import log
import random
from utils import sql


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
        if 'DANCE' in resp:
            await ctx.send(f'♫ ┌༼ຈل͜ຈ༽┘ ♪ {resp} RIOT ♪ └༼ຈل͜ຈ༽┐♫')
        else:
            await ctx.send(f'ヽ༼ຈل͜ຈ༽ﾉ {resp} RIOT ヽ༼ຈل͜ຈ༽ﾉ')

    @commands.group()
    async def bag(self, ctx):
        """!bag

        Get in the bag, Nebby."""
        if ctx.invoked_subcommand is None:
            try:
                message = sql.read_bag()
            except sql.Error:
                await ctx.send('Encountered an error while trying to grab a message from the bag')
            else:
                await ctx.send(message.format(name=self.bot.user.display_name))

    @bag.command()
    async def add(self, ctx, fmtstr: str):
        """!bag add <fmtstr>

        Add a message to the bag.

        {name}: Insert the bot's name."""
        try:
            if sql.add_bag(fmtstr):
                await ctx.send('Message was successfully placed in the bag')
            else:
                await ctx.send('That message is already in the bag')
        except sql.Error:
            await ctx.send('Encountered an error while trying to add message to the bag')

    @commands.command()
    async def nebby(self, ctx):
        """!nebby

        Pew!"""
        # States: start, P, E, W, !, end
        transition = [[0, 1, 9, 0, 0, 0],
                      [0, 1, 2, 1, 0, 0],
                      [0, 1, 1, 1, 1, 0],
                      [0, 0, 0, 0, 1, 9],
                      [0, 0, 0, 0, 0, 1]]
        state = 0
        emission = 'P'
        while len(emission < 100):
            state = random.choices(range(5), weights=transition[state])
            if state == 4:
                break
            emission += 'pew!'[state]
        await ctx.send(emission)


def setup(bot):
    bot.add_cog(Meme(bot))
