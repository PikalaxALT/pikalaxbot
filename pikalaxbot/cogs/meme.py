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
import aiohttp
import typing
import re
import pyfiglet
import asyncio
import time
import functools
import operator

import discord
from discord.ext import commands, tasks, menus

from . import *
from .utils.menus import NavMenuPages
from ..types import *
from ..constants import *


class Meme(BaseCog):
    """Random meme commands"""

    @functools.cache
    def _calc_gayness(self, member: discord.Member):
        return random.Random(member).random()

    async def cog_command_error(self, ctx: MyContext, error: commands.CommandError):
        if isinstance(error, commands.CheckFailure):
            return
        if isinstance(error, commands.CommandInvokeError):
            error = error.original
            embed = ctx.prepare_command_error_embed()
            await self.bot.send_tb(ctx, error, origin=f'command {ctx.command}', embed=embed)
        await ctx.send(f'**{error.__class__.__name__}:** {error}')

    @commands.command(ignore_extra=False)
    async def archeops(self, ctx: MyContext, subj1: MaybePartialEmoji = '', subj2: MaybePartialEmoji = ''):
        """Generates a random paragraph using <arg1> and <arg2> as subject keywords, using the WatchOut4Snakes frontend.
        """

        true_subj1 = subj1 if isinstance(subj1, str) else '%5bBLAH1%5d'
        true_subj2 = subj2 if isinstance(subj2, str) else '%5bBLAH2%5d'

        timeout = aiohttp.ClientTimeout(total=15.0)
        params = {'Subject1': true_subj1, 'Subject2': true_subj2}
        async with ctx.typing():
            async with self.bot.client_session.post(
                    'http://www.watchout4snakes.com/Random/RandomParagraph',
                    data=params,
                    timeout=timeout
            ) as r:
                res = await r.text()
        if not isinstance(subj1, str):
            res = res.replace(true_subj1, str(subj1))
        if not isinstance(subj2, str):
            res = res.replace(true_subj2, str(subj2))
        if len(res) > 2000:
            paginator = commands.Paginator('', '')
            for line in res.rstrip('.').split('. '):
                paginator.add_line(line + '.')
            for page in paginator.pages:
                await ctx.send(page)
        else:
            await ctx.send(res)

    @commands.command()
    async def riot(self, ctx: MyContext, *, reason=''):
        """Riots (for some reason)"""

        if reason:
            reason = reason.upper() + ' '
        if re.search(r'\bDANCE\b', reason):
            await ctx.send(f'♫ ┌༼ຈل͜ຈ༽┘ ♪ {reason}RIOT ♪ └༼ຈل͜ຈ༽┐♫')
        else:
            await ctx.send(f'ヽ༼ຈل͜ຈ༽ﾉ {reason}RIOT ヽ༼ຈل͜ຈ༽ﾉ')

    @commands.check(lambda ctx: ctx.bot.pokeapi is not None)
    @commands.command()
    async def yolonome(self, ctx: MyContext):
        """Happy birthday, Waggle!"""

        move_name = await self.bot.pokeapi.random_move_name()
        await ctx.send(f'{ctx.author.mention} used Metronome!\n'
                       f'Waggling a finger allowed it to use {move_name}!')

    @commands.command()
    async def olden(self, ctx: MyContext):
        """Time to corrupt your save file >:D"""

        await ctx.send('https://vignette.wikia.nocookie.net/twitchplayspokemoncrystal/images/5/5f/'
                       'Serious_%22OLDEN%22_Times.png/revision/latest?cb=20160820193335')

    @commands.command()
    async def honk(self, ctx: MyContext):
        """HONK"""

        emoji = discord.utils.get(self.bot.emojis, name='HONK')
        await ctx.message.add_reaction(emoji)

    @commands.guild_only()
    @commands.command()
    async def someone(self, ctx: MyContext):
        """\"Pings\" someone"""

        await ctx.send(random.choice(ctx.guild.members).mention, allowed_mentions=discord.AllowedMentions.none())

    @commands.check(lambda ctx: ctx.guild.id == DPY_GUILD_ID)
    @commands.command(aliases=['pp', 'peepee'])
    async def dick(self, ctx: MyContext, *, target: typing.Union[discord.Member, discord.Role] = None):
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
    async def ascii(self, ctx: MyContext, *, message: str):
        """Prints the message in huge ugly block letters"""

        paginator = commands.Paginator()
        partial = functools.partial(pyfiglet.figlet_format, message, width=37)
        block_text = await asyncio.get_running_loop().run_in_executor(None, partial)
        for i, line in enumerate(block_text.splitlines(), 1):
            paginator.add_line(line)
            if i % 30 == 0:
                paginator.close_page()

        class SimplePageSource(menus.ListPageSource):
            def format_page(self, menu_: NavMenuPages, page):
                return f'{page}\n\nPage {menu_.current_page + 1} of {self.get_max_pages()}'

        menu = NavMenuPages(
            SimplePageSource(paginator.pages, per_page=1),
            delete_message_after=True,
            clear_reactions_after=True
        )
        await menu.start(ctx)

    @commands.max_concurrency(1, commands.BucketType.channel)
    @commands.command(aliases=['cookie', 'c'])
    async def cookies(self, ctx: MyContext):
        """Reaction time game! Click the cookie as fast as you can!"""

        emoji, = random.choices(['🥠', '🍪'], k=1, weights=[0.05, 0.95])
        embed = discord.Embed(
            description=f'First one to eat the cookie {emoji} wins!',
            colour=0xf47fff
        )
        msg = await ctx.send(embed=embed)

        @self.bot.listen()
        async def on_reaction_add(reaction: discord.Reaction, user: discord.User):
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
        asyncio.create_task(msg.add_reaction(emoji))
        start = time.perf_counter()
        try:
            rxn, usr = await self.bot.wait_for(
                'reaction_add',
                check=lambda r, u:
                    r.message == msg
                    and str(r) == emoji
                    and u != self.bot.user,
                timeout=10.0
            )  # type: discord.Reaction, discord.User
        except asyncio.TimeoutError:
            embed.description = 'No one claimed the cookie...'
        else:
            end = time.perf_counter()
            embed.description = f'**{usr}** has eaten the cookie in {end - start:.3f}s, yum yum'
        finally:
            await msg.remove_reaction(emoji, ctx.me)
        await msg.edit(embed=embed)

    @commands.guild_only()
    @commands.command(name='howgay')
    async def show_how_gay(self, ctx, *, member: discord.Member = None):
        """Reports how gay you are"""

        member = member or ctx.author
        gayness = self._calc_gayness(member)
        await ctx.send(f'{member} is {gayness * 100:.1f}% gay.')

    @commands.guild_only()
    @commands.command(name='who-is-gay', aliases=['whosgay', 'whoisgay', 'whos-gay'])
    async def show_top_gays(self, ctx):
        """Reports the top 10 gay people"""

        async with ctx.typing():
            members = sorted(
                [(member, self._calc_gayness(member)) for member in ctx.guild.members if not member.bot],
                key=operator.itemgetter(1),
                reverse=True
            )[:10]
        embed = discord.Embed(
            title=f'Top {min(len(members), 10)} gayest members of {ctx.guild}',
            description='\n'.join(
                f'**#{i}:** {member.mention} ({gayness * 100:.1f}%)'
                for i, (member, gayness) in enumerate(members[:10], 1)
            ),
            colour=0xF47FFF
        )
        await ctx.send(embed=embed)


def setup(bot: PikalaxBOT):
    bot.add_cog(Meme(bot))
