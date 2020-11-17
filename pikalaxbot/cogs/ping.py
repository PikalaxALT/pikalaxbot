import discord
from discord.ext import commands, tasks
from . import BaseCog
import io
import time
import datetime
import matplotlib.pyplot as plt
import typing
import traceback
import numpy as np
from .utils.converters import PastTime
from .utils.mpl_time_axis import *


class Ping(BaseCog):
    """Commands for testing the bot's ping, and for reporting history."""

    def cog_unload(self):
        self.build_ping_history.cancel()

    async def init_db(self, sql):
        await sql.execute('create table if not exists ping_history (timestamp real, latency real)')
        await sql.execute('create unique index if not exists ping_history_idx on ping_history (timestamp)')
        self.build_ping_history.start()

    @tasks.loop(seconds=30)
    async def build_ping_history(self):
        now = self.build_ping_history._last_iteration.replace(tzinfo=None)
        ping = self.bot.latency * 1000
        async with self.bot.sql as sql:
            await sql.execute_insert('insert or ignore into ping_history values (?, ?)', (now.timestamp(), ping))

    @build_ping_history.before_loop
    async def before_ping_history(self):
        await self.bot.wait_until_ready()

    @build_ping_history.error
    async def ping_history_error(self, error):
        s = traceback.format_exception(error.__class__, error, error.__traceback__)
        content = f'Ignoring exception in Ping.build_ping_history\n{s}'
        await self.bot.send_tb(content)

    @commands.group(invoke_without_command=True)
    async def ping(self, ctx: commands.Context):
        """Quickly test the bot's ping"""

        new = await ctx.send('Pong!')
        delta = new.created_at - ctx.message.created_at
        await new.edit(content=f'Pong!\n'
                               f'Round trip: {delta.total_seconds() * 1000:.0f} ms\n'
                               f'Heartbeat latency: {self.bot.latency * 1000:.0f} ms')

    def do_plot_ping(self, buffer, history):
        times = list(history.keys())
        values = list(history.values())
        plt.figure()
        ax: plt.Axes = plt.gca()
        idxs = thin_points(len(times), 1000)
        times = np.array(times)[idxs]
        values = np.array(values)[idxs]
        ax.plot(times, values)
        ax.fill_between(times, [0 for _ in values], values)
        set_time_xlabs(ax, times)
        plt.xlabel('Time (UTC)')
        plt.ylabel('Heartbeat latency (ms)')
        plt.tight_layout()
        plt.savefig(buffer)
        plt.close()

    @ping.command(name='history', aliases=['graph', 'plot'])
    async def plot_ping(self, ctx, history: typing.Union[PastTime, int] = 60):
        """Plot the bot's ping history (measured as gateway heartbeat)
        for the indicated number of minutes (default: 60)"""
        if isinstance(history, int):
            history = ctx.message.created_at - datetime.timedelta(minutes=history)
        else:
            history = history.dt
        async with ctx.typing():
            fetch_start = time.perf_counter()
            async with self.bot.sql as sql:
                async with sql.execute('select * from ping_history where timestamp > ? order by timestamp', (history.timestamp())) as cur:
                    ping_history = {datetime.datetime.fromtimestamp(timestamp): latency async for timestamp, latency in cur}
            fetch_end = time.perf_counter()
            buffer = io.BytesIO()
            start = time.perf_counter()
            await self.bot.loop.run_in_executor(None, self.do_plot_ping, buffer, ping_history)
            end = time.perf_counter()
            buffer.seek(0)
        await ctx.send(
            f'Fetched records in {fetch_end - fetch_start:.3f}s\n'
            f'Rendered image in {end - start:.3f}s',
            file=discord.File(buffer, 'ping.png')
        )


def setup(bot):
    bot.add_cog(Ping(bot))
