import discord
from discord.ext import commands, tasks
from collections import Counter, defaultdict
from . import BaseCog
import time
import datetime
import io
import matplotlib.pyplot as plt
import typing
import traceback
from .utils.converters import PastTime
from .utils.mpl_time_axis import *
import numpy as np


class MemberStatus(BaseCog):
    """Commands for showing the historical distribution of user statuses
    (online, offline, etc.) in the guild."""

    colormap = {
        discord.Status.online: '#43B581',
        discord.Status.offline: '#747F8D',
        discord.Status.dnd: '#F04747',
        discord.Status.idle: '#FAA61A'
    }

    def cog_unload(self):
        self.update_counters.cancel()

    async def init_db(self, sql):
        await sql.execute('create table if not exists memberstatus (guild_id integer, timestamp real, online integer, offline integer, dnd integer, idle integer)')
        await sql.execute('create unique index if not exists memberstatus_idx on memberstatus (guild_id, timestamp)')
        self.update_counters.start()

    @tasks.loop(seconds=30)
    async def update_counters(self):
        now = self.update_counters._last_iteration.replace(tzinfo=None)
        sql_now = now.timestamp()
        to_insert = []
        for guild in self.bot.guilds:
            counts = Counter(m.status for m in guild.members)
            to_insert.append([
                guild.id,
                sql_now,
                counts[discord.Status.online],
                counts[discord.Status.offline],
                counts[discord.Status.dnd],
                counts[discord.Status.idle]
            ])
        async with self.bot.sql as sql:
            await sql.executemany('insert or ignore into memberstatus values (?, ?, ?, ?, ?, ?)', to_insert)

    @update_counters.before_loop
    async def update_counters_before_loop(self):
        await self.bot.wait_until_ready()

    @update_counters.error
    async def update_counters_error(self, error):
        s = traceback.format_exception(error.__class__, error, error.__traceback__)
        content = f'Ignoring exception in MemberStatus.update_counters\n{s}'
        await self.bot.send_tb(content)

    def do_plot_status_history(self, buffer, history):
        times, values = zip(*history)
        plt.figure()
        counts = {key: [v[key] for v in values] for key in self.colormap}
        ax: plt.Axes = plt.gca()
        idxs = thin_points(len(times), 1000)
        for key, value in counts.items():
            ax.plot(np.array(times)[idxs], np.array(value)[idxs], c=self.colormap[key], label=str(key).title())
        set_time_xlabs(ax, times)
        _, ymax = ax.get_ylim()
        ax.set_ylim(0, ymax)
        plt.xlabel('Time (UTC)')
        plt.ylabel('Number of users')
        plt.legend(loc=0)
        plt.tight_layout()
        plt.savefig(buffer)
        plt.close()

    @commands.guild_only()
    @commands.command(name='userstatus')
    async def plot_status(self, ctx, hstart: typing.Union[PastTime, int] = 60, hend: typing.Union[PastTime, int] = 0):
        """Plot history of user status counts in the current guild."""
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
                async with sql.execute('select timestamp, online, offline, dnd, idle from memberstatus where guild_id = ? and timestamp >= ? and timestamp < ? order by timestamp', (ctx.guild.id, hstart.timestamp(), hend.timestamp())) as cur:
                    counts = [(datetime.datetime.fromtimestamp(row[0]), {name: count for name, count in zip(discord.Status, row[1:])}) async for row in cur]
            fetch_end = time.perf_counter()
            buffer = io.BytesIO()
            start = time.perf_counter()
            await self.bot.loop.run_in_executor(None, self.do_plot_status_history, buffer, counts)
            end = time.perf_counter()
        buffer.seek(0)
        await ctx.send(
            f'Fetched records in {fetch_end - fetch_start:.3f}s\n'
            f'Rendered image in {end - start:.3f}s',
            file=discord.File(buffer, 'status.png')
        )


def setup(bot):
    bot.add_cog(MemberStatus(bot))
