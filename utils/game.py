import asyncio
import discord
import math
import time
from utils import sql
from discord.ext import commands


def find_emoji(guild, name, case_sensitive=True):
    def lower(s):
        return s if case_sensitive else s.lower()

    return discord.utils.find(lambda e: lower(name) == lower(e.name), guild.emojis)


class GameBase:
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
        await self._lock.release()

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
            discord.compat.create_task(self.end(ctx, failed=True))
            self._task = None

    async def start(self, ctx):
        self.running = True
        self._message = await ctx.send(self)
        self._task = discord.compat.create_task(self.timeout(ctx), loop=self.bot.loop)
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

    def award_points(self):
        score = max(math.ceil(self.score / len(self._players)), 1)
        for player in self._players:
            sql.increment_score(player, by=score)
        return score


class GameCogBase:
    def __init__(self, gamecls, bot, *, groupname=None):
        self.bot = bot
        self.channels = {}
        self.gamecls = gamecls
        self.groupname = groupname

    def __getitem__(self, channel):
        if channel not in self.channels:
            self.channels[channel] = self.gamecls(self.bot)
        return self.channels[channel]

    @staticmethod
    def convert_args(*args):
        if len(args) >= 2:
            yield from map(int, args[:2])
        else:
            x, y, *rest = args[0].lower()
            yield ord(x) - 0x60
            yield int(y)

    async def game_cmd(self, cmd, ctx, *args, **kwargs):
        async with self[ctx.channel.id] as game:
            cb = getattr(game, cmd)
            if cb is None:
                await ctx.send(f'{ctx.author.mention}: Invalid command: !{self.groupname} {cmd}',
                               delete_after=10)
            else:
                await cb(ctx, *args, **kwargs)

    async def argcheck(self, ctx, *args, minx=1, maxx=5, miny=1, maxy=5):
        try:
            if len(args) >= 2:
                x, y = map(int, args[:2])
            else:
                y, x, *rest = args[0].lower()
                x = int(x)
                y = ord(y) - 0x60
        except ValueError:
            pass
        else:
            if minx <= x <= maxx and miny <= y <= maxy:
                return x - 1, y - 1
        await ctx.send(f'{ctx.author.mention}: Invalid arguments. '
                       f'Try using two numbers (i.e. 2 5) or a letter '
                       f'and a number (i.e. c2).')
        raise commands.CommandError
