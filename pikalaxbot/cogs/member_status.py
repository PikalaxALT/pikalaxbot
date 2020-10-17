import discord
from discord.ext import commands, tasks
from collections import Counter, defaultdict
from . import BaseCog
import time
import datetime
import io
import matplotlib.pyplot as plt
import typing
from .utils.converters import PastTime
from .utils.mpl_time_axis import set_time_xlabs


class MemberStatus(BaseCog):
    colormap = {
        discord.Status.online: '#43B581',
        discord.Status.offline: '#747F8D',
        discord.Status.dnd: '#F04747',
        discord.Status.idle: '#FAA61A'
    }

    def __init__(self, bot):
        super().__init__(bot)
        self.counters = defaultdict(dict)
        self.update_counters.start()

    def cog_unload(self):
        self.update_counters.cancel()

    async def init_db(self, sql):
        await sql.execute('create table if not exists memberstatus (guild_id integer, timestamp integer, online integer, offline integer, dnd integer, idle integer)')
        await sql.execute('create unique index if not exists memberstatus_idx on memberstatus (guild_id, timestamp)')
        for guild_id, timestamp, online, offline, dnd, idle in await sql.execute_fetchall('select * from memberstatus'):
            self.counters[guild_id][datetime.datetime.utcfromtimestamp(timestamp)] = {
                discord.Status.online: online,
                discord.Status.offline: offline,
                discord.Status.dnd: dnd,
                discord.Status.idle: idle
            }

    @tasks.loop(seconds=30)
    async def update_counters(self):
        now = self.update_counters._last_iteration.replace(tzinfo=None)
        sql_now = now.timestamp()
        to_insert = []
        for guild in self.bot.guilds:
            counts = Counter(m.status for m in guild.members)
            self.counters[guild.id][now] = counts
            to_insert.append([
                guild.id,
                sql_now,
                counts[discord.Status.online],
                counts[discord.Status.offline],
                counts[discord.Status.dnd],
                counts[discord.Status.idle]
            ])
        async with self.bot.sql as sql:
            await sql.executemany('insert or ignore into membserstatus values (?, ?, ?, ?, ?, ?)', to_insert)

    @update_counters.before_loop
    async def update_counters_before_loop(self):
        await self.bot.wait_until_ready()

    def do_plot_status_history(self, buffer, ctx, history):
        times, values = zip(*sorted([t for t in self.counters[ctx.guild.id].items() if t[0] >= history]))
        plt.figure()
        counts = {key: [v[key] for v in values] for key in self.colormap}
        ax: plt.Axes = plt.gca()
        for key, value in counts.items():
            ax.plot(times, value, c=self.colormap[key], label=str(key).title())
        set_time_xlabs(ax, times)
        plt.xlabel('Time (UTC)')
        plt.ylabel('Number of users')
        plt.legend(loc=0)
        plt.tight_layout()
        plt.savefig(buffer)
        plt.close()

    @commands.guild_only()
    @commands.check(lambda ctx: ctx.cog.counters)
    @commands.command(name='userstatus')
    async def plot_status(self, ctx, history: typing.Union[PastTime, int] = 60):
        """Plot history of user status counts in the current guild."""
        if isinstance(history, int):
            history = ctx.message.created_at - datetime.timedelta(minutes=history)
        else:
            history = history.dt
        buffer = io.BytesIO()
        start = time.perf_counter()
        await self.bot.loop.run_in_executor(None, self.do_plot_status_history, buffer, ctx, history)
        end = time.perf_counter()
        buffer.seek(0)
        await ctx.send(f'Completed in {end - start:.3f}s', file=discord.File(buffer, 'status.png'))


def setup(bot):
    bot.add_cog(MemberStatus(bot))
