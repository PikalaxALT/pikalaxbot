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

import asyncio
import discord
import math
import time
from discord.ext import commands
from .errors import BadGameArgument
import typing
import collections
from .. import *
from ...types import T
from ...pokeapi import PokeApi

from sqlalchemy import Column, BIGINT, INTEGER, CheckConstraint, select, func, delete, update
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.dialects.postgresql import insert

__all__ = (
    'find_emoji',
    'GameBase',
    'GameStartCommand',
    'GameCogBase',
    'Game'
)


class Game(BaseTable):
    id = Column(BIGINT, primary_key=True)
    score = Column(INTEGER, nullable=False)

    __table_args__ = (CheckConstraint(score >= 0),)

    @classmethod
    async def increment_score(cls, connection: AsyncConnection, player: discord.Member, *, by=1):
        statement = insert(cls).values(id=player.id, score=by)
        upsert = statement.on_conflict_do_update(
            index_elements=['id'],
            set_={'score': cls.score + statement.excluded.score}
        )
        await connection.execute(upsert)

    @classmethod
    async def decrement_score(cls, connection: AsyncConnection, player: discord.Member, *, by=1):
        statement = update(cls).values(score=cls.score - by).where(cls.id == player.id)
        await connection.execute(statement)

    @classmethod
    async def check_score(cls, connection: AsyncConnection, player: discord.Member):
        ranking = func.rank().over(order_by=cls.score.desc())
        table = select([cls.id, cls.score, ranking])
        statement = select([table.columns[1], table.columns[2]]).where(table.columns[0] == player.id)
        result = await connection.execute(statement)
        return result.first()

    @classmethod
    async def check_all_scores(cls, connection: AsyncConnection):
        statement = select([cls.id, cls.score]).order_by(cls.score.desc()).limit(10)
        result = await connection.execute(statement)
        return result.all()

    @classmethod
    async def clear(cls, connection: AsyncConnection):
        return await connection.execute(delete(cls).where(True))


def find_emoji(
        guild: typing.Union[PikalaxBOT, discord.Guild],
        name: str,
        case_sensitive=True
) -> typing.Optional[discord.Emoji]:
    if case_sensitive:
        return discord.utils.get(guild.emojis, name=name)
    name = name.lower()
    return discord.utils.find(lambda e: e.name.lower() == name, guild.emojis)


class NoInvokeOnEdit(commands.CheckFailure):
    pass


class GameBase:
    __slots__ = (
        'bot', '_timeout', '_lock', '_max_score', '_state', '_running', '_message', '_task',
        'start_time', '_players', '_solution'
    )

    def __init__(self, bot: PikalaxBOT, timeout=90, max_score=1000):
        self.bot = bot
        self._timeout = timeout
        self._lock = asyncio.Lock()
        self._max_score = max_score
        # Inline self.reset()
        self._state = None
        self._running = False
        self._message: typing.Optional[discord.Message] = None
        self._task: typing.Union[None, asyncio.Task, asyncio.Future] = None
        self.start_time = -1
        self._players: set[discord.Member] = set()
        self._solution: typing.Optional[PokeApi.PokemonSpecies] = None

    async def __aenter__(self):
        await self._lock.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._lock.release()

    def reset(self):
        self._state = None
        self._running = False
        self._message = None
        self._task = None
        self.start_time = -1
        self._players.clear()
        self._solution = None

    @property
    def state(self):
        return self._state

    @property
    def task(self) -> typing.Union[None, asyncio.Task, asyncio.Future]:
        t: typing.Union[None, asyncio.Task, asyncio.Future] = self._task
        if not t or t.done():
            t = self._task = None
        return t

    @task.setter
    def task(self, _task: typing.Union[None, asyncio.Task, asyncio.Future]):
        self._task = _task

    @property
    def score(self):
        end_time = time.time()
        if self._timeout is None:
            time_factor = 2 ** ((self.start_time - end_time) / 300.0)
        else:
            time_factor = (self._timeout - end_time + self.start_time) / self._timeout
        return max(int(math.ceil(self._max_score * time_factor)), 1)

    @property
    def running(self):
        return self._running

    @running.setter
    def running(self, state):
        self._running = state

    def __str__(self):
        return 'GameCogBase object should be subclassed'

    def add_player(self, player):
        self._players.add(player)

    def get_player_names(self):
        return ', '.join(player.name for player in self._players)

    async def timeout(self, ctx):
        await asyncio.sleep(self._timeout)
        if self.running:
            await ctx.send('Time\'s up!')
            asyncio.create_task(self.end(ctx, failed=True))

    async def start(self, ctx: MyContext):
        def destroy_self(task: asyncio.Task):
            self.task = None

        self.running = True
        self._message = await ctx.send(str(self))
        if self._timeout is None:
            self.task = self.bot.loop.create_future()
        else:
            self.task = asyncio.create_task(self.timeout(ctx))
        self.task.add_done_callback(destroy_self)
        self.start_time = time.time()

    async def end(self, ctx: MyContext, failed=False, aborted=False):
        if self.running:
            if self.task:
                self.task.cancel()
            return True
        return False

    async def show(self, ctx: MyContext):
        if self.running:
            await self._message.delete()
            self._message = await ctx.send(str(self))
            return self._message
        return None

    async def award_points(self):
        score = round(max(math.ceil(self.score / len(self._players)), 1))
        async with self.bot.sql as sql:
            for player in self._players:
                await Game.increment_score(sql, player, by=score)
        return score

    async def get_solution_embed(self, *, failed=False, aborted=False):
        sprite_url = await self.bot.pokeapi.get_species_sprite_url(self._solution)
        return discord.Embed(
                title=self._solution.name,
                colour=discord.Colour.red() if failed or aborted else discord.Colour.green()
            ).set_image(url=sprite_url or discord.Embed.Empty)


class GameStartCommand(commands.Command):
    @property
    def _max_concurrency(self):
        if self.cog:
            return self.cog._max_concurrency

    @_max_concurrency.setter  # Workaround for super __init__
    def _max_concurrency(self, value):
        pass


class GameCogBase(BaseCog, typing.Generic[T]):
    @discord.utils.cached_property
    def _gamecls(self) -> typing.Type[T]:
        return typing.get_args(self.__orig_bases__[0])[0]

    async def init_db(self, sql):
        await Game.create(sql)

    def _local_check(self, ctx: MyContext):
        if ctx.guild is None:
            raise commands.NoPrivateMessage('This command cannot be used in private messages.')
        if ctx.message.edited_at:
            raise NoInvokeOnEdit('This command cannot be invoked by editing your message')
        return True

    def __init__(self, bot):
        super().__init__(bot)
        self.channels: typing.Mapping[int, T] = collections.defaultdict(lambda: self._gamecls(self.bot))
        self._max_concurrency = commands.MaxConcurrency(1, per=commands.BucketType.channel, wait=False)

    def __getitem__(self, channel: int):
        return self.channels[channel]

    async def game_cmd(self, cmd: str, ctx: MyContext, *args, **kwargs):
        async with self[ctx.channel.id] as game:
            cb: typing.Callable[[MyContext, ...], typing.Coroutine] = getattr(game, cmd)
            if cb is None:
                await ctx.send(f'{ctx.author.mention}: Invalid command: '
                               f'{ctx.prefix}{self._gamecls.__name__.lower()} {cmd}',
                               delete_after=10)
            else:
                await cb(ctx, *args, **kwargs)
        if cmd == 'start':
            await asyncio.wait({
                ctx._task,
                asyncio.wait_for(self[ctx.channel.id]._task, None)
            }, return_when=asyncio.FIRST_COMPLETED)

    async def _error(self, ctx: MyContext, exc: commands.CommandError):
        if isinstance(exc, BadGameArgument):
            await ctx.send(f'{ctx.author.mention}: Invalid arguments. '
                           f'Try using two numbers (i.e. 2 5) or a letter '
                           f'and a number (i.e. c2).',
                           delete_after=10)
        elif isinstance(exc, (commands.NoPrivateMessage, NoInvokeOnEdit)):
            await ctx.send(str(exc))
        elif isinstance(exc, commands.MaxConcurrencyReached):
            await ctx.send(f'{self.qualified_name} is already running here')
        else:
            await self.bot.get_cog('ErrorHandling').send_tb(ctx, exc, origin=f'command {ctx.command}')
        self.log_tb(ctx, exc)

    async def end_quietly(self, ctx: MyContext, history: set[int]):
        async with self[ctx.channel.id] as game:
            if game.running and game._message and game._message.id in history:
                game.task.cancel()
                game.reset()
