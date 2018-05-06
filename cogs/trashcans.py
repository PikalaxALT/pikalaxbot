import asyncio
import discord
from discord.ext import commands
import random


class TrashcansGame:
    def __init__(self, bot):
        self.bot = bot
        self._timeout = 90
        self.reset()

    def reset(self):
        self._running = False
        self._message: discord.Message = None
        self._task: asyncio.Task = None
        self.reset_locks()

    @property
    def running(self):
        return self._running

    @running.setter
    def running(self, state):
        self._running = state

    @property
    def state(self):
        return self._state

    def show(self):
        return '\n'.join(' '.join('\u2705' if y else chr(0x1f5d1) for y in x) for x in self.state)

    @staticmethod
    def is_valid(x, y):
        return x in range(5) and y in range(3)

    def reset_locks(self):
        self._solution = [[False for j in range(5)] for i in range(3)]
        x1 = random.randint(0, 4)
        y1 = random.randint(0, 2)
        self._solution[y1][x1] = True
        options = [
            ( 0, -1),
            ( 0,  1),
            (-1,  0),
            ( 1,  0),
            (-1, -1),
            (-1,  1),
            ( 1, -1),
            ( 1,  1)
        ]
        x2 = -1
        y2 = -1
        while not self.is_valid(x2, y2):
            dx, dy = random.choice(options)
            x2 = x1 + dx
            y2 = y1 + dy
        self._solution[y2][x2] = True
        self._state = [[False for j in range(5)] for i in range(3)]
        self.on_second_can = False

    async def start(self, ctx: commands.Context):
        if self.running:
            await ctx.send(f'{ctx.author.mention}: Trashcans is already running here.',
                           delete_after=10)
        else:
            self.running = True
            self.reset_locks()
            await ctx.send(f'Welcome to Lt. Surge\'s Gym!  Use `!trashcans guess x y` to check a can!')
            self._message = await ctx.send(f'{self.show()}')
            self._task = discord.compat.create_task(self.timeout(ctx), loop=self.bot.loop)

    async def timeout(self, ctx:commands.Context):
        await asyncio.sleep(self._timeout)
        if self.running:
            await ctx.send('Time\'s up!')
            await self.end(ctx, failed=True)

    async def end(self, ctx: commands.Context, failed=False, aborted=False):
        if self._task and not self._task.done():
            self._task.cancel()
            self._task = None
        if self.running:
            await self._message.edit(content=f'{self.show()}')
            if aborted:
                await ctx.send(f'Game terminated by {ctx.author.mention}.')
            elif failed:
                await ctx.send(f'Time\'s up.  Looks like you won\'t be fighting the Gym Leader today.')
            else:
                await ctx.send(f'The 2nd electric lock opened! The motorized door opened!')
            self.reset()
        else:
            await ctx.send(f'{ctx.author.mention}: Trashcans is not running here. '
                           f'Start a game by saying `{ctx.prefix}trashcans start`.',
                           delete_after=10)

    async def guess(self, ctx: commands.Context, x: int, y: int):
        if self.running:
            x -= 1
            y -= 1
            if self.is_valid(x, y):
                if self.on_second_can:
                    if self.state[y][x] or not self._solution[y][x]:
                        self.reset_locks()
                        await ctx.send(f'Nope! There\'s only trash here.\n'
                                       f'Hey! The electric locks were reset!')
                    else:
                        self.state[y][x] = True
                        await ctx.send(f'Hey! There\'s another switch under the trash! Turn it on!')
                        await self.end(ctx)
                else:
                    if self._solution[y][x]:
                        self.state[y][x] = True
                        self.on_second_can = True
                        await ctx.send(f'Hey! There\'s a switch under the trash! Turn it on!')
                        await ctx.send(f'The 1st electric lock opened!')
                    else:
                        await ctx.send(f'Nope, there\'s only trash here.')
                await self._message.edit(content=f'{self.show()}')
            else:
                await ctx.send(f'{ctx.author.mention}: Coordinates out of range.',
                               delete_after=10)

        else:
            await ctx.send(f'{ctx.author.mention}: Trashcans is not running here. '
                           f'Start a game by saying `{ctx.prefix}trashcans start`.',
                           delete_after=10)


class Trashcans:
    def __init__(self, bot):
        self.bot = bot
        self.channels = {}

    @commands.group(pass_context=True)
    async def trashcans(self, ctx):
        f"""Play trashcans"""
        if ctx.invoked_subcommand is None:
            await ctx.send(f'Incorrect trashcans subcommand passed. Try `{ctx.prefix}help trashcans`')
        if ctx.channel.id not in self.channels:
            self.channels[ctx.channel.id] = TrashcansGame(self.bot)

    @trashcans.command()
    async def start(self, ctx):
        """Start a game in the current channel"""
        await self.channels[ctx.channel.id].start(ctx)

    @trashcans.command()
    async def guess(self, ctx, x: int, y: int):
        """Make a guess, if you dare"""
        await self.channels[ctx.channel.id].guess(ctx, x, y)

    @trashcans.command()
    async def end(self, ctx):
        """End the game as a loss (owner only)"""
        if self.bot.is_owner(ctx.author):
            await self.channels[ctx.channel.id].end(ctx, aborted=True)


def setup(bot):
    bot.add_cog(Trashcans(bot))
