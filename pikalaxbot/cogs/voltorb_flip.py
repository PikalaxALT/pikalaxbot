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

import typing

import discord
from discord.ext import commands
import numpy as np

from . import *
from .utils.game import GameBase, GameCogBase, GameStartCommand
from .utils.converters import board_coords
from jishaku.functools import executor_function

from sqlalchemy import Column, BIGINT, INTEGER, CheckConstraint, select
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.dialects.postgresql import insert


class Voltorb(BaseTable):
    id = Column(BIGINT, primary_key=True)
    level = Column(INTEGER, nullable=False, default=1)

    __table_args__ = (CheckConstraint(level.between(1, 10)),)

    @classmethod
    async def getlevel(cls, conn: AsyncConnection, channel: discord.TextChannel):
        statement = select(cls.level).where(cls.id == channel.id)
        return (await conn.scalar(statement)) or 1

    @classmethod
    async def updatelevel(cls, conn: AsyncConnection, channel: discord.TextChannel, new_level: int):
        statement = insert(cls).values(id=channel.id, level=new_level)
        upsert = statement.on_conflict_do_update(
            index_elements=['id'],
            set_={'level': statement.excluded.level}
        )
        await conn.execute(upsert)


class VoltorbFlipGame(GameBase):
    ONE = 1
    TWO = 2
    THR = 3
    FLG = 4
    RVL = 8
    VTB = 16
    _minmax = (20, 50, 100, 200, 500, 1000, 2000, 3000, 5000, 7000, 10000)

    def __init__(self, bot):
        super().__init__(bot, timeout=180)
        self._level: typing.Optional[int] = None
        self._state = np.ones((5, 5), dtype=np.uint8)
        self._score = 0
        self._ended = False
        self._coin_total = 1
        self._revealed_total = 1

    def reset(self):
        super().reset()
        self._state = np.ones((5, 5), dtype=np.uint8)
        self._score = 0
        self._ended = False
        self._coin_total = 1
        self._revealed_total = 1

    @property
    def level(self):
        return self._level

    async def get_level(self, channel: discord.TextChannel):
        if self._level is None:
            async with self.bot.sql as sql:
                self._level = await Voltorb.getlevel(sql, channel)
        return self._level

    async def update_level(self, channel: discord.TextChannel, new_level: int):
        self._level = new_level
        async with self.bot.sql as sql:
            await Voltorb.updatelevel(sql, channel, new_level)

    @executor_function
    def build_board(self):
        _min, _max = VoltorbFlipGame._minmax[self.level - 1:self.level + 1]  # type: int, int
        _num_voltorb = 6 + self.level // 2
        _cum_weights = [0.8 - 0.05 * self.level, 0.96 - 0.04 * self.level, 1.]
        _weights = [0.8 - 0.05 * self.level, 0.16 + 0.01 * self.level, 0.04 + 0.04 * self.level]
        _coin_sq_ct = 25 - _num_voltorb

        while not _max >= (_coin_total := (coins := np.random.choice(
            np.arange(3, dtype=np.uint8),
            _coin_sq_ct,
            p=_weights
        ) + 1).prod()) >= _min:
            pass
        self._coin_total = _coin_total

        board_flat = np.append(coins, np.full((_num_voltorb,), VoltorbFlipGame.VTB | 1, dtype=np.uint8))
        np.random.shuffle(board_flat)
        self._state = board_flat.reshape((5, 5))

    def __str__(self):
        bombs: np.ndarray[bool] = self._state & VoltorbFlipGame.VTB != 0
        coins: np.ndarray[np.uint8] = (self._state & 3) * ~bombs
        colbombcounts = [f'　{x:d}' for x in bombs.sum(0)]
        colcoincounts = [f'x{x:d}' for x in coins.sum(0)]
        rowbombcounts = [f':bomb:{y:d}' for y in bombs.sum(1)]
        rowcoincounts = [f'x{y:d}' for y in coins.sum(1)]
        state = f'LEVEL: {self.level}\n' \
                f'BOARD STATE:\n'
        state += '{}|{}|{}|{}|{}:bomb:\n'.format(*colbombcounts)
        state += ' {} | {} | {} | {} | {}\n'.format(*colcoincounts)
        unr = ':white_square_button:'
        flg = ':triangular_flag_on_post:'
        charmap: np.ndarray[str] = np.array([
            unr, unr, unr, unr,
            flg, flg, flg, flg,
            unr, ':one:', ':two:', ':three:',
            unr, ':one:', ':two:', ':three:',
            unr, unr, unr, unr,
            flg, flg, flg, flg,
            unr, ':bomb:', unr, unr,
            unr, ':bomb:', unr, unr,
        ])
        char_array: np.ndarray[str] = charmap[self._state]
        state += '\n'.join(
            ''.join(row) + ' | {} | {}'.format(bomby, coiny)
            for row, bomby, coiny in zip(char_array, rowbombcounts, rowcoincounts)
        ) + f'\nSCORE: {0 if self._ended else self._score:d}'
        return state

    async def start(self, ctx):
        if self.running:
            await ctx.send(f'{ctx.author.mention}: Voltorb Flip is already running here.',
                           delete_after=10)
        else:
            await self.get_level(ctx.channel)
            self._players = set()
            self._score = 1
            await self.build_board()
            await ctx.send(f'New game of Voltorb Flip! Use `{ctx.prefix}voltorb guess y x` to reveal a square, '
                           f'`{ctx.prefix}voltorb flag y x` to flag a square. You have {self._timeout} seconds '
                           f'to find all the coins!')
            await super().start(ctx)

    async def end(self, ctx: MyContext, failed=False, aborted=False):
        if await super().end(ctx, failed=failed, aborted=aborted):
            new_level = self.level
            self._state |= VoltorbFlipGame.RVL
            await self._message.edit(content=self)
            if aborted:
                await ctx.send(f'Game terminated by {ctx.author.mention}')
            elif failed:
                self._ended = True
                await ctx.send(f'Game over. You win 0 coins.')
                new_level = max(new_level - 1, 1)
            else:
                score = await self.award_points()
                await ctx.send(f'The following players each earn {score:d} points:\n'
                               f'```{self.get_player_names()}```')
                new_level = min(new_level + 1, 10)
            if new_level != self.level:
                await ctx.send(f'The game level {"rose" if new_level > self.level else "fell"} to {new_level:d}!')
                await self.update_level(ctx.channel, new_level)
            self.reset()
        else:
            await ctx.send(f'{ctx.author.mention}: Voltorb Flip is not running here. '
                           f'Start a game by saying `{ctx.prefix}voltorb start`.',
                           delete_after=10)

    async def guess(self, ctx: MyContext, x: int, y: int):
        if self.running:
            if self._state[y, x] & VoltorbFlipGame.VTB:
                await ctx.send('KAPOW')
                await self.end(ctx, failed=True)
            elif self._state[y, x] & VoltorbFlipGame.RVL:
                await ctx.send(f'{ctx.author.mention}: Tile already revealed.',
                               delete_after=10)
            else:
                self.add_player(ctx.author)
                self._state[y, x] |= VoltorbFlipGame.RVL
                await self._message.edit(content=self.__str__())
                if (multiplier := self._state[y, x] & 3) > 1:
                    self._score *= multiplier
                    await ctx.send(f'Got x{multiplier:d}!', delete_after=10)
                    emoji = discord.utils.get(self.bot.emojis, name='RaccAttack')
                    if emoji is not None:
                        await ctx.message.add_reaction(emoji)
                if self._score == self._coin_total:
                    await self.end(ctx)
        else:
            await ctx.send(f'{ctx.author.mention}: Voltorb Flip is not running here. '
                           f'Start a game by saying `{ctx.prefix}voltorb start`.',
                           delete_after=10)

    async def flag(self, ctx: MyContext, x: int, y: int):
        if self.running:
            if self._state[y, x] & VoltorbFlipGame.RVL:
                await ctx.send(f'{ctx.author.mention}: Tile already revealed',
                               delete_after=10)
            elif self._state[y, x] & VoltorbFlipGame.FLG:
                await ctx.send(f'{ctx.author.mention}: Tile already flagged',
                               delete_after=10)
            else:
                self._state[y, x] |= VoltorbFlipGame.FLG
                await self._message.edit(content=self)
        else:
            await ctx.send(f'{ctx.author.mention}: Voltorb Flip is not running here. '
                           f'Start a game by saying `{ctx.prefix}voltorb start`.',
                           delete_after=10)

    async def unflag(self, ctx: MyContext, x: int, y: int):
        if self.running:
            if self._state[y, x] & VoltorbFlipGame.RVL:
                await ctx.send(f'{ctx.author.mention}: Tile already revealed',
                               delete_after=10)
            elif not self._state[y, x] & VoltorbFlipGame.FLG:
                await ctx.send(f'{ctx.author.mention}: Tile not flagged',
                               delete_after=10)
            else:
                self._state[y, x] &= ~VoltorbFlipGame.FLG
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


converter = board_coords()


class VoltorbFlip(GameCogBase[VoltorbFlipGame]):
    """Commands for playing Voltorb Flip, everyone's favorite game from
    the international release of Pokemon HeartGold and SoulSilver."""

    async def init_db(self, sql):
        await super().init_db(sql)
        await Voltorb.create(sql)

    def cog_check(self, ctx: MyContext):
        return self._local_check(ctx)

    @commands.group(case_insensitive=True, invoke_without_command=True)
    async def voltorb(self, ctx: MyContext):
        """Play Voltorb Flip"""
        await ctx.send_help(ctx.command)

    @voltorb.command(cls=GameStartCommand)
    async def start(self, ctx: MyContext):
        """Start a game of Voltorb Flip"""
        await self.game_cmd('start', ctx)

    @commands.command(name='voltstart', aliases=['vst'], cls=GameStartCommand)
    async def voltorb_start(self, ctx: MyContext):
        """Start a game of Voltorb Flip"""
        await self.start(ctx)

    @voltorb.command()
    async def guess(self, ctx: MyContext, *, args: converter):
        """Reveal a square and either claim its coins or blow it up"""
        await self.game_cmd('guess', ctx, *args)

    @commands.command(name='voltguess', aliases=['vgu', 'vg'])
    async def voltorb_guess(self, ctx: MyContext, *, args: converter):
        """Reveal a square and either claim its coins or blow it up"""
        await self.guess(ctx, args=args)

    @voltorb.command(usage='<y x|yx>')
    async def flag(self, ctx: MyContext, *, args: converter):
        """Flag a square"""
        await self.game_cmd('flag', ctx, *args)

    @commands.command(name='voltflag', aliases=['vfl', 'vf'], usage='[< x|yx>')
    async def voltorb_flag(self, ctx: MyContext, *, args: converter):
        """Flag a square"""
        await self.flag(ctx, args=args)

    @voltorb.command(usage='<y x|yx>')
    async def unflag(self, ctx: MyContext, *, args: converter):
        """Unflag a square"""
        await self.game_cmd('unflag', ctx, *args)

    @commands.command(name='voltunflag', aliases=['vuf', 'vu'], usage='<y x|yx>')
    async def voltorb_unflag(self, ctx: MyContext, *, args: converter):
        """Unflag a square"""
        await self.unflag(ctx, args=args)

    @voltorb.command()
    @commands.is_owner()
    async def end(self, ctx: MyContext):
        """End the game as a loss (owner only)"""
        await self.game_cmd('end', ctx, aborted=True)

    @commands.command(name='voltend', aliases=['ve'])
    @commands.is_owner()
    async def voltorb_end(self, ctx: MyContext):
        """End the game as a loss (owner only)"""
        await self.end(ctx)

    @voltorb.command()
    async def show(self, ctx: MyContext):
        """Show the board in a new message"""
        await self.game_cmd('show', ctx)

    @commands.command(name='voltshow', aliases=['vsh'])
    async def voltorb_show(self, ctx: MyContext):
        """Show the board in a new message"""
        await self.show(ctx)

    async def cog_command_error(self, ctx: MyContext, exc: commands.CommandError):
        await self._error(ctx, exc)


def setup(bot: PikalaxBOT):
    bot.add_cog(VoltorbFlip(bot))


def teardown(bot: PikalaxBOT):
    Voltorb.unlink()
