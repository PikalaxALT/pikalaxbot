# PikalaxBOT - A Discord bot in discord.py
# Copyright (C) 2018-2021  PikalaxALT
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

import random

import discord
from discord.ext import commands

from . import *
from .utils.converters import dice_roll
import typing
import collections
from jishaku.functools import executor_function


class Rng(BaseCog):
    """Commands for random number generators"""

    @commands.command()
    async def choose(self, ctx: MyContext, *options: str):
        """Choose between multiple options separated by spaces.
        Use quotes to wrap multi-word options."""

        if len(set(options)) < 2:
            await ctx.send('I need at least 2 unique options!',
                           delete_after=10)
        else:
            await ctx.send(random.choice(options))

    @commands.command()
    async def roll(self, ctx: MyContext, params: dice_roll = (1, 6)):
        """Roll one or more dice with a given number of sides."""

        count, sides = params  # type: int, int
        rolls = [str(random.randint(1, sides)) for i in range(count)]
        rollstr = ', '.join(rolls)
        dice = 'die' if count == 1 else 'dice'
        await ctx.send(f'Rolled {count} {sides}-sided {dice}.  Result:\n'
                       f'{rollstr}')

    @commands.group()
    async def random(self, ctx: MyContext):
        """RNG-related commands"""

    @commands.check(lambda ctx: ctx.bot.pokeapi is not None)
    @random.command(name='pokemon')
    async def random_pokemon(self, ctx: MyContext):
        """Get a random Pokemon name"""

        mon = await self.bot.pokeapi.random_pokemon_name()
        await ctx.send(mon)
    
    @random.command(name='quilava')
    async def random_quilava(self, ctx: MyContext):
        """Random quilava image"""

        img_pool = [
            "http://25.media.tumblr.com/tumblr_m2y3fwJvIp1r29nmno1_1280.jpg",
            "http://orig12.deviantart.net/736b/f/2013/230/3/9/quilava_by_haychel-d6is5we.jpg",
            "http://pre03.deviantart.net/556f/th/pre/i/2013/208/9/c/quilava_playing_with_a_pokeball_by_tropiking-d6ffpu6.png",
            "http://orig12.deviantart.net/8d43/f/2013/349/5/d/pokeddexy_07__quilava_by_saital-d6y4u4c.png",
            "http://pre11.deviantart.net/b767/th/pre/i/2014/134/0/e/i_don_t_want_go_back_to_poke_ball____by_ffxazq-d7hyhp5.jpg",
            "http://img14.deviantart.net/32f8/i/2014/098/f/b/quilava_background_by_rinnai_rai-d7dpu2n.png",
            "http://orig15.deviantart.net/1aed/f/2014/082/2/1/exbo_by_nexeron-d7bbcnu.png",
            "http://orig01.deviantart.net/fae2/f/2012/364/b/5/quilava_by_ieaka-d5pqu98.png",
            "http://orig05.deviantart.net/efe3/f/2012/131/5/0/quilava_by_sirnorm-d4zc40n.png",
            "http://img01.deviantart.net/eace/i/2015/113/f/6/fire_loves_ice_by_dreamynormy-d5ps06w.png",
            "http://pre05.deviantart.net/5b79/th/pre/f/2014/243/6/e/devin_and_lightphire__pmdte_fanart__by_speedboosttorchic-d7xhpya.png",
            "http://img03.deviantart.net/4a05/i/2013/238/0/8/quilava_s_in_love____by_yoko_uzumaki-d6jsn21.png",
            "http://img03.deviantart.net/0922/i/2013/153/5/4/more_cuddling_x3_by_rikuaoshi-d67k2gn.jpg"
        ]
        url = random.choice(img_pool)
        await ctx.send(f'Quilava ❤ {url}')

    async def cog_command_error(self, ctx: MyContext, exc: commands.CommandError):
        orig: BaseException = getattr(exc, 'original', exc)
        if isinstance(exc, commands.ConversionError):
            if isinstance(orig, AssertionError):
                await ctx.send(f'Argument to {ctx.prefix}{ctx.command} must not be more than 200 dice, '
                               f'and each die must have between 2 and 100 sides.')
                exc = None
            elif isinstance(orig, (ValueError, TypeError)):
                await ctx.send(f'Argument to {ctx.prefix}{ctx.command} must be of the form [N]d[S], '
                               f'where N is the number of dice and S is the number of sides per die. '
                               f'Both N and S are optional, but at least one must be supplied.')
                exc = None
            elif orig is not None:
                exc = orig
        if exc is not None:
            await ctx.send(f'**{exc.__class__.__name__}:** {exc} {self.bot.command_error_emoji}',
                           delete_after=10)
        self.log_tb(ctx, exc)

    @staticmethod
    @executor_function
    def sample_random(k: int, choices: typing.Sequence[str]):
        return collections.Counter(random.choices(choices, k=k))

    @staticmethod
    def get_keycap_emoji(i: int):
        assert 10 >= i >= 0
        if i < 10:
            return '{:d}\ufe0f\u20e3'.format(i)
        return '\U0001f51f'

    @commands.command(aliases=['randvote'])
    async def choosebestof(self, ctx: MyContext, k: typing.Optional[int], *choices: str):
        """Sample k times and report the results"""

        response = discord.Embed(colour=0xf47fff)
        nitems = len(choices)
        if nitems < 2:
            raise ValueError('need at least 2 choices to choose from')
        if k is None:
            k = 1000
            response.title = f'Simulating 1000 (default) votes among {nitems} items'
        else:
            old_k = k
            k = min(10000, max(k, 1))
            if k != old_k:
                response.title = f'Simulating {k} votes (clamped) among {nitems} items'
            else:
                response.title = f'Simulating {k} votes among {nitems} items'
        results: collections.Counter[str] = await Rng.sample_random(k, choices)
        if len(results) > 10:
            response.set_footer(text='Only showing the top 10 results')
        response.description = '\n'.join(
            f'{Rng.get_keycap_emoji(i)} {item} ({count} times, {count * 100 / k:.2f}%)'
            for i, (item, count) in enumerate(results.most_common(10), 1)
        )
        await ctx.send(embed=response)


def setup(bot: PikalaxBOT):
    bot.add_cog(Rng(bot))
