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

from discord.ext import commands

from utils.data import data
from utils.game import GameBase, GameCogBase


# noinspection PyAttributeOutsideInit
class AnagramGame(GameBase):
    def __init__(self, bot, attempts=3):
        self._attempts = attempts
        super().__init__(bot)

    def reset(self):
        super().reset()
        self._state = ''
        self._solution = ''
        self._incorrect = []
        self.attempts = 0

    @property
    def incorrect(self):
        return ', '.join(self._incorrect)

    def __str__(self):
        return f'```Puzzle: {self.state}\n' \
               f'Incorrect: [{self.incorrect}]\n' \
               f'Remaining: {self.attempts:d}```'

    async def start(self, ctx: commands.Context):
        if self.running:
            await ctx.send(f'{ctx.author.mention}: Anagram is already running here.',
                           delete_after=10)
        else:
            self._solution = data.random_pokemon_name().upper()
            self._state = list(self._solution)
            while ''.join(self._state) == self._solution:
                random.shuffle(self._state)
            self._state = ''.join(self._state)
            self.attempts = self._attempts
            self._incorrect = []
            await ctx.send(f'Anagram has started! You have {self.attempts:d} attempts and {self._timeout:d} seconds '
                           f'to guess correctly before OLDEN corrupts your save.\n')
            await super().start(ctx)

    async def end(self, ctx: commands.Context, failed=False, aborted=False):
        if await super().end(ctx, failed=failed, aborted=aborted):
            await self._message.edit(content=self)
            if aborted:
                await ctx.send(f'Game terminated by {ctx.author.mention}.\n'
                               f'Solution: {self._solution}')
            elif failed:
                await ctx.send(f'You were too late, welcome to Glitch Purgatory.\n'
                               f'Solution: {self._solution}')
            else:
                self.add_player(ctx.author)
                score = await self.award_points()
                await ctx.send(f'{ctx.author.mention} has solved the puzzle!\n'
                               f'Solution: {self._solution}\n'
                               f'{ctx.author.mention} earned {score} points for winning!')
            self.reset()
        else:
            await ctx.send(f'{ctx.author.mention}: Anagram is not running here. '
                           f'Start a game by saying `{ctx.prefix}anagram start`.',
                           delete_after=10)

    async def solve(self, ctx: commands.Context, *guess):
        if self.running:
            guess = ' '.join(guess).upper()
            if guess in self._incorrect:
                await ctx.send(f'{ctx.author.mention}: Solution already guessed: {guess}',
                               delete_after=10)
            else:
                if self._solution == guess:
                    self._state = self._solution
                    await self.end(ctx)
                else:
                    self._incorrect.append(guess)
                    self.attempts -= 1
            if self.running:
                await self._message.edit(content=self)
                if self.attempts == 0:
                    await self.end(ctx, True)
        else:
            await ctx.send(f'{ctx.author.mention}: Anagram is not running here. '
                           f'Start a game by saying `{ctx.prefix}anagram start`.',
                           delete_after=10)

    async def show(self, ctx):
        if await super().show(ctx) is None:
            await ctx.send(f'{ctx.author.mention}: Anagram is not running here. '
                           f'Start a game by saying `{ctx.prefix}hangman start`.',
                           delete_after=10)


class Anagram(GameCogBase):
    gamecls = AnagramGame

    def cog_check(self, ctx):
        return self._local_check(ctx)

    @commands.group(case_insensitive=True)
    async def anagram(self, ctx: commands.Context):
        """Play Anagram"""
        if ctx.invoked_subcommand is None:
            await ctx.send(f'Incorrect anagram subcommand passed. '
                           f'Try `{ctx.prefix}{self.bot.settings.help_name} anagram`')

    @anagram.command()
    async def start(self, ctx: commands.Context):
        """Start a game in the current channel"""
        await self.game_cmd('start', ctx)

    @commands.command(name='anastart', aliases=['ast'])
    async def anagram_start(self, ctx):
        """Start a game in the current channel"""
        await ctx.invoke(self.start)

    @anagram.command()
    async def solve(self, ctx: commands.Context, *guess: str):
        """Make a guess, if you dare"""
        await self.game_cmd('solve', ctx, *guess)

    @commands.command(name='anasolve', aliases=['aso'])
    async def anagram_solve(self, ctx, *guess: str):
        """Make a guess, if you dare"""
        await ctx.invoke(self.solve, *guess)

    @anagram.command()
    @commands.is_owner()
    async def end(self, ctx: commands.Context):
        """End the game as a loss (owner only)"""
        await self.game_cmd('end', ctx, aborted=True)

    @commands.command(name='anaend', aliases=['ae'])
    @commands.is_owner()
    async def anagram_end(self, ctx):
        """End the game as a loss (owner only)"""
        await ctx.invoke(self.end)

    @anagram.command()
    async def show(self, ctx):
        """Show the board in a new message"""
        await self.game_cmd('show', ctx)

    @commands.command(name='anashow', aliases=['ash'])
    async def anagram_show(self, ctx):
        """Show the board in a new message"""
        await ctx.invoke(self.show)

    async def cog_command_error(self, ctx, exc):
        await self._error(ctx, exc)


def setup(bot):
    bot.add_cog(Anagram(bot))
