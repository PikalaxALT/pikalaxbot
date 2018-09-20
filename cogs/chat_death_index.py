import asyncio
from collections import defaultdict, Counter, deque
import discord
import datetime
from discord.ext import commands
from cogs import BaseCog
from utils.botclass import PikalaxBOT
import traceback


class ChatDeathIndex(BaseCog):
    MIN_SAMPLES = 5
    MAX_SAMPLES = 30

    def __init__(self, bot: PikalaxBOT):
        super().__init__(bot)
        self.cdi_samples = defaultdict(deque)
        self.cumcharcount = Counter()
        self.task = self.bot.loop.create_task(self.save_message_count())

    def __unload(self):
        self.task.cancel()

    @staticmethod
    def get_message_cdi_effect(message: discord.Message):
        return len(message.clean_content) / 6

    async def msg_counts_against_chat_death(self, message: discord.Message):
        if message.author.bot:
            return False
        context = await self.bot.get_context(message)
        return not context.valid

    async def save_message_count(self):
        await self.bot.wait_until_ready()
        start = datetime.datetime.now() - datetime.timedelta(minutes=30)

        try:
            for channel in self.bot.get_all_channels():
                if isinstance(channel, discord.TextChannel) and channel.permissions_for(channel.guild.me).read_message_history:
                    samples = deque(0 for i in range(self.MAX_SAMPLES))
                    async for message in channel.history(after=start):  # type: discord.Message
                        if await self.msg_counts_against_chat_death(message):
                            idx = int((message.created_at - start).total_seconds()) // self.MAX_SAMPLES
                            if idx > self.MAX_SAMPLES:
                                await self.bot.owner.send(f'{channel}: {idx} {message.created_at}')
                            samples[idx] += self.get_message_cdi_effect(message)
                    self.cdi_samples[channel.id] = samples
        except Exception as e:
            tb = ''.join(traceback.format_exception(e.__class__, e, e.__traceback__, limit=1))
            await self.bot.owner.send(f'Warning: Failed to prime CDI data.\n'
                                      f'```{tb}```')

        while not self.bot.is_closed():
            await asyncio.sleep(60)
            for channel in self.bot.get_all_channels():
                if isinstance(channel, discord.TextChannel) and channel.permissions_for(channel.guild.me).read_messages:
                    key = channel.id
                    self.cdi_samples[key].append(self.cumcharcount[key])
                    if len(self.cdi_samples[key]) > self.MAX_SAMPLES:
                        self.cdi_samples[key].popleft()
                    self.cumcharcount[key] = 0

    def account_for_message(self, message: discord.Message):
        pass

    @staticmethod
    def to_cdi(avg):
        return int((avg - 64) ** 2 * 2.3) * ((-1) ** (avg >= 64))

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


def setup(bot: PikalaxBOT):
    bot.add_cog(ChatDeathIndex(bot))
