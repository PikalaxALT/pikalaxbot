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

import discord
from discord.ext import commands, menus
import random
from . import *
import asyncio
import re
import traceback
import typing
import asyncpg
from .utils.game import increment_score


_emojis = '\u270a', '\u270b', '\u270c', '\u274c'


class RPSError(commands.CommandError):
    pass


class RPSMenu(menus.Menu):
    async def my_action(self, payload: discord.RawReactionActionEvent):
        self.player_move = _emojis.index(str(payload.emoji))
        self.stop()

    def __init__(
            self,
            player: typing.Optional[discord.Member] = None,
            opponent: typing.Optional[discord.Member] = None,
            **kwargs
    ):
        super().__init__(**kwargs)
        self.player_move = 3
        self.player = player
        self.opponent = opponent
        self.bot_move = 3 if opponent else random.randrange(3)
        self.timed_out = False
        for emoji in _emojis:
            self.add_button(menus.Button(emoji, self.my_action))

    async def send_initial_message(self, ctx: MyContext, channel):
        self.player = self.player or ctx.author
        self.opponent = self.opponent or ctx.me
        embed = discord.Embed(
            title=f'Rock Paper Scissors between {self.player} and {self.opponent}',
            description='Once all four reactions have been set, choose one to'
                        ' react with in an epic battle of Rock Paper Scissors.'
                        ' React with \u274c to cancel.',
            colour=discord.Colour.orange()
        )
        return await channel.send(embed=embed)

    async def finalize(self, timed_out):
        embed: discord.Embed = self.message.embeds[0]
        if self.opponent != self.ctx.me:
            self.timed_out = timed_out
            return
        elif timed_out:
            embed.description += '\n\nTime\'s up, the player left'
        elif self.player_move == 3:
            embed.description += '\n\nGame cancelled by player'
        else:
            player_emoji = _emojis[self.player_move]
            bot_emoji = _emojis[self.bot_move]
            diff = self.bot_move - self.player_move
            # 0: tied
            # 1: bot wins
            # 2: player wins
            embed.description += f'\n\n{self.ctx.author}: {player_emoji}\n{self.bot.user}: {bot_emoji}\n\n'
            embed.description += '**' + ('It\'s a draw!', 'The player loses...', 'The player wins!')[diff] + '**'
            embed.colour = (discord.Colour.dark_gray, discord.Colour.red, discord.Colour.green)[diff]()
        await self.message.edit(embed=embed)


class RockPaperScissors(BaseCog):
    """Commands for playing rock-paper-scissors"""

    def __init__(self, bot):
        super().__init__(bot)
        self.rps_tasks: dict[tuple[int, int, int], asyncio.Task] = {}

    async def do_rps(self, ctx: MyContext, *, opponent: discord.Member = None):
        if opponent in {ctx.me, None}:
            menu = RPSMenu(clear_reactions_after=True)
            await menu.start(ctx, wait=True)
        elif opponent == ctx.author:
            return await ctx.send('You can\'t play against yourself!')
        elif opponent.bot:
            return await ctx.send('You can\'t play against a bot!')
        else:
            await ctx.send(f'{opponent.mention} you have been challenged to '
                           f'an epic game of Rock Paper Scissors with {ctx.author.mention}. '
                           f'Do you accept?')

            def check(m: discord.Message):
                return m.channel == ctx.channel and m.author == opponent

            try:
                msg = await self.bot.wait_for('message', check=check, timeout=60.0)
            except asyncio.TimeoutError:
                return await ctx.send('The other player did not respond...')
            if not re.match(r'^(y(es|e?a?h?)?|o?k(ay)?|sure)$', msg.content, re.I):
                return await ctx.send('That wasn\'t a yes. Challenge canceled.')
            menu1 = RPSMenu(player=ctx.author, opponent=opponent, clear_reactions_after=True)
            menu2 = RPSMenu(player=opponent, opponent=ctx.author, clear_reactions_after=True)
            try:
                menu1.message = await menu1.send_initial_message(ctx, ctx.author)
            except discord.Forbidden:
                return await ctx.send('You need to turn on your DMs for this!')
            try:
                menu2.message = await menu2.send_initial_message(ctx, opponent)
            except discord.Forbidden:
                await menu1.message.edit(content='Game cancelled', embed=None)
                await menu1.message.delete(delay=5)
                return await ctx.send('Your opponent has their DMs closed...')
            await ctx.send(f'Rock Paper Scissors between {ctx.author.mention} and {opponent.mention}! '
                           f'Check your DMs!')
            tasks = [
                asyncio.create_task(menu1.start(ctx, channel=ctx.author.dm_channel, wait=True)),
                asyncio.create_task(menu2.start(ctx, channel=opponent.dm_channel, wait=True))
            ]
            try:
                await asyncio.wait(tasks, return_when=asyncio.ALL_COMPLETED)
            except asyncio.CancelledError:
                [task.cancel() for task in tasks]
                raise
            content_return = f'Game finished, go back to {ctx.channel.mention} for the results'
            [asyncio.create_task(user.send(content_return)) for user in (ctx.author, opponent)]
            if menu1.timed_out:
                return await ctx.send(f'{ctx.author} took too long to respond...')
            elif menu1.player_move == 3:
                return await ctx.send(f'{ctx.author} forfeited...')
            elif menu2.timed_out:
                return await ctx.send(f'{opponent} took too long to respond...')
            elif menu2.player_move == 3:
                return await ctx.send(f'{opponent} forfeited...')
            player_emoji = _emojis[menu1.player_move]
            opponent_emoji = _emojis[menu2.player_move]
            diff = menu2.player_move - menu1.player_move
            # 0: tied
            # 1: defender wins
            # 2: challenger wins
            content = f'\n\n' \
                      f'{ctx.author.mention}\'s move: {player_emoji}\n' \
                      f'{opponent.mention}\'s move: {opponent_emoji}\n\n'
            content += '**' + ('It\'s a draw!', f'{opponent.mention} wins!', f'{ctx.author.mention} wins!')[diff] + '**'
            if winner := [None, opponent, ctx.author][diff]:
                async with self.bot.sql as sql:  # type: asyncpg.Connection
                    await increment_score(sql, winner, by=69)
                content += f'\n\n{winner.mention} earns 69 points for winning!'
            await ctx.send(content)

    @commands.group(aliases=['rps'])
    @commands.max_concurrency(1, commands.BucketType.channel)
    async def rock_paper_scissors(self, ctx: MyContext, *, opponent: discord.Member = None):
        """Play a game of Rock-Paper-Scissors with someone, or with the bot"""
        coro = self.do_rps(ctx, opponent=opponent)
        task = asyncio.create_task(coro)
        self.rps_tasks[(ctx.guild.id, ctx.channel.id, ctx.author.id)] = task
        try:
            await task
        except asyncio.CancelledError:
            await ctx.send('The game was cancelled.')

    async def cog_command_error(self, ctx: MyContext, error: commands.CommandError):
        error = getattr(error, 'original', error)
        if isinstance(error, commands.MaxConcurrencyReached):
            await ctx.send(f'Wait your turn, {ctx.author.mention}!', delete_after=10)
        else:
            tb = traceback.format_exception(error.__class__, error, error.__traceback__)
            pag = commands.Paginator
            [pag.add_line(line.rstrip('\n')) for line in tb]

            class ErrorPageSource(menus.ListPageSource):
                def format_page(self, menu: menus.MenuPages, page: str):
                    return page

            exc_menu = menus.MenuPages(ErrorPageSource(pag.pages, per_page=1), delete_message_after=True)
            await exc_menu.start(ctx)


def setup(bot: PikalaxBOT):
    bot.add_cog(RockPaperScissors(bot))
