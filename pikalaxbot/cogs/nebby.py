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

from discord.ext import commands
from . import *
from .utils.game import find_emoji
import typing
from ..types import *
import random

from sqlalchemy import Column, TEXT, bindparam, func, select, delete
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import StatementError


class Meme(BaseTable):
    __default_bag = (
        'happily jumped into the bag!',
        'reluctantly clambored into the bag.',
        'turned away!',
        'let out a cry in protest!'
    )

    bag = Column(TEXT, primary_key=True)

    @classmethod
    async def init(cls, conn: AsyncConnection):
        statement = insert(cls).values(bag=bindparam('bag'))
        upsert = statement.on_conflict_do_nothing(index_elements=['bag'])
        await conn.execute(upsert, [{'bag': msg} for msg in cls.__default_bag])

    @classmethod
    async def create(cls, connection: AsyncConnection):
        await super().create(connection)
        await cls.init(connection)

    @classmethod
    async def get(cls, conn: AsyncConnection) -> str:
        statement = select(cls.bag).order_by(func.random())
        return await conn.scalar(statement)

    @classmethod
    async def put(cls, conn: AsyncConnection, msg: str):
        statement = insert(cls).values(bag=msg)
        await conn.execute(statement)

    @classmethod
    async def drop(cls, conn: AsyncConnection, msg: str):
        statement = delete(cls).where(cls.bag == msg)
        await conn.execute(statement)

    @classmethod
    async def reset(cls, conn: AsyncConnection):
        await conn.execute(delete(cls).where(True))
        await cls.init(conn)


class HMM(typing.Generic[T]):
    def __init__(self, transition: typing.Sequence[typing.Sequence[float]], emission: typing.Sequence[T]):
        if len(emission) != len(transition):
            raise ValueError('Different number of transition and emission states')
        if any(len(x) != len(emission) for x in transition):
            raise ValueError('Transition matrix must be square')
        self.transition = transition
        self.emission = emission
        self.state = 0

    @property
    def n_states(self):
        return len(self.transition)

    def emit(self):
        res = self.emission[self.state]
        self.state, = random.choices(range(self.n_states), weights=self.transition[self.state])
        return res

    def get_chain(self, length: int, start=0) -> typing.Generator[T, typing.Any, None]:
        self.state = start
        for i in range(length):
            yield self.emit()
            if self.state == self.n_states - 1:
                break


class Nebby(BaseCog):
    """Commands related to Lillie's bag. Get in, Nebby."""

    default_bag = (
        ('happily jumped into the bag!',),
        ('reluctantly clambored into the bag.',),
        ('turned away!',),
        ('let out a cry in protest!',)
    )

    _nebby: HMM[str] = HMM(
        [[0, 1, 0, 0, 0],
         [1, 2, 1, 0, 0],
         [0, 0, 1, 1, 0],
         [0, 0, 0, 1, 9],
         [0, 0, 0, 0, 1]],
        'pew! '
    )

    async def init_db(self, sql):
        await Meme.create(sql)

    @commands.group(invoke_without_command=True)
    async def bag(self, ctx: MyContext):
        """Get in the bag, Nebby."""
        async with self.bot.sql as sql:
            if message := await Meme.get(sql):
                await ctx.send(f'*{message}*')
            else:
                emoji = find_emoji(ctx.bot, 'BibleThump', case_sensitive=False)
                await ctx.send(f'*cannot find the bag {emoji}*')

    @bag.command()
    async def add(self, ctx: MyContext, *, fmtstr: str):
        """Add a message to the bag."""
        try:
            async with self.bot.sql as sql:
                await Meme.put(sql, fmtstr)
        except StatementError:
            await ctx.send('That message is already in the bag')
        else:
            await ctx.send('Message was successfully placed in the bag')

    @bag.command(name='remove')
    @commands.is_owner()
    async def remove_bag(self, ctx: MyContext, *, msg: str):
        """Remove a phrase from the bag"""
        if msg in self.default_bag:
            return await ctx.send('Cannot remove default message from bag')
        try:
            async with self.bot.sql as sql:
                await Meme.drop(sql, msg)
        except StatementError:
            await ctx.send('Cannot remove message from the bag')
        else:
            await ctx.send('Removed message from bag')

    @bag.command(name='reset')
    @commands.is_owner()
    async def reset_bag(self, ctx: MyContext):
        """Reset the bag"""
        async with self.bot.sql as sql:
            await Meme.reset(sql)
        await ctx.send('Reset the bag')

    @commands.command()
    async def nebby(self, ctx):
        """Pew!"""

        emission = ''.join(self._nebby.get_chain(100)).title()
        await ctx.send(emission)


def setup(bot: PikalaxBOT):
    bot.add_cog(Nebby(bot))


def teardown(bot: PikalaxBOT):
    Meme.unlink()
