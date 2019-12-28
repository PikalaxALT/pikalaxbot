from collections import defaultdict, Counter
import discord
import datetime
from discord.ext import commands, tasks
from . import BaseCog
import typing
import traceback
import matplotlib
import io
matplotlib.use('Agg')
import matplotlib.pyplot as plt


class ChatDeathIndex(BaseCog):
    MIN_SAMPLES = 5
    MAX_SAMPLES = 30

    def __init__(self, bot):
        super().__init__(bot)
        self.cdi_samples = defaultdict(list)
        self.calculations = defaultdict(list)
        self.cumcharcount = Counter()
        self.save_message_count.start()

    def __unload(self):
        self.save_message_count.cancel()

    def plot(self, channels: typing.Tuple[discord.TextChannel], buffer):
        plt.figure()
        for channel in channels:
            samples = self.calculations[channel.id]
            plt.plot(list(range(1 - len(samples), 1)), samples, label=f'#{channel}')
        plt.xlabel('Minutes ago')
        plt.ylabel('CDI')
        plt.legend(loc=0)
        plt.savefig(buffer)
        plt.close()

    @staticmethod
    def get_message_cdi_effect(message: discord.Message) -> float:
        return len(message.clean_content) / 6

    @staticmethod
    def can_get_messages(channel: typing.Any) -> bool:
        if not isinstance(channel, discord.TextChannel):
            return False
        return channel.permissions_for(channel.guild.me).read_message_history

    async def msg_counts_against_chat_death(self, message: discord.Message) -> bool:
        if message.author.bot:
            return False
        context = await self.bot.get_context(message)
        return not context.valid

    @tasks.loop(seconds=60, reconnect=True)
    async def save_message_count(self):
        for channel in self.bot.get_all_channels():
            self.cdi_samples[channel.id].append(self.cumcharcount[channel.id])
            self.cdi_samples[channel.id] = self.cdi_samples[channel.id][-ChatDeathIndex.MAX_SAMPLES:]
            self.calculations[channel.id].append(ChatDeathIndex.samples_to_cdi(self.cdi_samples[channel.id]))
            self.calculations[channel.id] = self.calculations[channel.id][-ChatDeathIndex.MAX_SAMPLES:]
            self.cumcharcount[channel.id] = 0

    async def init_channel(self, channel: discord.TextChannel, now):
        start = now - datetime.timedelta(minutes=2 * ChatDeathIndex.MAX_SAMPLES - 1)
        if ChatDeathIndex.can_get_messages(channel):
            self.cdi_samples[channel.id] = [0 for _ in range(2 * ChatDeathIndex.MAX_SAMPLES - 1)]
            async for message in channel.history(before=now, after=start):  # type: discord.Message
                if await self.msg_counts_against_chat_death(message):
                    idx = int((message.created_at - start).total_seconds()) // 60
                    self.cdi_samples[channel.id][idx] += ChatDeathIndex.get_message_cdi_effect(message)
        for i in range(ChatDeathIndex.MAX_SAMPLES):
            self.calculations[channel.id].append(ChatDeathIndex.samples_to_cdi(self.cdi_samples[channel.id][i:i + ChatDeathIndex.MAX_SAMPLES]))
        self.cdi_samples[channel.id] = self.cdi_samples[channel.id][-ChatDeathIndex.MAX_SAMPLES:]
        self.cumcharcount[channel.id] = 0

    @save_message_count.before_loop
    async def start_message_count(self):
        await self.bot.wait_until_ready()
        now = datetime.datetime.now()

        for channel in self.bot.get_all_channels():
            await self.init_channel(channel, now)

    @staticmethod
    def to_cdi(avg):
        return round((avg - 64) ** 2 * 2.3) * ((-1) ** (avg >= 64))

    @staticmethod
    def accumulate(samples):
        n = len(samples)
        if n == 0:
            return 0
        return 2 * sum((i + 1) * x for i, x in enumerate(samples)) / (n * (n + 1))

    @staticmethod
    def samples_to_cdi(samples):
        return ChatDeathIndex.to_cdi(ChatDeathIndex.accumulate(samples))

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if await self.msg_counts_against_chat_death(message):
            self.cumcharcount[message.channel.id] += ChatDeathIndex.get_message_cdi_effect(message)

    @commands.command(name='cdi')
    async def get_cdi(self, ctx: commands.Context, channel: discord.TextChannel = None):
        """Returns the Chat Death Index of the given channel (if not specified, uses the current channel)"""
        channel = channel or ctx.channel
        chat_avg = self.cdi_samples[channel.id]
        n = len(chat_avg)
        if n < ChatDeathIndex.MIN_SAMPLES:
            await ctx.send(f'I cannot determine the Chat Death Index of {channel.mention} at this time.')
        else:
            accum = ChatDeathIndex.accumulate(chat_avg)
            cdi = ChatDeathIndex.to_cdi(accum)
            await ctx.send(f'Current Chat Death Index of {channel.mention}: {cdi} ({accum:.3f})')

    @commands.command(name='plot-cdi')
    async def plot_cdi(self, ctx: commands.Context, *channels: discord.TextChannel):
        """Plots the Chat Death Index history of the given channel (if not specified, uses the current channel)"""
        channels = set(channels) or (ctx.channel,)
        async with ctx.typing():
            mem_buffer = io.BytesIO()
            await self.bot.loop.run_in_executor(None, self.plot, channels, mem_buffer)
            mem_buffer.seek(0)
            file = discord.File(mem_buffer, filename='cdi.png')
        await ctx.send(file=file)

    @commands.command(name='plot-all-cdi')
    async def plot_all_cdi(self, ctx: commands.Context):
        nsfw = ctx.channel.is_nsfw()
        chs = [ch for ch in ctx.guild.text_channels if ch.is_nsfw() <= nsfw and ChatDeathIndex.can_get_messages(ch)]
        await ctx.invoke(self.plot_cdi, *chs)

    @plot_cdi.error
    async def plot_cdi_error(self, ctx, exc):
        await ctx.send('```\n' + ''.join(traceback.format_exception(exc.__class__, exc, None)) + '\n```')

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        now = datetime.datetime.now()
        for channel in guild.text_channels:
            await self.init_channel(channel, now)


def setup(bot):
    bot.add_cog(ChatDeathIndex(bot))
