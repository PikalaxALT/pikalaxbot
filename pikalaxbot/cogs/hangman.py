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

import math

from discord.ext import commands

from .utils.game import GameBase, GameCogBase, Game, GameStartCommand
from . import *


class HangmanGame(GameBase):
    def __init__(self, bot, attempts=8):
        super().__init__(bot)
        self._attempts = attempts
        self._solution_name = ''
        self._incorrect: list[str] = []
        self.attempts = 0

    def reset(self):
        super().reset()
        self._state: list[str] = []
        self._solution = None
        self._solution_name = ''
        self._incorrect.clear()
        self.attempts = 0

    @property
    def incorrect(self):
        return ', '.join(self._incorrect)

    @property
    def state(self):
        return ' '.join(self._state)

    def __str__(self):
        return f'```Puzzle: {self.state}\n' \
               f'Incorrect: [{self.incorrect}]\n' \
               f'Remaining: {self.attempts:d}\n' \
               f'Players: {self.get_player_names()}```'

    async def start(self, ctx):
        if self.running:
            await ctx.send(f'{ctx.author.mention}: Hangman is already running here.',
                           delete_after=10)
        else:
            self._solution = await self.bot.pokeapi.random_pokemon()
            self._solution_name = self.bot.pokeapi.get_name(self._solution, clean=True).upper()
            self._state = ['_' if c.isalnum() else c for c in self._solution_name]
            self.attempts = self._attempts
            self._incorrect.clear()
            await ctx.send(f'Hangman has started! You have {self.attempts:d} attempts and {self._timeout:d} seconds '
                           f'to guess correctly before the man dies!')
            await super().start(ctx)

    async def end(self, ctx: MyContext, failed=False, aborted=False):
        if self.running:
            if self.task:
                self.task.cancel()
                self.task = None
            await self._message.edit(content=self)
            embed = await self.get_solution_embed(failed=failed, aborted=aborted)
            if aborted:
                await ctx.send(f'Game terminated by {ctx.author.mention}.\n'
                               f'Solution: {self._solution_name}',
                               embed=embed)
            elif failed:
                await ctx.send(f'You were too late, the man has hanged to death.\n'
                               f'Solution: {self._solution_name}',
                               embed=embed)
            else:
                bonus = math.ceil(self._max_score / 10)
                async with self.bot.sql as sql:
                    await Game.increment_score(sql, ctx.author, by=bonus)
                score = await self.award_points()
                await ctx.send(f'{ctx.author.mention} has solved the puzzle!\n'
                               f'Solution: {self._solution_name}\n'
                               f'The following players each earn {score:d} points:\n'
                               f'```{self.get_player_names()}```\n'
                               f'{ctx.author.mention} gets an extra {bonus} points for solving the puzzle!',
                               embed=embed)
            self.reset()
        else:
            await ctx.send(f'{ctx.author.mention}: Hangman is not running here. '
                           f'Start a game by saying `{ctx.prefix}hangman start`.',
                           delete_after=10)

    async def guess(self, ctx: MyContext, *, guess: str):
        if self.running:
            guess = guess.upper()
            if guess in self._incorrect or guess in self._state:
                await ctx.send(f'{ctx.author.mention}: Character or solution already guessed: {guess}',
                               delete_after=10)
            elif len(guess) == 1:
                if guess in self._solution_name:
                    for i, _ in filter(lambda t: guess == t[1], enumerate(self._solution_name)):
                        self._state[i] = guess
                    self.add_player(ctx.author)
                    if ''.join(self._state) == self._solution_name:
                        await self.end(ctx)
                else:
                    self._incorrect.append(guess)
                    self.attempts -= 1
            else:
                if self._solution_name == guess:
                    self.add_player(ctx.author)
                    self._state = list(self._solution_name)
                    await self.end(ctx)
                else:
                    self._incorrect.append(guess)
                    self.attempts -= 1
            if self.running:
                await self._message.edit(content=self)
                if self.attempts == 0:
                    await self.end(ctx, True)
        else:
            await ctx.send(f'{ctx.author.mention}: Hangman is not running here. '
                           f'Start a game by saying `{ctx.prefix}hangman start`.',
                           delete_after=10)

    async def show(self, ctx):
        if await super().show(ctx) is None:
            await ctx.send(f'{ctx.author.mention}: Hangman is not running here. '
                           f'Start a game by saying `{ctx.prefix}hangman start`.',
                           delete_after=10)


class Hangman(GameCogBase[HangmanGame]):
    """Commands for playing a game of Pokemon Hangman.

    All commands are under the `hangman` group, or you can use one
    of the shortcuts below."""

    def cog_check(self, ctx: MyContext):
        return self._local_check(ctx) and ctx.bot.pokeapi is not None

    @commands.group(case_insensitive=True, invoke_without_command=True)
    async def hangman(self, ctx):
        """Play Hangman"""
        await ctx.send_help(ctx.command)

    @hangman.command(cls=GameStartCommand)
    async def start(self, ctx: MyContext):
        """Start a game in the current channel"""
        await self.game_cmd('start', ctx)

    @commands.command(name='hangstart', aliases=['hst'], cls=GameStartCommand)
    async def hangman_start(self, ctx: MyContext):
        """Start a game in the current channel"""
        await self.start(ctx)

    @hangman.command()
    async def guess(self, ctx: MyContext, *, guess: str):
        """Make a guess, if you dare"""
        await self.game_cmd('guess', ctx, guess=guess)

    @commands.command(name='hangguess', aliases=['hgu', 'hg'])
    async def hangman_guess(self, ctx: MyContext, *, guess: str):
        """Make a guess, if you dare"""
        await self.guess(ctx, guess=guess)

    @hangman.command()
    @commands.is_owner()
    async def end(self, ctx: MyContext):
        """End the game as a loss (owner only)"""
        await self.game_cmd('end', ctx, aborted=True)

    @commands.command(name='hangend', aliases=['he'])
    @commands.is_owner()
    async def hangman_end(self, ctx: MyContext):
        """End the game as a loss (owner only)"""
        await self.end(ctx)

    @hangman.command()
    async def show(self, ctx: MyContext):
        """Show the board in a new message"""
        await self.game_cmd('show', ctx)

    @commands.command(name='hangshow', aliases=['hsh'])
    async def hangman_show(self, ctx):
        """Show the board in a new message"""
        await self.show(ctx)

    async def cog_command_error(self, ctx: MyContext, exc: commands.CommandError):
        await self._error(ctx, exc)


def setup(bot: PikalaxBOT):
    bot.add_cog(Hangman(bot))
