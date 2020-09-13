import discord
from discord.ext import commands, tasks
from . import BaseCog
import io
import time
import datetime
import struct
import matplotlib.pyplot as plt


class Ping(BaseCog):
    def __init__(self, bot):
        super().__init__(bot)
        self.ping_history = []
        self.build_ping_history.start()
        self.start_time = None

    def cog_unload(self):
        self.build_ping_history.cancel()

    @tasks.loop(seconds=30)
    async def build_ping_history(self):
        self.ping_history.append(self.bot.latency * 1000)

    @build_ping_history.before_loop
    async def before_ping_history(self):
        await self.bot.wait_until_ready()
        self.start_time = datetime.datetime.utcnow()

    @commands.group(invoke_without_command=True)
    async def ping(self, ctx: commands.Context):
        new = await ctx.send('Pong!')
        delta = new.created_at - ctx.message.created_at
        await new.edit(content=f'Pong!\n'
                               f'Round trip: {delta.total_seconds() * 1000:.0f} ms\n'
                               f'Heartbeat latency: {self.bot.latency * 1000:.0f} ms')

    def do_plot_ping(self, buffer, history):
        values = self.ping_history
        start_time = self.start_time
        if history > 0:
            start_time = max(start_time, start_time + datetime.timedelta(minutes=len(values) / 2 - history))
            values = values[-2 * history:]
        history = len(values)
        plt.figure()
        plt.plot(range(history), values)
        plt.fill_between(range(history), [0 for _ in values], values)
        xtickvalues = list(range(0, history, history // 10 + (history % 10 != 0)))
        xticklabels = [(start_time + datetime.timedelta(seconds=i * 30)).strftime('%Y-%m-%d\nT%H:%M:%S') for i in xtickvalues]
        plt.xticks(xtickvalues, xticklabels, rotation=45, ha='right', ma='right')
        plt.xlabel('Time (UTC)')
        plt.ylabel('Heartbeat latency (ms)')
        plt.tight_layout()
        plt.savefig(buffer)
        plt.close()

    @commands.check(lambda ctx: ctx.cog.start_time)
    @ping.command(name='history', aliases=['graph', 'plot'])
    async def plot_ping(self, ctx, history=60):
        """Plot the bot's ping history (measured as gateway heartbeat) for the indicated number of minutes (default: 60)"""
        buffer = io.BytesIO()
        start = time.perf_counter()
        await self.bot.loop.run_in_executor(None, self.do_plot_ping, buffer, history)
        end = time.perf_counter()
        buffer.seek(0)
        await ctx.send(f'Completed in {end - start:.3f}s', file=discord.File(buffer, 'ping.png'))

    @commands.check(lambda ctx: ctx.cog.start_time)
    @ping.command(name='dump')
    async def dump_ping(self, ctx: commands.Context):
        async with ctx.typing():
            output = b''
            for i, record in enumerate(self.ping_history):
                timestamp = (self.start_time + datetime.timedelta(seconds=30 * i)).timestamp()
                output += struct.pack('=dd', timestamp, record)
            curtime = datetime.datetime.utcnow().strftime('%Y%m%d.%H%M%S')
            with open(f'ping_{curtime}.bin', 'wb') as ofp:
                ofp.write(output)
        await ctx.message.add_reaction('\u2705')


def setup(bot):
    bot.add_cog(Ping(bot))
