import asyncio
import discord
import math
import random
from utils.data import data
from utils.game import GameBase
from utils import sql
from discord.ext import commands


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

    def show(self):
        return f'```Puzzle: {self.state}\n' \
               f'Incorrect: [{self.incorrect}]\n' \
               f'Remaining: {self.attempts:d}```'

    async def start(self, ctx: commands.Context):
        if self.running:
            await ctx.send(f'{ctx.author.mention}: Anagram is already running here.',
                           delete_after=10)
        else:
            self._solution = random.choice(data.pokemon)
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
            await self._message.edit(content=self.show())
            if aborted:
                await ctx.send(f'Game terminated by {ctx.author.mention}.\n'
                               f'Solution: {self._solution}')
            elif failed:
                await ctx.send(f'You were too late, welcome to Glitch Purgatory.\n'
                               f'Solution: {self._solution}')
            else:
                bonus = math.ceil(self._max_score / 10)
                sql.increment_score(ctx.author, bonus)
                await ctx.send(f'{ctx.author.mention} has solved the puzzle!\n'
                               f'Solution: {self._solution}\n'
                               f'Congratulations to all the players! You each earn {self.award_points():d} points!\n'
                               f'{ctx.author.mention} gets an extra {bonus} points for solving the puzzle!')
            self.reset()
        else:
            await ctx.send(f'{ctx.author.mention}: Anagram is not running here. '
                           f'Start a game by saying `{ctx.prefix}anagram start`.',
                           delete_after=10)

    async def guess(self, ctx: commands.Context, guess):
        if self.running:
            self.add_player(ctx.author)
            guess = guess.upper()
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
                await self._message.edit(content=self.show())
                if self.attempts == 0:
                    await self.end(ctx, True)
        else:
            await ctx.send(f'{ctx.author.mention}: Anagram is not running here. '
                           f'Start a game by saying `{ctx.prefix}anagram start`.',
                           delete_after=10)

    async def show_(self, ctx):
        if await super().show_(ctx) is None:
            await ctx.send(f'{ctx.author.mention}: Hangman is not running here. '
                           f'Start a game by saying `{ctx.prefix}hangman start`.',
                           delete_after=10)


class Anagram:
    def __init__(self, bot):
        self.bot = bot
        self.channels = {}

    @commands.group(pass_context=True, case_insensitive=True)
    async def anagram(self, ctx: commands.Context):
        """Play Anagram"""
        if ctx.invoked_subcommand is None:
            await ctx.send(f'Incorrect anagram subcommand passed. Try `{ctx.prefix}pikahelp anagram`')
        if ctx.channel.id not in self.channels:
            self.channels[ctx.channel.id] = AnagramGame(self.bot)

    @anagram.command()
    async def start(self, ctx: commands.Context):
        """Start a game in the current channel"""
        game = self.channels[ctx.channel.id]
        async with game._lock:
            await game.start(ctx)

    @anagram.command()
    async def solve(self, ctx: commands.Context, guess: str):
        """Make a guess, if you dare"""
        game = self.channels[ctx.channel.id]
        async with game._lock:
            await game.guess(ctx, guess)

    @anagram.command()
    async def end(self, ctx: commands.Context):
        """End the game as a loss (owner only)"""
        if await self.bot.is_owner(ctx.author):
            game = self.channels[ctx.channel.id]
            async with game._lock:
                await game.end(ctx, aborted=True)

    @anagram.command()
    async def show(self, ctx):
        """Show the board in a new message"""
        game = self.channels[ctx.channel.id]
        async with game._lock:
            await game.show_(ctx)


def setup(bot):
    bot.add_cog(Anagram(bot))
