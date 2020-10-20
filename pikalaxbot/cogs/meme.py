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

import random
import aiohttp
import typing
import os

import discord
from discord.ext import commands

from . import BaseCog

DPY_GUILD_ID = 336642139381301249

__dir__ = os.path.dirname(os.path.dirname(__file__)) or '.'
with open(os.path.join(os.path.dirname(__dir__), 'version.txt')) as fp:
    __version__ = fp.read().strip()

MaybeEmoji = typing.Union[discord.Emoji, discord.PartialEmoji, str]


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


class Meme(BaseCog):
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
        self.session: typing.Optional[aiohttp.ClientSession] = None

        async def create_session():
            self.session = aiohttp.ClientSession(raise_for_status=True)

        bot.loop.create_task(create_session())

    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())

    async def init_db(self, sql):
        c = await sql.execute("select count(*) from sqlite_master where type='table' and name='meme'")
        exists, = await c.fetchone()
        await sql.execute("create table if not exists meme (bag text primary key)")
        if not exists:
            await sql.executemany("insert into meme(bag) values (?)", sql.default_bag)

    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            return
        await ctx.send(f'**{error.__class__.__name__}:** {error}')

    @commands.command(ignore_extra=False)
    async def archeops(self, ctx, subj1: MaybeEmoji = '', subj2: MaybeEmoji = ''):
        """Generates a random paragraph using <arg1> and <arg2> as subject keywords, using the WatchOut4Snakes frontend.
        """

        true_subj1 = subj1 if isinstance(subj1, str) else '%5bBLAH1%5d'
        true_subj2 = subj2 if isinstance(subj2, str) else '%5bBLAH2%5d'

        timeout = aiohttp.ClientTimeout(total=15.0)
        params = {'Subject1': true_subj1, 'Subject2': true_subj2}
        async with ctx.typing():
            async with self.session.post('http://www.watchout4snakes.com/wo4snakes/Random/RandomParagraph', data=params, timeout=timeout) as r:
                res = await r.text()
        if not isinstance(subj1, str):
            res = res.replace(true_subj1, str(subj1))
        if not isinstance(subj2, str):
            res = res.replace(true_subj2, str(subj2))
        await ctx.send(res)

    @commands.command()
    async def riot(self, ctx, *, args):
        """Riots (for some reason)"""

        resp = args.upper()
        if 'DANCE' in resp:
            await ctx.send(f'♫ ┌༼ຈل͜ຈ༽┘ ♪ {resp} RIOT ♪ └༼ຈل͜ຈ༽┐♫')
        else:
            await ctx.send(f'ヽ༼ຈل͜ຈ༽ﾉ {resp} RIOT ヽ༼ຈل͜ຈ༽ﾉ')

    @commands.command()
    async def nebby(self, ctx):
        """Pew!"""

        emission = ''.join(self._nebby.get_chain(100, end=4)).title()
        await ctx.send(emission)

    @commands.check(lambda ctx: ctx.bot.pokeapi)
    @commands.command()
    async def yolonome(self, ctx):
        """Happy birthday, Waggle!"""

        await ctx.send(f'{ctx.author.mention} used Metronome!\n'
                       f'Waggling a finger allowed it to use {self.bot.pokeapi.random_move_name(clean=False)}!')

    @commands.command()
    async def olden(self, ctx):
        """Time to corrupt your save file >:D"""

        await ctx.send('https://vignette.wikia.nocookie.net/twitchplayspokemoncrystal/images/5/5f/'
                       'Serious_%22OLDEN%22_Times.png/revision/latest?cb=20160820193335')

    @commands.command()
    async def honk(self, ctx):
        """HONK"""

        emoji = discord.utils.get(self.bot.emojis, name='HONK')
        await ctx.message.add_reaction(emoji)

    @commands.guild_only()
    @commands.command()
    async def someone(self, ctx):
        """\"Pings\" someone"""

        await ctx.send(random.choice(ctx.guild.members).mention, allowed_mentions=discord.AllowedMentions.none())

    @commands.check(lambda ctx: ctx.guild.id == DPY_GUILD_ID)
    @commands.command(aliases=['pp', 'peepee'])
    async def dick(self, ctx, *, target: typing.Union[discord.Member, discord.Role] = None):
        """Get the size of your dick"""

        target = target or ctx.author
        if not isinstance(target, discord.Role) and target.id in (self.bot.user.id, self.bot.owner_id):
            shaft = '=' * 69
        else:
            shaft = '=' * ((hash(target) % 30) + 1)
        collective = 'average ' if isinstance(target, discord.Role) else ''
        mention = '@everyone' if isinstance(target, discord.Role) and target.is_default() else target.mention
        await ctx.send(f'{mention}\'s {collective}dick: 8{shaft}D', allowed_mentions=discord.AllowedMentions.none())


def setup(bot):
    bot.add_cog(Meme(bot))
