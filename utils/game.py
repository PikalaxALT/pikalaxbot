# PikalaxBOT - A Discord bot in discord.py
# Copyright (C) 2018  PikalaxALT
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
from cogs import Cog
from discord.ext import commands


def find_emoji(guild, name, case_sensitive=True):
    def lower(s):
        return s if case_sensitive else s.lower()

    return discord.utils.find(lambda e: lower(name) == lower(e.name), guild.emojis)


class BadGameArgument(commands.BadArgument):
    pass


class BoardCoords(commands.Converter):
    def __init__(self, minx=1, maxx=5, miny=1, maxy=5):
        super().__init__()
        self.minx = minx
        self.maxx = maxx
        self.miny = miny
        self.maxy = maxy

    async def convert(self, ctx, argument):
        if isinstance(argument, tuple):
            return argument
        try:
            argument = argument.lower()
            if argument.startswith(tuple('abcde')):
                y = ord(argument[0]) - 0x60
                x = int(argument[1])
            else:
                y, x = map(int, argument.split())
            assert self.minx <= x <= self.maxx and self.miny <= y <= self.maxy
            return x - 1, y - 1
        except (ValueError, AssertionError) as e:
            raise BadGameArgument from e


class GameBase:
    __slots__ = (
        'bot', '_timeout', '_lock', '_max_score', '_state', '_running', '_message', '_task',
        'start_time', '_players'
    )

    def __init__(self, bot, timeout=90, max_score=1000):
        self.bot = bot
        self._timeout = timeout
        self._lock = asyncio.Lock()
        self._max_score = max_score
        self.reset()

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
        self._players = set()

    @property
    def state(self):
        return self._state

    @property
    def score(self):
        time_factor = (self._timeout - time.time() + self.start_time) / self._timeout
        return max(int(math.ceil(self._max_score * time_factor)), 1)

    @property
    def running(self):
        return self._running

    @running.setter
    def running(self, state):
        self._running = state

    def __str__(self):
        pass

    def add_player(self, player):
        self._players.add(player)

    def get_player_names(self):
        return ', '.join(player.name for player in self._players)

    async def timeout(self, ctx):
        await asyncio.sleep(self._timeout)
        if self.running:
            await ctx.send('Time\'s up!')
            self.bot.create_task(self.end(ctx, failed=True))
            self._task = None

    async def start(self, ctx):
        self.running = True
        self._message = await ctx.send(self)
        self._task = self.bot.loop.create_task(self.timeout(ctx))
        self.start_time = time.time()

    async def end(self, ctx, failed=False, aborted=False):
        if self.running:
            if self._task and not self._task.done():
                self._task.cancel()
                self._task = None
            return True
        return False

    async def show(self, ctx):
        if self.running:
            await self._message.delete()
            self._message = await ctx.send(self)
            return self._message
        return None

    async def award_points(self):
        score = max(math.ceil(self.score / len(self._players)), 1)
        with self.bot.sql as sql:
            for player in self._players:
                sql.increment_score(player, by=score)
        return score


class GameCogBase(Cog):
    gamecls = None
    __slots__ = ('channels',)

    def __local_check(self, ctx):
        if ctx.guild is None:
            raise commands.NoPrivateMessage('This command cannot be used in private messages.')
        return True

    def __init__(self, bot):
        if self.gamecls is None:
            raise NotImplemented('this class must be subclassed')
        super().__init__(bot)
        self.channels = {}

    def __getitem__(self, channel):
        if channel not in self.channels:
            self.channels[channel] = self.gamecls(self.bot)
        return self.channels[channel]

    async def game_cmd(self, cmd, ctx, *args, **kwargs):
        async with self[ctx.channel.id] as game:
            cb = getattr(game, cmd)
            if cb is None:
                await ctx.send(f'{ctx.author.mention}: Invalid command: '
                               f'{ctx.prefix}{self.gamecls.__class__.__name__.lower()} {cmd}',
                               delete_after=10)
            else:
                await cb(ctx, *args, **kwargs)

    async def _error(self, ctx, exc):
        if isinstance(exc, BadGameArgument):
            await ctx.send(f'{ctx.author.mention}: Invalid arguments. '
                           f'Try using two numbers (i.e. 2 5) or a letter '
                           f'and a number (i.e. c2).',
                           delete_after=10)
        elif isinstance(exc, commands.NoPrivateMessage):
            await ctx.send(exc)
        self.log_tb(ctx, exc)
