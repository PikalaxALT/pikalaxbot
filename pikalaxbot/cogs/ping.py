# PikalaxBOT - A Discord bot in discord.py
# Copyright (C) 2018-2021  PikalaxALT
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import discord
from discord.ext import commands, tasks
from . import *
import io
import time
import datetime
import matplotlib.pyplot as plt
import typing
import numpy as np
from .utils.converters import PastTime
from .utils.mpl_time_axis import *
from jishaku.functools import executor_function

from sqlalchemy import Column, TIMESTAMP, REAL, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection


class PingHistory(BaseTable):
    timestamp = Column(TIMESTAMP, primary_key=True)
    latency = Column(REAL)

    @classmethod
    async def insert(cls, conn: AsyncConnection, now: datetime.datetime, latency: float):
        statement = insert(cls).values(timestamp=now, latency=latency)
        await conn.execute(statement)

    @classmethod
    async def fetch(cls, conn: AsyncConnection, start: datetime.datetime, end: datetime.datetime):
        statement = select(cls).where(cls.timestamp.between(start, end)).order_by(cls.timestamp)
        result = await conn.execute(statement)
        return result.all()


class Ping(BaseCog):
    """Commands for testing the bot's ping, and for reporting history."""

    def cog_unload(self):
        self.build_ping_history.cancel()

    async def init_db(self, sql):
        await PingHistory.create(sql)
        self.build_ping_history.start()

    @tasks.loop(seconds=30)
    async def build_ping_history(self):
        now = self.build_ping_history._last_iteration.replace(tzinfo=None)
        ping = self.bot.latency * 1000
        async with self.bot.sql as sql:
            await PingHistory.insert(sql, now, ping)

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
        hstart = hstart.dt if hstart else ctx.message.created_at - datetime.timedelta(minutes=60)
        hend = hend.dt if hend else ctx.message.created_at
        async with ctx.typing():
            fetch_start = time.perf_counter()
            async with self.bot.sql as sql:
                ping_history: dict[datetime.datetime, float] = dict(await PingHistory.fetch(sql, hstart, hend))
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
