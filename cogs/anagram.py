import asyncio
import discord
import random
from utils.data import data
from discord.ext import commands
from bot import log
import time


class AnagramGame:
    def __init__(self, bot, attempts=3):
        self.bot = bot
        self._attempts = attempts
        self._timeout = 90
        self.reset()

    def reset(self):
        self._running = False
        self._state = ''
        self._solution = ''
        self._incorrect = []
        self.attempts = 0
        self._message = None
        self._task = None

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
            self.running = True
            await ctx.send(f'Anagram has started! You have {self.attempts:d} attempts and {self._timeout:d} seconds '
                           f'to guess correctly before OLDEN corrupts your save.\n')
            self._message = await ctx.send(self.show())
            self._task = discord.compat.create_task(self.timeout(ctx), loop=self.bot.loop)

    async def timeout(self, ctx:commands.Context):
        await asyncio.sleep(self._timeout)
        if self.running:
            await ctx.send('Time\'s up!')
            discord.compat.create_task(self.end(ctx, failed=True))
            self._task = None

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
                await ctx.send(f'You were too late, welcome to Glitch Purgatory.\n'
                               f'Solution: {self._solution}')
            else:
                await ctx.send(f'{ctx.author.mention} has solved the puzzle!\n'
                               f'Solution: {self._solution}')
            self.reset()
        else:
            await ctx.send(f'{ctx.author.mention}: Anagram is not running here. '
                           f'Start a game by saying `{ctx.prefix}anagram start`.',
                           delete_after=10)

    async def guess(self, ctx: commands.Context, guess):
        if self.running:
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
        if self.running:
            await self._message.delete()
            self._message = await ctx.send(self.show())
        else:
            await ctx.send(f'{ctx.author.mention}: Hangman is not running here. '
                           f'Start a game by saying `{ctx.prefix}hangman start`.',
                           delete_after=10)


class Anagram:
    def __init__(self, bot):
        self.bot = bot
        self.channels = {}

    @commands.group(pass_context=True)
    async def anagram(self, ctx: commands.Context):
        f"""Play Anagram"""
        if ctx.invoked_subcommand is None:
            await ctx.send(f'Incorrect anagram subcommand passed. Try `{ctx.prefix}help anagram`')
        if ctx.channel.id not in self.channels:
            self.channels[ctx.channel.id] = AnagramGame(self.bot)

    @anagram.command()
    async def start(self, ctx: commands.Context):
        """Start a game in the current channel"""
        await self.channels[ctx.channel.id].start(ctx)

    @anagram.command()
    async def solve(self, ctx: commands.Context, guess: str):
        """Make a guess, if you dare"""
        await self.channels[ctx.channel.id].guess(ctx, guess)

    @anagram.command()
    async def end(self, ctx: commands.Context):
        """End the game as a loss (owner only)"""
        if await self.bot.is_owner(ctx.author):
            await self.channels[ctx.channel.id].end(ctx, aborted=True)

    @anagram.command()
    async def show(self, ctx):
        """Show the board in a new message"""
        await self.channels[ctx.channel.id].show_(ctx)


def setup(bot):
    bot.add_cog(Anagram(bot))
