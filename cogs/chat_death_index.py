import asyncio
from collections import defaultdict, Counter, deque
import discord
from discord.ext import commands
from cogs import BaseCog
from utils.botclass import PikalaxBOT


class ChatDeathIndex(BaseCog):
    MIN_SAMPLES = 5
    MAX_SAMPLES = 30

    def __init__(self, bot: PikalaxBOT):
        super().__init__(bot)
        self.cdi_samples = defaultdict(deque)
        self.cumcharcount = Counter()

    async def calc_message_average(self):
        await self.bot.wait_until_ready()
        while True:
            await asyncio.sleep(60)
            for key, value in self.cumcharcount.items():
                self.cdi_samples[key].append(value)
                if len(self.cdi_samples[key]) > self.MAX_SAMPLES:
                    self.cdi_samples[key].popleft()
                self.cumcharcount[key] = 0

    def account_for_message(self, message: discord.Message):
        pass

    @staticmethod
    def to_cdi(avg):
        return int((avg - 64) ** 2 * 2.3) * (-1) ** (avg < 64)

    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        ctx: commands.Context = await self.bot.get_context(message)
        if ctx.valid:
            return
        self.cumcharcount[message.channel.id] += len(message.clean_content) / 6

    @commands.command(name='cdi')
    async def get_cdi(self, ctx: commands.Context, channel: discord.TextChannel = None):
        channel = channel or ctx.channel
        chat_avg = self.cdi_samples[channel.id]
        n = len(chat_avg)
        if len(chat_avg) < self.MIN_SAMPLES:
            await ctx.send(f'I cannot determine the Chat Death Index of {channel.mention} at this time.')
        else:
            accum = 2 * sum((i + 1) * x for i, x in enumerate(chat_avg)) / (n * (n + 1))
            cdi = self.to_cdi(accum)
            await ctx.send(f'Current Chat Death Index: {cdi} ({accum:.3f})')


def setup(bot: PikalaxBOT):
    bot.add_cog(ChatDeathIndex(bot))
