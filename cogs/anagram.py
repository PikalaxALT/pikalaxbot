import asyncio
import discord
import random
from utils.data import data
from discord.ext import commands
from bot import log


class AnagramGame():
    def __init__(self, bot, attempts=3):
        self.bot = bot
        self._attempts = attempts
        self.reset()

    def reset(self):
        self._running = False
        self._state = ''
        self._solution = ''
        self._incorrect = []
        self.attempts = 0
        self._message = None

    @property
    def state(self):
        return self._state

    @property
    def incorrect(self):
        return ', '.join(self._incorrect)

    @property
    def running(self):
        return self._running

    @running.setter
    def running(self, state):
        self._running = state

    def show(self):
        return f'```Puzzle: {self.state}\n' \
               f'Incorrect: [{self.incorrect}]\n' \
               f'Remaining: {self.attempts:d}```'

    async def start(self, ctx):
        if self.running:
            await ctx.author.send(f'Anagram is already running in {ctx.channel.mention}.')
        else:
            self._solution = random.choice(data.pokemon)
            self._state = list(self._solution)
            while ''.join(self._state) == self._solution:
                random.shuffle(self._state)
            self._state = ''.join(self._state)
            self.attempts = self._attempts
            self._incorrect = []
            self.running = True
            await ctx.send(f'Anagram has started! You have {self.attempts:d} attempts to guess correctly before '
                           f'OLDEN corrupts your save.\n')
            self._message = await ctx.send(f'{self.show()}')

    async def end(self, ctx, failed=False, aborted=False):
        await self._message.edit(content=f'{self.show()}')
        if self.running:
            if aborted:
                await ctx.send(f'Game terminated by {ctx.author.mention}.\n'
                               f'Solution: {self._solution}')
            elif failed:
                await ctx.send(f'You were too late, welcome to Glitch Purgatory.\n'
                               f'Solution: {self._solution}')
            else:
                await ctx.send(f'{ctx.author.mention} has solved the puzzle!\n'
                               f'Solution: {self._solution}')
            self.reset()
        else:
            await ctx.author.send(f'Anagram is not running in {ctx.channel.mention}.')

    async def guess(self, ctx, guess):
        if self.running:
            guess = guess.upper()
            if guess in self._incorrect:
                await ctx.author.send(f'Solution already guessed: {guess}')
            else:
                if self._solution == guess:
                    self._state = self._solution
                    await self.end(ctx)
                else:
                    self._incorrect.append(guess)
                    self.attempts -= 1
            if self.running:
                await self._message.edit(content=f'{self.show()}')
                if self.attempts == 0:
                    await self.end(ctx, True)
        else:
            await ctx.author.send(f'Anagram is not running in {ctx.channel.mention}.')


class Anagram():
    def __init__(self, bot):
        self.bot = bot
        self.channels = {}

    @commands.group(pass_context=True)
    async def anagram(self, ctx):
        f"""Play Anagram"""
        if ctx.invoked_subcommand is None:
            await ctx.send(f'Incorrect anagram subcommand passed. Try {ctx.prefix}help game')
        if ctx.channel.id not in self.channels:
            self.channels[ctx.channel.id] = AnagramGame(self.bot)

    @anagram.command()
    async def start(self, ctx):
        """Start a game in the current channel"""
        await self.channels[ctx.channel.id].start(ctx)

    @anagram.command()
    async def solve(self, ctx, guess):
        """Make a guess, if you dare"""
        await self.channels[ctx.channel.id].guess(ctx, guess)

    @anagram.command()
    async def end(self, ctx):
        """End the game as a loss (owner only)"""
        if self.bot.is_owner(ctx.author):
            await self.channels[ctx.channel.id].end(ctx, aborted=True)


def setup(bot):
    bot.add_cog(Anagram(bot))
