import discord
from discord.ext import commands, tasks
from . import BaseCog
import io
import time
import datetime
import matplotlib.pyplot as plt
import typing
import numpy as np
from .utils.converters import PastTime
from .utils.mpl_time_axis import *


class Ping(BaseCog):
    """Commands for testing the bot's ping, and for reporting history."""

    def cog_unload(self):
        self.build_ping_history.cancel()

    async def init_db(self, sql):
        await sql.execute('create table if not exists ping_history (timestamp timestamp, latency real)')
        await sql.execute('create unique index if not exists ping_history_idx on ping_history (timestamp)')
        self.build_ping_history.start()

    @tasks.loop(seconds=30)
    async def build_ping_history(self):
        now = self.build_ping_history._last_iteration.replace(tzinfo=None)
        ping = self.bot.latency * 1000
        async with self.bot.sql as sql:
            await sql.execute('insert into ping_history values ($1, $2) on conflict (timestamp) do nothing', now, ping)

    @build_ping_history.before_loop
    async def before_ping_history(self):
        await self.bot.wait_until_ready()

    @build_ping_history.error
    async def ping_history_error(self, error):
        content = 'Ignoring exception in Ping.build_ping_history'
        await self.bot.send_tb(None, error, ignoring=content)

    @commands.group(invoke_without_command=True)
    async def ping(self, ctx: commands.Context):
        """Quickly test the bot's ping"""

        # Typing delay
        t = time.perf_counter()
        async with ctx.typing():
            t2 = time.perf_counter()

        # Send delay
        embed = discord.Embed(title='Pong!', colour=0xf47fff)
        t3 = time.perf_counter()
        new = await ctx.reply(embed=embed, mention_author=False)
        t4 = time.perf_counter()

        # Report results
        embed.add_field(name='Heartbeat latency', value=f'{self.bot.latency * 1000:.0f} ms')
        embed.add_field(name='Typing delay', value=f'{(t2 - t) * 1000:.0f} ms')
        embed.add_field(name='Message send delay', value=f'{(t4 - t3) * 1000:.0f} ms')
        await new.edit(embed=embed, mention_author=False)

    @staticmethod
    def do_plot_ping(buffer, history):
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
    async def plot_ping(self, ctx, hstart: typing.Union[PastTime, int] = 60, hend: typing.Union[PastTime, int] = 0):
        """Plot the bot's ping history (measured as gateway heartbeat)
        for the indicated number of minutes (default: 60)"""
        if isinstance(hstart, int):
            hstart = ctx.message.created_at - datetime.timedelta(minutes=hstart)
        else:
            hstart = hstart.dt
        if isinstance(hend, int):
            hend = ctx.message.created_at - datetime.timedelta(minutes=hend)
        else:
            hend = hend.dt
        async with ctx.typing():
            fetch_start = time.perf_counter()
            async with self.bot.sql as sql:
                ping_history = dict(await sql.fetch('select * from ping_history where timestamp between $1 and $2 order by timestamp', hstart, hend))
            fetch_end = time.perf_counter()
            if len(ping_history) > 1:
                buffer = io.BytesIO()
                start = time.perf_counter()
                await self.bot.loop.run_in_executor(None, Ping.do_plot_ping, buffer, ping_history)
                end = time.perf_counter()
                buffer.seek(0)
                msg = f'Fetched {len(ping_history)} records in {fetch_end - fetch_start:.3f}s\n' \
                      f'Rendered image in {end - start:.3f}s'
                file = discord.File(buffer, 'ping.png')
            else:
                msg = f'Fetched {len(ping_history)} records in {fetch_end - fetch_start:.3f}s\n' \
                      f'Plotting failed'
                file = None
        await ctx.reply(msg, file=file, mention_author=False)


def setup(bot):
    bot.add_cog(Ping(bot))
