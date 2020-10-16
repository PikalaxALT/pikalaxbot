import discord
from discord.ext import commands, tasks
from collections import Counter, defaultdict
from . import BaseCog
import time
import datetime
import io
import matplotlib.pyplot as plt
from .utils.converters import HumanTime


class MemberStatus(BaseCog):
    def __init__(self, bot):
        super().__init__(bot)
        self.counters = defaultdict(list)
        self.update_counters.start()
        self.start_time = None

    @tasks.loop(seconds=30)
    async def update_counters(self):
        for guild in self.bot.guilds:
            self.counters[guild.id].append(Counter(m.status for m in guild.members))

    @update_counters.before_loop
    async def update_counters_before_loop(self):
        await self.bot.wait_until_ready()
        self.start_time = datetime.datetime.utcnow()

    def do_plot_status_history(self, buffer, ctx, history):
        mapping = {
            discord.Status.online: '#43B581',
            discord.Status.offline: '#747F8D',
            discord.Status.dnd: '#F04747',
            discord.Status.idle: '#FAA61A',
            'other': '#7289DA'
        }

        values = self.counters[ctx.guild.id]
        if history > 0:
            values = values[-2 * history:]
        history = len(values)
        plt.figure()
        counts = {key: [v[key] for v in values] for key in mapping}
        counts['other'] = [sum(v[key] for key in v if key not in mapping) for v in values]
        for key, value in counts.items():
            plt.plot(range(history), value, c=mapping[key], label=str(key).title())
        xtickvalues = list(range(0, history, history // 10 + (history % 10 != 0)))
        xticklabels = [(self.start_time + datetime.timedelta(seconds=i * 30)).strftime('%Y-%m-%d\nT%H:%M:%S') for i in xtickvalues]
        plt.xticks(xtickvalues, xticklabels, rotation=45, ha='right', ma='right')
        plt.xlabel('Time (UTC)')
        plt.ylabel('Number of users')
        plt.legend(loc=0)
        plt.tight_layout()
        plt.savefig(buffer)
        plt.close()

    @commands.guild_only()
    @commands.check(lambda ctx: ctx.cog.start_time)
    @commands.command(name='userstatus')
    async def plot_status(self, ctx, history: HumanTime = datetime.timedelta(minutes=1)):
        """Plot history of user status counts in the current guild."""
        buffer = io.BytesIO()
        start = time.perf_counter()
        await self.bot.loop.run_in_executor(None, self.do_plot_status_history, buffer, ctx, round(history.total_seconds()))
        end = time.perf_counter()
        buffer.seek(0)
        await ctx.send(f'Completed in {end - start:.3f}s', file=discord.File(buffer, 'status.png'))


def setup(bot):
    bot.add_cog(MemberStatus(bot))
