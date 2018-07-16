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

import asyncio
import discord
import aiohttp
import os
import random
import io
from discord.ext import commands
from utils.data import data
from cogs import Cog


class HMM:
    def __init__(self, transition, emission):
        self.transition = transition
        self.emission = emission
        self.state = 0

    @property
    def n_states(self):
        return len(self.transition)

    def emit(self):
        res = self.emission[self.state]
        self.state, = random.choices(range(self.n_states), weights=self.transition[self.state])
        return res

    def get_chain(self, length, start=0, end=-1):
        self.state = start
        for i in range(length):
            yield self.emit()
            if self.state == end:
                break


class Meme(Cog):
    _nebby = HMM(
        [[0, 1, 0, 0, 0],
         [1, 2, 1, 0, 0],
         [0, 0, 1, 1, 0],
         [0, 0, 0, 1, 9],
         [0, 0, 0, 0, 1]],
        'pew! '
    )

    def __init__(self, bot):
        super().__init__(bot)
        self.cs = aiohttp.ClientSession(raise_for_status=True)

    def __del__(self):
        task = self.bot.loop.create_task(self.cs.close())
        asyncio.wait([task])

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
        r = await self.cs.get('http://inspirobot.me/api', params={'generate': 'true'})
        url = await r.text()
        r = await self.cs.get(url)
        stream = io.BytesIO(await r.read())
        await ctx.send(file=discord.file.File(stream, os.path.basename(url)))

    @inspire.error
    async def inspire_error(self, ctx, exc):
        await ctx.send(f'An error occurred. How uninspiring.\n'
                       f'{exc.__class__.__name__}: {exc}')


def setup(bot):
    bot.add_cog(Meme(bot))
