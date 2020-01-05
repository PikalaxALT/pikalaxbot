import discord
from discord.ext import commands, tasks
from . import BaseCog
import io
import time
import matplotlib.pyplot as plt


class Ping(BaseCog):
    def __init__(self, bot):
        super().__init__(bot)
        self.ping_history = []
        self.build_ping_history.start()

    @tasks.loop(seconds=1)
    async def build_ping_history(self):
        self.ping_history.append(self.bot.latency)

    @build_ping_history.before_loop
    async def before_ping_history(self):
        await self.bot.wait_until_ready()

    @commands.group(invoke_without_command=True)
    async def ping(self, ctx: commands.Context):
        new = await ctx.send('Pong!')
        delta = new.created_at - ctx.message.created_at
        await new.edit(content=f'Pong!\n'
                               f'Round trip: {delta.total_seconds() * 1000:.0f} ms\n'
                               f'Heartbeat latency: {self.bot.latency * 1000:.0f} ms')

    def do_plot_ping(self, buffer, history):
        values = self.ping_history
        if history > 0:
            values = values[-history:]
        history = len(values)
        plt.figure()
        plt.plot(range(history), values)
        plt.fill_between(range(history), [0 for _ in values], values)
        plt.savefig(buffer)
        plt.close()

    @ping.command(name='history', aliases=['graph'])
    async def plot_ping(self, ctx, history=60):
        buffer = io.BytesIO()
        start = time.perf_counter()
        await self.bot.loop.run_in_executor(None, self.do_plot_ping, buffer, history)
        end = time.perf_counter()
        buffer.seek(0)
        await ctx.send(f'Completed in {end - start:.3f}s', file=discord.File(buffer, 'ping.png'))


def setup(bot):
    bot.add_cog(Ping(bot))
