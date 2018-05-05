import asyncio
import discord
import random
from utils.data import data
from discord.ext import commands


class HangmanGame:
    def __init__(self, bot, attempts=8):
        self.bot = bot
        self._attempts = attempts
        self.reset()

    def reset(self):
        self._running = False
        self._state = []
        self._solution = ''
        self._incorrect = []
        self.attempts = 0

    @property
    def state(self):
        return ' '.join(self._state)

    @property
    def incorrect(self):
        return ', '.join(self._incorrect)

    @property
    def running(self):
        return self._running

    @running.setter
    def running(self, state):
        self._running = state

    async def start(self, ctx):
        if self.running:
            await ctx.send(f'{ctx.author.mention}: Hangman is already running here.')
        else:
            self._solution = random.choice(data.pokemon)
            self._state = ['_' for c in self._solution]
            self.attempts = self._attempts
            self._incorrect = []
            self.running = True
            await ctx.send(f'Hangman has started! You have {self.attempts:d} attempts to guess correctly before '
                           f'the man dies!\n'
                           f'Puzzle: {self.state} | Incorrect: [{self.incorrect}]')

    async def end(self, ctx, failed=False):
        if self.running:
            if failed:
                await ctx.send(f'You were too late, the man has hanged to death.\n'
                               f'Solution: {self._solution}')
            else:
                await ctx.send(f'{ctx.author.mention} has solved the puzzle!\n'
                               f'Solution: {self._solution}')
            self.reset()
        else:
            await ctx.send(f'{ctx.author.mention}: Hangman is not running here.')

    async def guess(self, ctx, guess):
        if self.running:
            guess = guess.upper()
            if guess in self._incorrect or guess in self._state:
                await ctx.send(f'Character or solution already guessed: {guess}')
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
                await ctx.send(f'Puzzle: {self.state} | Incorrect: [{self.incorrect}]')
                if self.attempts == 0:
                    await self.end(ctx, True)
        else:
            await ctx.send(f'{ctx.author.mention}: Hangman is not running here.')


class Hangman:
    def __init__(self, bot, attempts=8):
        self.bot = bot
        self._attempts = attempts
        self.channels = {}

    @commands.group(pass_context=True)
    async def hangman(self, ctx):
        """Play Hangman"""
        if ctx.invoked_subcommand is None:
            await ctx.send(f'Incorrect hangman subcommand passed. Try {ctx.prefix}help hangman')
        if ctx.channel.id not in self.channels:
            self.channels[ctx.channel.id] = HangmanGame(self.bot, self._attempts)

    @hangman.command()
    async def start(self, ctx):
        """Start a game in the current channel"""
        await self.channels[ctx.channel.id].start(ctx)

    @hangman.command()
    async def guess(self, ctx, guess):
        """Guess a letter or solve the puzzle"""
        await self.channels[ctx.channel.id].guess(ctx, guess)

    @hangman.command()
    async def end(self, ctx):
        """End the game as a loss (owner only)"""
        if self.bot.is_owner(ctx.author):
            await self.channels[ctx.channel.id].end(ctx, True)


def setup(bot):
    bot.add_cog(Hangman(bot))
