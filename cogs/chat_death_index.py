from collections import defaultdict, Counter
import discord
import datetime
from discord.ext import commands, tasks
from cogs import BaseCog
from utils.botclass import PikalaxBOT
import typing
import traceback
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


class ChatDeathIndex(BaseCog):
    MIN_SAMPLES = 5
    MAX_SAMPLES = 30

    def __init__(self, bot: PikalaxBOT):
        super().__init__(bot)
        self.cdi_samples = defaultdict(list)
        self.cumcharcount = Counter()

    def __unload(self):
        self.save_message_count.cancel()

    def plot(self, channel: discord.TextChannel):
        try:
            filename = f'{channel}.{datetime.datetime.utcnow().timestamp()}.png'
            samples = self.cdi_samples[channel.id]
            plt.figure()
            plt.plot(range(1 - self.MAX_SAMPLES, 1), map(self.to_cdi, samples))
            plt.xlabel('Time (min)')
            plt.ylabel('CDI')
            plt.title(f'#{channel}')
            plt.savefig(filename)
            plt.close()
            return filename
        except Exception as e:
            return e

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
            self.cdi_samples[channel.id] = self.cdi_samples[channel.id][-self.MAX_SAMPLES:]
            self.cumcharcount[channel.id] = 0

    @commands.Cog.listener()
    async def on_ready(self):
        now = datetime.datetime.now()
        start = now - datetime.timedelta(minutes=self.MAX_SAMPLES)

        for channel in self.bot.get_all_channels():
            if self.can_get_messages(channel):
                self.cdi_samples[channel.id] = [0 for _ in range(self.MAX_SAMPLES)]
                async for message in channel.history(before=now, after=start):  # type: discord.Message
                    if await self.msg_counts_against_chat_death(message):
                        idx = int((message.created_at - start).total_seconds()) // 60
                        self.cdi_samples[channel.id][idx] += self.get_message_cdi_effect(message)
            self.cumcharcount[channel.id] = 0
        self.save_message_count.start()

    def account_for_message(self, message: discord.Message):
        pass

    @staticmethod
    def to_cdi(avg):
        return round((avg - 64) ** 2 * 2.3) * ((-1) ** (avg >= 64))

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if await self.msg_counts_against_chat_death(message):
            self.cumcharcount[message.channel.id] += self.get_message_cdi_effect(message)

    @commands.command(name='cdi')
    async def get_cdi(self, ctx: commands.Context, channel: discord.TextChannel = None):
        """Returns the Chat Death Index of the given channel (if not specified, uses the current channel)"""
        channel = channel or ctx.channel
        chat_avg = self.cdi_samples[channel.id]
        n = len(chat_avg)
        if len(chat_avg) < self.MIN_SAMPLES:
            await ctx.send(f'I cannot determine the Chat Death Index of {channel.mention} at this time.')
        else:
            accum = 2 * sum((i + 1) * x for i, x in enumerate(chat_avg)) / (n * (n + 1))
            cdi = self.to_cdi(accum)
            await ctx.send(f'Current Chat Death Index of {channel.mention}: {cdi} ({accum:.3f})')

    @commands.command(name='plot-cdi')
    async def plot_cdi(self, ctx: commands.Context, channel: discord.TextChannel = None):
        channel = channel or ctx.channel
        await ctx.typing()
        filename = await self.bot.loop.run_in_executor(None, self.plot, channel)
        if isinstance(filename, Exception):
            raise filename
        file = discord.File(filename)
        await ctx.send(file=file)

    @plot_cdi.error
    async def plot_cdi_error(self, ctx, exc):
        await ctx.send('```\n' + traceback.format_exception(exc.__class__, exc, None) + '\n```')


def setup(bot: PikalaxBOT):
    bot.add_cog(ChatDeathIndex(bot))
