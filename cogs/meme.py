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
import aiohttp
import os
import random
from discord.ext import commands
from utils import sql
from utils.game import find_emoji
from utils.data import data
from utils.default_cog import Cog


class HMM:
    def __init__(self, transition, emission):
        self.transition = transition
        self.emission = emission
        self.state = 0

    @property
    def n_states(self):
        return len(self.transition)

    def emit(self):
        self.state = random.choices(range(self.n_states), weights=self.transition[self.state])
        return self.emission[self.state]

    def get_chain(self, length, start=0, end=-1):
        self.state = start
        for i in range(length):
            yield self.emit()
            if self.state == end:
                break


class Meme(Cog):
    bot_owners = {
        'fixpika': 'PikalaxALT',
        'fixgroudon': 'chfoo',
        'fixyay': 'azum and tustin',
        'fixupdater': 'tustin',
        'fixstarmie': 'Danny',
        'fixmeme': 'Jet'
    }
    bot_names = {
        'fixyay': 'xfix\s bot'
    }
    _nebby = HMM(
        [[0, 1, 0, 0, 0],
         [1, 2, 1, 0, 0],
         [0, 0, 1, 1, 0],
         [0, 0, 0, 1, 9],
         [0, 0, 0, 0, 1]],
        'pew! '
    )

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
            message = await sql.read_bag()
            if message is None:
                emoji = find_emoji(ctx.guild, 'BibleThump', case_sensitive=False)
                await ctx.send(f'*cannot find the bag {emoji}*')
            else:
                await ctx.send(f'*{message}*')

    @bag.command()
    async def add(self, ctx, *, fmtstr):
        """Add a message to the bag."""
        if await sql.add_bag(fmtstr):
            await ctx.send('Message was successfully placed in the bag')
        else:
            await ctx.send('That message is already in the bag')

    @commands.command()
    async def nebby(self, ctx):
        """Pew!"""
        emission = ''.join(self._nebby.get_chain(100, end=4)).title()
        await ctx.send(emission)

    @commands.command()
    async def yolonome(self, ctx):
        """Happy birthday, Waggle!"""
        await ctx.send(f'{ctx.author.mention} used Metronome!\n'
                       f'Waggling a finger allowed it to use {data.random_move_name()}!')

    @commands.command()
    @commands.is_nsfw()
    @commands.bot_has_permissions(attach_files=True)
    async def inspire(self, ctx: commands.Context):
        """Generate an inspirational poster using inspirobot.me"""
        url = ''
        async with aiohttp.ClientSession() as cs:
            async with cs.get('http://inspirobot.me/api',
                              params={'generate': 'true'}) as r:  # type: aiohttp.ClientResponse
                if r.status == 200:
                    url = await r.text()
                else:
                    await ctx.send(f'InspiroBot error (phase: gen-url): {r.status:d}')
                    r.raise_for_status()
                    raise aiohttp.ClientError(f'Abnormal status {r.status:d}')

            filename = os.path.basename(url)
            async with cs.get(url) as r:
                if r.status == 200:
                    with open(filename, 'wb') as t:
                        t.write(await r.read())
                    await ctx.send(file=discord.file.File(filename))
                    os.remove(filename)
                else:
                    await ctx.send(f'InspiroBot error (phase: get-jpg): {r.status:d}')
                    r.raise_for_status()
                    raise aiohttp.ClientError(f'Abnormal status {r.status:d}')

    @commands.command(aliases=list(bot_owners.keys()))
    async def fix(self, ctx: commands.Context):
        alias = ctx.invoked_with
        owner = self.bot_owners.get(alias, 'already')
        botname = self.bot_names.get(alias, 'your bot')
        await ctx.send(f'"Fix {botname}, {owner}!" - PikalaxALT 2018')


def setup(bot):
    bot.add_cog(Meme(bot))
