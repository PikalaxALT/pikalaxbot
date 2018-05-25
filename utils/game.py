import asyncio
import discord
import math
import time
from utils import sql
from discord.ext import commands


class GameBase:
    def __init__(self, bot, timeout=90, max_score=1000):
        self.bot = bot
        self._timeout = timeout
        self._lock = asyncio.Lock()
        self._max_score = 1000
        self.reset()

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
        return max(int(math.ceil(5 * (self._timeout - time.time() + self.start_time) / self._timeout)), 1)

    @property
    def running(self):
        return self._running

    @running.setter
    def running(self, state):
        self._running = state

    def show(self):
        pass

    def add_player(self, ctx):
        self._players.add(ctx.author.id)

    async def timeout(self, ctx):
        await asyncio.sleep(self._timeout)
        if self.running:
            await ctx.send('Time\'s up!')
            discord.compat.create_task(self.end(ctx, failed=True))
            self._task = None

    async def start(self, ctx):
        self.running = True
        self._message = await ctx.send(self.show())
        self._task = discord.compat.create_task(self.timeout(ctx), loop=self.bot.loop)
        self.start_time = time.time()
        self.add_player(ctx)

    async def end(self, ctx, failed=False, aborted=False):
        if self.running:
            if self._task and not self._task.done():
                self._task.cancel()
                self._task = None
            return True
        return False

    async def show_(self, ctx):
        if self.running:
            await self._message.delete()
            self._message = await ctx.send(self.show())
            return self._message
        return None

    def award_points(self, ctx):
        score = max(math.ceil(self.score / len(self._players)), 1)
        author = ctx.author
        for player in self._players:
            ctx.message.author = ctx.guild.get_member(player)
            sql.increment_score(ctx, by=score)
        ctx.message.author = author
        return score


class GameCogBase:
    def __init__(self, bot):
        self.bot = bot
        self.channels = {}

    @staticmethod
    def convert_args(*args):
        if len(args) >= 2:
            yield from map(int, args[:2])
        else:
            x, y, *rest = args[0].lower()
            yield ord(x) - 0x60
            yield int(y)