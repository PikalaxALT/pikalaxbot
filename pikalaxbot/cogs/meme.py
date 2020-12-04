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
import re
import pyfiglet
import asyncio
import time
import functools

import discord
from discord.ext import commands, tasks, menus

from . import BaseCog
from .utils.menus import NavMenuPages

DPY_GUILD_ID = 336642139381301249
MaybePartialEmoji = typing.Union[discord.PartialEmoji, str]


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
    """Random meme commands"""

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
        self.session: aiohttp.ClientSession = bot.client_session

    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            return
        await ctx.send(f'**{error.__class__.__name__}:** {error}')

    @commands.command(ignore_extra=False)
    async def archeops(self, ctx, subj1: MaybePartialEmoji = '', subj2: MaybePartialEmoji = ''):
        """Generates a random paragraph using <arg1> and <arg2> as subject keywords, using the WatchOut4Snakes frontend.
        """

        true_subj1 = subj1 if isinstance(subj1, str) else '%5bBLAH1%5d'
        true_subj2 = subj2 if isinstance(subj2, str) else '%5bBLAH2%5d'

        timeout = aiohttp.ClientTimeout(total=15.0)
        params = {'Subject1': true_subj1, 'Subject2': true_subj2}
        async with ctx.typing():
            async with self.session.post('http://www.watchout4snakes.com/Random/RandomParagraph', data=params, timeout=timeout) as r:
                res = await r.text()
        if not isinstance(subj1, str):
            res = res.replace(true_subj1, str(subj1))
        if not isinstance(subj2, str):
            res = res.replace(true_subj2, str(subj2))
        await ctx.send(res)

    @commands.command()
    async def riot(self, ctx, *, reason=''):
        """Riots (for some reason)"""

        if reason:
            reason = reason.upper() + ' '
        if re.search(r'\bDANCE\b', reason):
            await ctx.send(f'♫ ┌༼ຈل͜ຈ༽┘ ♪ {reason}RIOT ♪ └༼ຈل͜ຈ༽┐♫')
        else:
            await ctx.send(f'ヽ༼ຈل͜ຈ༽ﾉ {reason}RIOT ヽ༼ຈل͜ຈ༽ﾉ')

    @commands.command()
    async def nebby(self, ctx):
        """Pew!"""

        emission = ''.join(self._nebby.get_chain(100, end=4)).title()
        await ctx.send(emission)

    @commands.check(lambda ctx: ctx.bot.pokeapi)
    @commands.command()
    async def yolonome(self, ctx):
        """Happy birthday, Waggle!"""

        async with self.bot.pokeapi as pokeapi:
            move_name = await pokeapi.random_move_name(clean=False)
        await ctx.send(f'{ctx.author.mention} used Metronome!\n'
                       f'Waggling a finger allowed it to use {move_name}!')

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
        if not isinstance(target, discord.Role) and target.id in {self.bot.user.id, self.bot.owner_id}:
            shaft = '=' * 69
        else:
            shaft = '=' * ((hash(target) % 30) + 1)
        collective = 'average ' if isinstance(target, discord.Role) else ''
        mention = '@everyone' if isinstance(target, discord.Role) and target.is_default() else target.mention
        await ctx.send(f'{mention}\'s {collective}dick: 8{shaft}D', allowed_mentions=discord.AllowedMentions.none())

    @commands.command()
    async def ascii(self, ctx, *, message):
        """Prints the message in huge ugly block letters"""

        paginator = commands.Paginator()
        partial = functools.partial(pyfiglet.figlet_format, message, width=37)
        block_text = await self.bot.loop.run_in_executor(None, partial)
        for i, line in enumerate(block_text.splitlines(), 1):
            paginator.add_line(line)
            if i % 30 == 0:
                paginator.close_page()

        class SimplePageSource(menus.ListPageSource):
            async def format_page(self, menu: NavMenuPages, page):
                return f'{page}\n\nPage {menu.current_page + 1} of {self.get_max_pages()}'

        menu = NavMenuPages(SimplePageSource(paginator.pages, per_page=1), delete_message_after=True, clear_reactions_after=True)
        await menu.start(ctx)

    @commands.max_concurrency(1, commands.BucketType.channel)
    @commands.command(aliases=['cookie', 'c'])
    async def cookies(self, ctx: commands.Context):
        """Reaction time game! Click the cookie as fast as you can!"""

        emoji, = random.choices(['🥠', '🍪'], k=1, weights=[0.05, 0.95])
        embed = discord.Embed(
            description=f'First one to eat the cookie {emoji} wins!',
            colour=0xf47fff
        )
        msg = await ctx.send(embed=embed)

        @self.bot.listen()
        async def on_reaction_add(reaction, user):
            if reaction.message == msg and user != self.bot.user:
                try:
                    await reaction.clear()
                except discord.Forbidden:
                    pass

        @tasks.loop(seconds=1, count=3)
        async def countdown():
            embed.description = 3 - countdown.current_loop
            await msg.edit(embed=embed)

        @countdown.before_loop
        async def before_countdown():
            await asyncio.sleep(random.random() * 5 + 3)

        @countdown.after_loop
        async def after_countdown():
            await discord.utils.sleep_until(countdown._next_iteration)
            self.bot.remove_listener(on_reaction_add)

        await countdown.start()
        self.bot.loop.create_task(msg.add_reaction(emoji))
        start = time.perf_counter()
        try:
            rxn, usr = await self.bot.wait_for('reaction_add', check=lambda r, u: r.message == msg and str(r) == emoji and u != self.bot.user, timeout=10.0)
        except asyncio.TimeoutError:
            embed.description = 'No one claimed the cookie...'
        else:
            end = time.perf_counter()
            embed.description = f'**{usr}** has eaten the cookie in {end - start:.3f}s, yum yum'
        finally:
            await msg.remove_reaction(emoji, ctx.me)
        await msg.edit(embed=embed)

    @commands.command(name='howgay')
    async def show_how_gay(self, ctx, *, member: discord.Member = None):
        """Reports how gay you are"""

        member = member or ctx.author
        await ctx.send(f'{member} is {random.Random(hash(member)).random() * 100:.1f}% gay.')


def setup(bot):
    bot.add_cog(Meme(bot))
