import asyncio
import discord
from discord.ext import commands
from utils.game import GameBase
from utils import sql
import random


class VoltorbFlipGame(GameBase):
    ONE = 1
    TWO = 2
    THR = 3
    FLG = 4
    RVL = 8
    VTB = 16

    def __init__(self, bot):
        super().__init__(bot, timeout=180)

    def reset(self):
        super().reset()
        self._state = [[1 for x in range(5)] for y in range(5)]
        self._score = 0
        self._level = 1
        self._players = set()

    def is_flagged(self, x, y):
        return self.state[y][x] & self.FLG

    def is_revealed(self, x, y):
        return self.state[y][x] & self.RVL

    def is_bomb(self, x, y):
        return self.state[y][x] & self.VTB

    def coin_value(self, x, y):
        return self.state[y][x] & 3

    def colsum(self, x, do_coins=True):
        return sum((self.coin_value if do_coins else self.is_bomb)(x, y) for y in range(5))

    def rowsum(self, y, do_coins=True):
        return sum((self.coin_value if do_coins else self.is_bomb)(x, y) for x in range(5))

    def set_flag(self, x, y):
        self.state[y][x] |= self.FLG

    def clear_flag(self, x, y):
        self.state[y][x] &= ~self.FLG

    def set_revealed(self, x, y):
        self.state[y][x] |= self.RVL

    def set_coins(self, x, y, coins):
        self.state[y][x] &= ~3
        self.state[y][x] |= coins

    def get_coin_total(self, condition=lambda x, y: True):
        res = 1
        for y in range(5):
            for x in range(5):
                if condition(x, y):
                    res *= self.coin_value(x, y)
        return res

    def get_revealed_coins(self):
        return self.get_coin_total(self.is_revealed)

    @property
    def score(self):
        return self.get_coin_total() / len(self._players)

    def build_board(self):
        minmax = (20, 50, 100, 200, 500, 1000, 2000, 3000, 5000, 7000, 10000)
        _min = minmax[self._level - 1]
        _max = minmax[self._level]
        _num_voltorb = 6 + self._level // 2
        self._state = [[1 for x in range(5)] for y in range(5)]
        for i in range(_num_voltorb):
            y, x = divmod(random.randrange(25), 5)
            while self.is_bomb(x, y):
                y, x = divmod(random.randrange(25), 5)
            self._state[y][x] |= self.VTB
        while not _min <= self.get_coin_total() <= _max:
            for i in range(25):
                y, x = divmod(i, 5)
                if self.is_bomb(x, y):
                    self.set_coins(x, y, 1)
                else:
                    rv = random.random()
                    if rv < .8 - 0.05 * self._level:
                        self.set_coins(x, y, 1)
                    elif rv < 0.96 - 0.04 * self._level:
                        self.set_coins(x, y, 2)
                    else:
                        self.set_coins(x, y, 3)

    def found_all_coins(self):
        return self.get_revealed_coins() == self.get_coin_total()

    def reveal_all(self):
        for y in range(5):
            for x in range(5):
                self.set_revealed(x, y)

    def get_element_char(self, x, y):
        if self.is_flagged(x, y):
            return ':triangular_flag_on_post:'
        if self.is_revealed(x, y):
            return (':bomb:', ':one:', ':two:', ':three:')[self.coin_value(x, y)]
        return ':white_square_button:'

    def show(self):
        colbombcounts = [f':bomb:{self.colsum(x):d}' for x in range(5)]
        colcoincounts = [f'x{self.colsum(x, True):d}' for x in range(5)]
        rowbombcounts = [f':bomb:{self.rowsum(y):d}' for y in range(5)]
        rowcoincounts = [f'x{self.rowsum(y, True):d}' for y in range(5)]
        state = f'LEVEL: {self._level}\n' \
                f'BOARD STATE:'
        state += '{}|{}|{}|{}|{}\n'.format(*colbombcounts)
        state += '{}|{}|{}|{}|{}\n'.format(*colcoincounts)
        for y in range(5):
            state += ''.join(self.get_element_char(x, y) for x in range(5))
            state += '|{}|{}\n'.format(rowbombcounts[y], rowcoincounts[y])
        state += f'SCORE: {self._score:d}'
        return state

    async def start(self, ctx):
        if self.running:
            await ctx.send(f'{ctx.author.mention}: Voltorb Flip is already running here.',
                           delete_after=10)
        else:
            self._players = set()
            self._score = 1
            self.build_board()
            await ctx.send(f'New game of Voltorb Flip! Use `{ctx.prefix}voltorb guess x y` to reveal a square!')
            await self.show_(ctx)

    async def end(self, ctx: commands.Context, failed=False, aborted=False):
        if self.running:
            self.reveal_all()
            await self._message.edit(content=self.show())
            if aborted:
                await ctx.send(f'Game terminated by {ctx.author.mention}')
            elif failed:
                await ctx.send(f'Game over. You win 0 coins.')
                self._level = max(self._level - 1, 1)
            else:
                score = self.score
                await ctx.send(f'Congratulations to all the players! You each earn {score:d} points!')
                author = ctx.author
                for player in self._players:
                    ctx.message.author = ctx.guild.get_member(player)
                    sql.increment_score(ctx, by=score)
                ctx.message.author = author
                self._level = min(self._level + 1, 10)
            self.reset()
        else:
            await ctx.send(f'{ctx.author.mention}: Voltorb flip is not running here. '
                           f'Start a game by saying `{ctx.prefix}voltorb start`.',
                           delete_after=10)

    async def guess(self, ctx, x: int, y: int):
        self._players.add(ctx.author.id)
        if self.is_bomb(x, y):
            await ctx.send('KAPOW')
            await self.end(ctx, failed=True)
        else:
            self.set_revealed(x, y)
            multiplier = self.coin_value(x, y)
            if multiplier > 1:
                self._score *= multiplier
                await ctx.send(f'Got x{multiplier:d}!', delete_after=10)
            await self._message.edit(content=self.show())
            if self.found_all_coins():
                await self.end(ctx)

    async def flag(self, ctx, x: int, y: int):
        self._players.add(ctx.author.id)
        (self.clear_flag if self.is_flagged(x, y) else self.set_flag)(x, y)
        await self._message.edit(content=self.show())

    async def show_(self, ctx):
        if await super().show_(ctx) is None:
            await ctx.send()


class VoltorbFlip:
    def __init__(self, bot):
        self.bot = bot
        self.channels = {}

    @commands.group(pass_context=True)
    async def voltorb(self, ctx):
        """Play Voltorb Flip"""
        if ctx.invoked_subcommand is None:
            await ctx.send(f'Incorrect voltorb subcommand passed')
        if ctx.channel.id not in self.channels:
            self.channels[ctx.channel.id] = VoltorbFlipGame(self.bot)

    @voltorb.command()
    async def start(self, ctx):
        """Start a game of Voltorb Flip"""
        game = self.channels[ctx.channel.id]
        async with game._lock:
            await game.start(ctx)

    @voltorb.command()
    async def guess(self, ctx, x: int, y: int):
        """Reveal a square and either claim its coins or blow it up"""
        if 1 <= x <= 5 and 1 <= y <= 5:
            game = self.channels[ctx.channel.id]
            async with game._lock:
                await game.guess(ctx, x - 1, y - 1)
        else:
            await ctx.send(f'{ctx.author.mention}: Invalid coordinates given')

    @voltorb.command()
    async def flag(self, ctx, x: int, y: int):
        """Flag a square"""
        if 1 <= x <= 5 and 1 <= y <= 5:
            game = self.channels[ctx.channel.id]
            async with game._lock:
                await game.flag(ctx, x - 1, y - 1)
        else:
            await ctx.send(f'{ctx.author.mention}: Invalid coordinates given')

    @voltorb.command()
    async def end(self, ctx):
        """End the game as a loss (owner only)"""
        if await self.bot.is_owner(ctx.author):
            game = self.channels[ctx.channel.id]
            async with game._lock:
                await game.end(ctx, aborted=True)

    @voltorb.command()
    async def show(self, ctx):
        """Show the board in a new message"""
        game = self.channels[ctx.channel.id]
        async with game._lock:
            await game.show_(ctx)


def setup(bot):
    bot.add_cog(VoltorbFlip(bot))
