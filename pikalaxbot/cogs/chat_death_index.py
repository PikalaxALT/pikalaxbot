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

from collections import defaultdict, Counter
import discord
import datetime
from discord.ext import commands, tasks
from . import *
import typing
import io
import time
import matplotlib.pyplot as plt
from jishaku.functools import executor_function


class ChatDeathIndex(BaseCog):
    """Commands for displaying the chat death index of a given channel."""

    MIN_SAMPLES = 5
    MAX_SAMPLES = 30

    def __init__(self, bot):
        super().__init__(bot)
        self.cdi_samples: dict[discord.TextChannel, list[float]] = defaultdict(list)
        self.calculations: dict[discord.TextChannel, list[int]] = defaultdict(list)
        self.cumcharcount: Counter[discord.TextChannel] = Counter()
        self.save_message_count.start()

    def cog_unload(self):
        self.save_message_count.cancel()

    @executor_function
    def plot(self, channels: frozenset[discord.TextChannel], buffer: typing.BinaryIO):
        plt.figure()
        for channel in channels:
            samples = self.calculations[channel]
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

    @tasks.loop(seconds=60)
    async def save_message_count(self):
        for channel in self.bot.get_all_channels():
            self.cdi_samples[channel].append(self.cumcharcount[channel])
            self.cdi_samples[channel] = self.cdi_samples[channel][-ChatDeathIndex.MAX_SAMPLES:]
            self.calculations[channel].append(ChatDeathIndex.samples_to_cdi(self.cdi_samples[channel]))
            self.calculations[channel] = self.calculations[channel][-ChatDeathIndex.MAX_SAMPLES:]
            self.cumcharcount[channel] = 0

    def account_for_message(self, channel: discord.TextChannel, start: datetime.datetime):
        def inner(message: discord.Message):
            idx = int((message.created_at - start).total_seconds()) // 60
            self.cdi_samples[channel][idx] += ChatDeathIndex.get_message_cdi_effect(message)
        return inner

    async def init_channel(self, channel: discord.TextChannel, now: datetime.datetime):
        start = now - datetime.timedelta(minutes=2 * ChatDeathIndex.MAX_SAMPLES - 1)
        if ChatDeathIndex.can_get_messages(channel):
            self.cdi_samples[channel] = [0. for _ in range(2 * ChatDeathIndex.MAX_SAMPLES - 1)]
            await channel.history(
                before=now,
                after=start
            ).filter(
                self.msg_counts_against_chat_death
            ).map(
                self.account_for_message(channel, start)
            ).flatten()
            self.calculations[channel] = [ChatDeathIndex.samples_to_cdi(
                    self.cdi_samples[channel][i:i + ChatDeathIndex.MAX_SAMPLES]
                ) for i in range(ChatDeathIndex.MAX_SAMPLES)]
        self.cdi_samples[channel] = self.cdi_samples[channel][-ChatDeathIndex.MAX_SAMPLES:]
        self.cumcharcount[channel] = 0

    @save_message_count.before_loop
    async def start_message_count(self):
        await self.bot.wait_until_ready()
        now = datetime.datetime.now()

        for guild in self.bot.guilds:  # type: discord.Guild
            for channel in guild.text_channels:
                await self.init_channel(channel, now)

    @save_message_count.error
    async def save_message_error(self, error):
        await self.bot.send_tb(None, error, origin='ChatDathIndex.save_message_count')

    @staticmethod
    def to_cdi(avg: float):
        return round((avg - 64) ** 2 * 2.3) * ((-1) ** (avg >= 64))

    @staticmethod
    def accumulate(samples: list[float]):
        n = len(samples)
        if n == 0:
            return 0.
        return 2 * sum((i + 1) * x for i, x in enumerate(samples)) / (n * (n + 1))

    @staticmethod
    def samples_to_cdi(samples: list[float]):
        return ChatDeathIndex.to_cdi(ChatDeathIndex.accumulate(samples))

    @BaseCog.listener()
    async def on_message(self, message: discord.Message):
        if await self.msg_counts_against_chat_death(message):
            self.cumcharcount[message.channel.id] += ChatDeathIndex.get_message_cdi_effect(message)

    @commands.command(name='cdi')
    async def get_cdi(self, ctx: MyContext, channel: discord.TextChannel = None):
        """Returns the Chat Death Index of the given channel (if not specified, uses the current channel)"""

        channel = channel or ctx.channel
        chat_avg = self.cdi_samples[channel]
        n = len(chat_avg)
        if n < ChatDeathIndex.MIN_SAMPLES:
            await ctx.send(f'I cannot determine the Chat Death Index of {channel.mention} at this time.')
        else:
            accum = ChatDeathIndex.accumulate(chat_avg)
            cdi = ChatDeathIndex.to_cdi(accum)
            await ctx.send(f'Current Chat Death Index of {channel.mention}: {cdi} ({accum:.3f})')

    @commands.command(name='plot-cdi')
    async def plot_cdi(self, ctx: MyContext, *channels: discord.TextChannel):
        """Plots the Chat Death Index history of the given channel (if not specified, uses the current channel)"""

        channels = frozenset(channels or (ctx.channel,))
        async with ctx.typing():
            mem_buffer = io.BytesIO()
            start = time.perf_counter()
            await self.plot(channels, mem_buffer)
            end = time.perf_counter()
            mem_buffer.seek(0)
            file = discord.File(mem_buffer, filename='cdi.png')
        await ctx.send(f'Task completed in {end - start:.3f}s', file=file)

    @commands.command(name='plot-all-cdi')
    async def plot_all_cdi(self, ctx: MyContext):
        """Plots the Chat Death Index history of all channels the bot can see.
        NSFW channels are skipped unless called in an NSFW channel."""

        nsfw = ctx.channel.is_nsfw()
        chs = [ch for ch in ctx.guild.text_channels if ch.is_nsfw() <= nsfw and ChatDeathIndex.can_get_messages(ch)]
        await self.plot_cdi(ctx, *chs)

    @BaseCog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        now = datetime.datetime.now()
        for channel in guild.text_channels:
            await self.init_channel(channel, now)


def setup(bot: PikalaxBOT):
    bot.add_cog(ChatDeathIndex(bot))
