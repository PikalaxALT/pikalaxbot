import asyncio
import discord
from discord.ext import commands
from utils.game import GameBase, GameCogBase, find_emoji
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
        self._level = None
        super().__init__(bot, timeout=180)

    def reset(self):
        super().reset()
        self._state = [[1 for x in range(5)] for y in range(5)]
        self._score = 0
        self._ended = False

    def is_flagged(self, x, y):
        return self.state[y][x] & self.FLG

    def is_revealed(self, x, y):
        return self.state[y][x] & self.RVL

    def is_bomb(self, x, y):
        return self.state[y][x] & self.VTB != 0

    def coin_value(self, x, y):
        return self.state[y][x] & 3

    def non_bomb_coin_value(self, x, y):
        return 0 if self.is_bomb(x, y) else self.coin_value(x, y)

    def colsum(self, x, do_coins=False):
        return sum((self.non_bomb_coin_value if do_coins else self.is_bomb)(x, y) for y in range(5))

    def rowsum(self, y, do_coins=False):
        return sum((self.non_bomb_coin_value if do_coins else self.is_bomb)(x, y) for x in range(5))

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
        return self.get_coin_total()
    
    @property
    def level(self):
        return self._level
    
    def get_level(self, channel):
        self._level = sql.get_voltorb_level(channel)
        return self._level

    def update_level(self, channel, new_level):
        self._level = new_level
        sql.set_voltorb_level(channel, new_level)

    def build_board(self):
        minmax = (20, 50, 100, 200, 500, 1000, 2000, 3000, 5000, 7000, 10000)
        _min = minmax[self.level - 1]
        _max = minmax[self.level]
        _num_voltorb = 6 + self.level // 2
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
                    if rv < .8 - 0.05 * self.level:
                        self.set_coins(x, y, 1)
                    elif rv < 0.96 - 0.04 * self.level:
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
        if self.is_revealed(x, y):
            idx = 0 if self.is_bomb(x, y) else self.coin_value(x, y)
            return (':bomb:', ':one:', ':two:', ':three:')[idx]
        if self.is_flagged(x, y):
            return ':triangular_flag_on_post:'
        return ':white_square_button:'

    def __str__(self):
        colbombcounts = [f':bomb:{self.colsum(x):d}' for x in range(5)]
        colcoincounts = [f'x{self.colsum(x, True):d}' for x in range(5)]
        rowbombcounts = [f':bomb:{self.rowsum(y):d}' for y in range(5)]
        rowcoincounts = [f'x{self.rowsum(y, True):d}' for y in range(5)]
        state = f'LEVEL: {self.level}\n' \
                f'BOARD STATE:\n'
        state += '{}|{}|{}|{}|{}\n'.format(*colbombcounts)
        state += ' {} | {} | {} | {} | {}\n'.format(*colcoincounts)
        for y in range(5):
            state += ''.join(self.get_element_char(x, y) for x in range(5))
            state += ' | {} | {}\n'.format(rowbombcounts[y], rowcoincounts[y])
        state += f'SCORE: {0 if self._ended else self._score:d}'
        return state

    async def start(self, ctx):
        if self.running:
            await ctx.send(f'{ctx.author.mention}: Voltorb Flip is already running here.',
                           delete_after=10)
        else:
            if self.level is None:
                self._level = self.get_level(ctx.channel)
            self._players = set()
            self._score = 1
            self.build_board()
            await ctx.send(f'New game of Voltorb Flip! Use `{ctx.prefix}voltorb guess y x` to reveal a square, '
                           f'`{ctx.prefix}voltorb flag y x` to flag a square. You have {self._timeout} seconds '
                           f'to find all the coins!')
            await super().start(ctx)

    async def end(self, ctx: commands.Context, failed=False, aborted=False):
        if await super().end(ctx, failed=failed, aborted=aborted):
            new_level = self.level
            self.reveal_all()
            await self._message.edit(content=self)
            if aborted:
                await ctx.send(f'Game terminated by {ctx.author.mention}')
            elif failed:
                self._ended = True
                await ctx.send(f'Game over. You win 0 coins.')
                new_level = max(new_level - 1, 1)
            else:
                await ctx.send(f'The following players each earn {self.award_points():d} points:\n'
                               f'```{self.get_player_names()}```')
                new_level = min(new_level + 1, 10)
            if new_level != self.level:
                await ctx.send(f'The game level {"rose" if new_level > self.level else "fell"} to {new_level:d}!')
                self.update_level(ctx.channel, new_level)
            self.reset()
        else:
            await ctx.send(f'{ctx.author.mention}: Voltorb Flip is not running here. '
                           f'Start a game by saying `{ctx.prefix}voltorb start`.',
                           delete_after=10)

    async def guess(self, ctx: commands.Context, x: int, y: int):
        if self.running:
            if self.is_bomb(x, y):
                await ctx.send('KAPOW')
                await self.end(ctx, failed=True)
            elif self.is_revealed(x, y):
                await ctx.send(f'{ctx.author.mention}: Tile already revealed.',
                               delete_after=10)
            else:
                self.add_player(ctx.author)
                self.set_revealed(x, y)
                multiplier = self.coin_value(x, y)
                if multiplier > 1:
                    self._score *= multiplier
                    await ctx.send(f'Got x{multiplier:d}!', delete_after=10)
                    emoji = find_emoji(ctx.guild, 'PogChamp', case_sensitive=False)
                    await ctx.message.add_reaction(emoji)
                await self._message.edit(content=self.__str__())
                if self.found_all_coins():
                    await self.end(ctx)
        else:
            await ctx.send(f'{ctx.author.mention}: Voltorb Flip is not running here. '
                           f'Start a game by saying `{ctx.prefix}voltorb start`.',
                           delete_after=10)

    async def flag(self, ctx, x: int, y: int):
        if self.running:
            if self.is_revealed(x, y):
                await ctx.send(f'{ctx.author.mention}: Tile already revealed',
                               delete_after=10)
            elif self.is_flagged(x, y):
                await ctx.send(f'{ctx.author.mention}: Tile already flagged',
                               delete_after=10)
            else:
                self.set_flag(x, y)
                await self._message.edit(content=self)
        else:
            await ctx.send(f'{ctx.author.mention}: Voltorb Flip is not running here. '
                           f'Start a game by saying `{ctx.prefix}voltorb start`.',
                           delete_after=10)

    async def unflag(self, ctx, x: int, y: int):
        if self.running:
            if self.is_revealed(x, y):
                await ctx.send(f'{ctx.author.mention}: Tile already revealed',
                               delete_after=10)
            elif not self.is_flagged(x, y):
                await ctx.send(f'{ctx.author.mention}: Tile not flagged',
                               delete_after=10)
            else:
                self.clear_flag(x, y)
                await self._message.edit(content=self)
        else:
            await ctx.send(f'{ctx.author.mention}: Voltorb Flip is not running here. '
                           f'Start a game by saying `{ctx.prefix}voltorb start`.',
                           delete_after=10)

    async def show(self, ctx):
        if await super().show(ctx) is None:
            await ctx.send(f'{ctx.author.mention}: Voltorb Flip is not running here. '
                           f'Start a game by saying `{ctx.prefix}voltorb start`.',
                           delete_after=10)


class VoltorbFlip(GameCogBase):
    def __init__(self, bot):
        super().__init__(VoltorbFlipGame, bot)

    @commands.group(pass_context=True, case_insensitive=True)
    async def voltorb(self, ctx):
        """Play Voltorb Flip"""
        if ctx.invoked_subcommand is None:
            await ctx.send(f'Incorrect voltorb subcommand passed')

    @voltorb.command()
    async def start(self, ctx):
        """Start a game of Voltorb Flip"""
        await self.game_cmd('start', ctx)

    @commands.command(name='voltstart', aliases=['vst'])
    async def voltorb_start(self, ctx):
        """Start a game of Voltorb Flip"""
        await ctx.invoke(self.start)

    @voltorb.command()
    async def guess(self, ctx, *args):
        """Reveal a square and either claim its coins or blow it up"""
        x, y = await self.argcheck(ctx, *args)
        await self.game_cmd('guess', ctx, x, y)

    @commands.command(name='voltguess', aliases=['vgu', 'vg'])
    async def voltorb_guess(self, ctx, *args):
        """Reveal a square and either claim its coins or blow it up"""
        await ctx.invoke(self.guess, *args)

    @voltorb.command()
    async def flag(self, ctx, *args):
        """Flag a square"""
        x, y = await self.argcheck(ctx, *args)
        await self.game_cmd('flag', ctx, x, y)

    @commands.command(name='voltflag', aliases=['vfl', 'vf'])
    async def voltorb_flag(self, ctx, *args):
        """Flag a square"""
        await ctx.invoke(self.flag, *args)

    @voltorb.command()
    async def unflag(self, ctx, *args):
        """Unflag a square"""
        x, y = await self.argcheck(ctx, *args)
        await self.game_cmd('unflag', ctx, x, y)

    @commands.command(name='voltunflag', aliases=['vuf', 'vu'])
    async def voltorb_unflag(self, ctx, *args):
        """Unflag a square"""
        await ctx.invoke(self.unflag, *args)

    @voltorb.command()
    @commands.check(commands.is_owner)
    async def end(self, ctx):
        """End the game as a loss (owner only)"""
        await self.game_cmd('end', ctx)

    @commands.command(name='voltend', aliases=['ve'])
    @commands.check(commands.is_owner)
    async def voltorb_end(self, ctx):
        """End the game as a loss (owner only)"""
        await ctx.invoke(self.end)

    @voltorb.command()
    async def show(self, ctx):
        """Show the board in a new message"""
        await self.game_cmd('show', ctx)

    @commands.command(name='voltshow', aliases=['vsh'])
    async def voltorb_show(self, ctx):
        """Show the board in a new message"""
        await ctx.invoke(self.show)


def setup(bot):
    bot.add_cog(VoltorbFlip(bot))
