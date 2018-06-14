import discord
import aiohttp
import os
import random
from discord.ext import commands
from utils import sql
from utils.checks import ctx_can_markov
from utils.game import find_emoji
from utils.data import data


class Meme:
    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    def gen_nebby():
        transition = [[0, 1, 0, 0, 0],
                      [1, 2, 1, 0, 0],
                      [0, 0, 1, 1, 0],
                      [0, 0, 0, 1, 9],
                      [0, 0, 0, 0, 1]]
        state = 0
        emission = 'P'
        while len(emission) < 100:
            state = random.choices(range(5), weights=transition[state])[0]
            if state == 4:
                break
            emission += 'pew!'[state]
        return emission

    @commands.command()
    async def archeops(self, ctx, subj1: str = '', subj2: str = ''):
        """Generates a random paragraph using <arg1> and <arg2> as subject keywords, using the WatchOut4Snakes frontend.
        """
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
        """Riots (for some reason)"""
        resp = ' '.join(args).upper()
        if 'DANCE' in resp:
            await ctx.send(f'♫ ┌༼ຈل͜ຈ༽┘ ♪ {resp} RIOT ♪ └༼ຈل͜ຈ༽┐♫')
        else:
            await ctx.send(f'ヽ༼ຈل͜ຈ༽ﾉ {resp} RIOT ヽ༼ຈل͜ຈ༽ﾉ')

    @commands.group()
    async def bag(self, ctx):
        """Get in the bag, Nebby."""
        if ctx.invoked_subcommand is None:
            message = sql.read_bag()
            if message is None:
                emoji = find_emoji(ctx.guild, 'BibleThump', case_sensitive=False)
                await ctx.send(f'*cannot find the bag {emoji}*')
            else:
                await ctx.send(f'*{message}*')

    @bag.command()
    async def add(self, ctx, *fmtstr):
        """Add a message to the bag."""
        if sql.add_bag(' '.join(fmtstr)):
            await ctx.send('Message was successfully placed in the bag')
        else:
            await ctx.send('That message is already in the bag')

    @commands.command()
    async def nebby(self, ctx):
        """Pew!"""
        # States: start, P, E, W, !, end
        emission = self.gen_nebby()
        await ctx.send(emission)

    @commands.command(pass_context=True, hidden=True)
    @commands.check(ctx_can_markov)
    async def markov(self, ctx):
        """Generate a random word Markov chain."""
        chain = self.bot.gen_msg(len_max=250, n_attempts=10)
        if chain:
            await ctx.send(f'{ctx.author.mention}: {chain}')
        else:
            await ctx.send(f'{ctx.author.mention}: An error has occurred.')

    @commands.command(pass_context=True)
    async def yolonome(self, ctx):
        """Happy birthday, Waggle!"""
        await ctx.send(f'{ctx.author.mention} used Metronome!\n'
                       f'Waggling a finger allowed it to use {data.random_move_name()}!')

    @commands.command(pass_context=True)
    async def inspire(self, ctx: commands.Context):
        """Generate an inspirational poster using inspirobot.me"""
        url = ''
        async with aiohttp.ClientSession() as cs:
            async with cs.get('http://inspirobot.me/api', params={'generate': 'true'}) as r:
                r: aiohttp.ClientResponse
                if r.status == 200:
                    url = await r.text()
                else:
                    await ctx.send(f'InspiroBot error (phase: gen-url): {r.status:d}')
                    r.raise_for_status()
                    raise aiohttp.ClientError(f'Abnormal status {r.status:d}')

            filename = os.path.basename(url)
            async with cs.get(url) as r:
                with open(filename, 'w+b') as t:
                    if r.status == 200:
                        t.write(await r.read())
                        t.seek(0)
                        try:
                            await ctx.send(file=discord.file.File(t))
                        except discord.Forbidden:
                            await ctx.send('Could not upload the meme (bot lacks permissions)')
                    else:
                        await ctx.send(f'InspiroBot error (phase: get-jpg): {r.status:d}')
                        r.raise_for_status()
                        raise aiohttp.ClientError(f'Abnormal status {r.status:d}')
        os.remove(filename)


def setup(bot):
    bot.add_cog(Meme(bot))
