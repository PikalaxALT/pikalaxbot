import asyncio
import discord
import math
import time


class GameBase:
    def __init__(self, bot, timeout=90):
        self.bot = bot
        self._timeout = timeout
        self._lock = asyncio.Lock()
        self.reset()

    def reset(self):
        self._running = False
        self._message = None
        self._task = None
        self.start_time = -1

    @property
    def score(self):
        return max(int(math.ceil(5 * (self._timeout - time.time() + self.start_time) / self._timeout)), 1)

    @property
    def running(self):
        return self._running

    @running.setter
    def running(self, state):
        self._running = state

    async def show(self):
        pass

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

    async def end(self, ctx, failed=False):
        pass

    async def show_(self, ctx):
        if self.running:
            await self._message.delete()
            self._message = await ctx.send(self.show())
            return self._message
        return None
