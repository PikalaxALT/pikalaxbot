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
from utils import sql
from utils.default_cog import Cog
from discord.ext import commands


def find_emoji(guild, name, case_sensitive=True):
    def lower(s):
        return s if case_sensitive else s.lower()

    return discord.utils.find(lambda e: lower(name) == lower(e.name), guild.emojis)


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
            asyncio.ensure_future(self.end(ctx, failed=True), loop=self.bot.loop)
            self._task = None

    async def start(self, ctx):
        self.running = True
        self._message = await ctx.send(self)
        self._task = asyncio.ensure_future(self.timeout(ctx), loop=self.bot.loop)
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
        for player in self._players:
            await sql.increment_score(player, by=score)
        return score


class GameCogBase(Cog):
    gamecls = None
    __slots__ = ('channels',)

    def __init__(self, bot):
        if self.gamecls is None:
            raise NotImplemented('this class must be subclassed')
        super().__init__(bot)
        self.channels = {}

    def __getitem__(self, channel):
        if channel not in self.channels:
            self.channels[channel] = self.gamecls(self.bot)
        return self.channels[channel]

    @staticmethod
    def convert_args(*args):
        if len(args) >= 2:
            y, x = map(int, args[:2])
            yield x
            yield y
        else:
            y, x, *rest = args[0].lower()
            yield ord(y) - 0x60
            yield int(x)

    async def game_cmd(self, cmd, ctx, *args, **kwargs):
        async with self[ctx.channel.id] as game:
            cb = getattr(game, cmd)
            if cb is None:
                await ctx.send(f'{ctx.author.mention}: Invalid command: !{self.groupname} {cmd}',
                               delete_after=10)
            else:
                await cb(ctx, *args, **kwargs)

    async def argcheck(self, ctx, *args, minx=1, maxx=5, miny=1, maxy=5):
        exc = None
        try:
            x, y = self.convert_args(*args)
        except ValueError as e:
            exc = e
        else:
            if minx <= x <= maxx and miny <= y <= maxy:
                return x - 1, y - 1
        await ctx.send(f'{ctx.author.mention}: Invalid arguments. '
                       f'Try using two numbers (i.e. 2 5) or a letter '
                       f'and a number (i.e. c2).',
                       delete_after=10)
        raise commands.CommandError from exc
