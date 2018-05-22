import asyncio
import discord
import random
from utils.data import data
from utils import sql
from utils.game import GameBase
from discord.ext import commands


class HangmanGame(GameBase):
    def __init__(self, bot, attempts=8):
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

    def show(self):
        return f'```Puzzle: {self.state}\n' \
               f'Incorrect: [{self.incorrect}]\n' \
               f'Remaining: {self.attempts:d}```'

    async def start(self, ctx: commands.Context):
        if self.running:
            await ctx.send(f'{ctx.author.mention}: Hangman is already running here.',
                           delete_after=10)
        else:
            self._solution = random.choice(data.pokemon)
            self._state = ['_' for c in self._solution]
            self.attempts = self._attempts
            self._incorrect = []
            await ctx.send(f'Hangman has started! You have {self.attempts:d} attempts and {self._timeout:d} seconds '
                           f'to guess correctly before the man dies!')
            await super().start(ctx)

    async def end(self, ctx: commands.Context, failed=False, aborted=False):
        if self.running:
            if self._task and not self._task.done():
                self._task.cancel()
                self._task = None
            await self._message.edit(content=self.show())
            if aborted:
                await ctx.send(f'Game terminated by {ctx.author.mention}.\n'
                               f'Solution: {self._solution}')
            elif failed:
                await ctx.send(f'You were too late, the man has hanged to death.\n'
                               f'Solution: {self._solution}')
            else:
                await ctx.send(f'{ctx.author.mention} has solved the puzzle!\n'
                               f'Solution: {self._solution}\n'
                               f'Congratulations to all the players! You each earn {self.award_points(ctx):d} points!')
            self.reset()
        else:
            await ctx.send(f'{ctx.author.mention}: Hangman is not running here. '
                           f'Start a game by saying `{ctx.prefix}hangman start`.',
                           delete_after=10)

    async def guess(self, ctx: commands.Context, guess: str):
        if self.running:
            self.add_player(ctx)
            guess = guess.upper()
            if guess in self._incorrect or guess in self._state:
                await ctx.send(f'{ctx.author.mention}: Character or solution already guessed: {guess}',
                               delete_after=10)
            elif len(guess) == 1:
                found = False
                for i, c in enumerate(self._solution):
                    if c == guess:
                        self._state[i] = guess
                        found = True
                if found:
                    if ''.join(self._state) == self._solution:
                        await self.end(ctx)
                else:
                    self._incorrect.append(guess)
                    self.attempts -= 1
            else:
                if self._solution == guess:
                    self._state = list(self._solution)
                    await self.end(ctx)
                else:
                    self._incorrect.append(guess)
                    self.attempts -= 1
            if self.running:
                await self._message.edit(content=self.show())
                if self.attempts == 0:
                    await self.end(ctx, True)
        else:
            await ctx.send(f'{ctx.author.mention}: Hangman is not running here. '
                           f'Start a game by saying `{ctx.prefix}hangman start`.',
                           delete_after=10)

    async def show_(self, ctx):
        if await super().show_(ctx) is None:
            await ctx.send(f'{ctx.author.mention}: Hangman is not running here. '
                           f'Start a game by saying `{ctx.prefix}hangman start`.',
                           delete_after=10)


class Hangman:
    def __init__(self, bot):
        self.bot = bot
        self.channels = {}

    @commands.group(pass_context=True, case_insensitive=True)
    async def hangman(self, ctx):
        """Play Hangman"""
        if ctx.invoked_subcommand is None:
            await ctx.send(f'Incorrect hangman subcommand passed. Try `{ctx.prefix}pikahelp hangman`')
        if ctx.channel.id not in self.channels:
            self.channels[ctx.channel.id] = HangmanGame(self.bot)

    @hangman.command()
    async def start(self, ctx):
        """Start a game in the current channel"""
        game = self.channels[ctx.channel.id]
        async with game._lock:
            await game.start(ctx)

    @hangman.command()
    async def guess(self, ctx, guess):
        """Make a guess, if you dare"""
        game = self.channels[ctx.channel.id]
        async with game._lock:
            await game.guess(ctx, guess)

    @hangman.command()
    async def end(self, ctx):
        """End the game as a loss (owner only)"""
        if await self.bot.is_owner(ctx.author):
            game = self.channels[ctx.channel.id]
            async with game._lock:
                await game.end(ctx, aborted=True)

    @hangman.command()
    async def show(self, ctx):
        """Show the board in a new message"""
        game = self.channels[ctx.channel.id]
        async with game._lock:
            await game.show_(ctx)


def setup(bot):
    bot.add_cog(Hangman(bot))
