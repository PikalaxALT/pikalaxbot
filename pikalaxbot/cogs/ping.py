import discord
from discord.ext import commands, tasks
from . import *
import io
import asyncpg
import time
import datetime
import matplotlib.pyplot as plt
import typing
import numpy as np
from .utils.converters import PastTime
from .utils.mpl_time_axis import *
from jishaku.functools import executor_function


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
        async with self.bot.sql as sql:  # type: asyncpg.Connection
            await sql.execute('insert into ping_history values ($1, $2) on conflict (timestamp) do nothing', now, ping)

    @build_ping_history.before_loop
    async def before_ping_history(self):
        await self.bot.wait_until_ready()

    @build_ping_history.error
    async def ping_history_error(self, error):
        content = 'Ping.build_ping_history'
        await self.bot.send_tb(None, error, origin=content)

    @commands.group(invoke_without_command=True)
    async def ping(self, ctx: MyContext):
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
        await new.edit(embed=embed, allowed_mentions=discord.AllowedMentions(replied_user=False))

    @staticmethod
    @executor_function
    def do_plot_ping(buffer: typing.BinaryIO, history: dict[datetime.datetime, float]):
        times, values = zip(*history.items())
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
    async def plot_ping(
            self,
            ctx: MyContext,
            hstart: PastTime = None,
            hend: PastTime = None):
        """Plot the bot's ping history (measured as gateway heartbeat)
        for the indicated time interval (default: last 60 minutes)"""
        hstart = hstart.dt or ctx.message.created_at - datetime.timedelta(minutes=60)
        hend = hend.dt or ctx.message.created_at
        async with ctx.typing():
            fetch_start = time.perf_counter()
            async with self.bot.sql as sql:  # type: asyncpg.Connection
                ping_history: dict[datetime.datetime, float] = dict(await sql.fetch(
                    'select * from ping_history '
                    'where timestamp between $1 and $2 '
                    'order by timestamp',
                    hstart,
                    hend
                ))
            fetch_end = time.perf_counter()
            if len(ping_history) > 1:
                buffer = io.BytesIO()
                start = time.perf_counter()
                await Ping.do_plot_ping(buffer, ping_history)
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


def setup(bot: PikalaxBOT):
    bot.add_cog(Ping(bot))
