# PikalaxBOT - A Discord bot in discord.py
# Copyright (C) 2018  PikalaxALT
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

import asyncio
import discord
from discord.ext import commands
from utils.default_cog import Cog
from utils.markov import Chain


class Markov(Cog):
    markov_channels = set()
    config_attrs = 'markov_channels',

    def __init__(self, bot):
        super().__init__(bot)
        self.initialized = False
        self.storedMsgsSet = set()
        self.chain = Chain(store_lowercase=True)

    def __local_check(self, ctx: commands.Context):
        if not self.initialized:
            return False
        if ctx.author.bot:
            return False
        if not ctx.channel.permissions_for(ctx.me).send_messages:
            return False
        if len(self.markov_channels) == 0:
            return False
        if ctx.command == self.markov:
            return True
        if ctx.command is not None:
            return False
        if ctx.me.mentioned_in(ctx.message):
            return True
        words = ctx.message.clean_content.lower().split()
        if ctx.me.name.lower() in words:
            return True
        return ctx.me.nick.lower() in words

    def gen_msg(self, len_max=64, n_attempts=5):
        longest = ''
        lng_cnt = 0
        chain = self.chain
        if chain is not None:
            for i in range(n_attempts):
                cur = chain.generate(len_max)
                if len(cur) > lng_cnt:
                    msg = ' '.join(cur)
                    if i == 0 or msg not in self.storedMsgsSet:
                        lng_cnt = len(cur)
                        longest = msg
                        if lng_cnt == len_max:
                            break
        return longest

    def learn_markov(self, ctx):
        if ctx.channel.id in self.markov_channels:
            self.storedMsgsSet.add(ctx.message.clean_content)
            self.chain.learn_str(ctx.message.clean_content)

    def forget_markov(self, ctx):
        if ctx.channel.id in self.markov_channels:
            self.chain.unlearn_str(ctx.message.clean_content)

    async def learn_markov_from_history(self, channel: discord.TextChannel):
        if channel.permissions_for(channel.guild.me).read_message_history:
            async for msg in channel.history(limit=5000):
                ctx = await self.bot.get_context(msg)
                self.learn_markov(ctx)
                self.bot.logger.info(f'Markov: Initialized channel {channel}')
                return True
        self.bot.logger.error(f'Markov: missing ReadMessageHistory permission for {channel}')
        return False

    async def on_ready(self):
        if not self.initialized:
            await self.fetch()
            for ch in list(self.markov_channels):
                channel = self.bot.get_channel(ch)
                if channel is None:
                    self.bot.logger.error(f'Markov: unable to find text channel {ch:d}')
                    self.markov_channels.discard(ch)
                else:
                    await self.learn_markov_from_history(channel)
            self.initialized = True

    @commands.command(hidden=True)
    async def markov(self, ctx):
        """Generate a random word Markov chain."""
        chain = self.gen_msg(len_max=250, n_attempts=10)
        if chain:
            await ctx.send(f'{ctx.author.mention}: {chain}')
        else:
            await ctx.send(f'{ctx.author.mention}: An error has occurred.')

    async def on_message(self, msg: discord.Message):
        ctx: commands.Context = await self.bot.get_context(msg)
        self.learn_markov(ctx)
        if ctx.command == self.markov:
            return
        ctx.command = None
        if await self.bot.can_run(ctx):
            ctx.command = self.markov
            await self.bot.invoke(ctx)

    async def on_message_edit(self, old, new):
        # Remove old message
        ctx = await self.bot.get_context(old)
        self.forget_markov(ctx)

        # Add new message
        ctx = await self.bot.get_context(new)
        self.learn_markov(ctx)

    async def on_message_delete(self, msg):
        ctx = await self.bot.get_context(msg)
        self.forget_markov(ctx)


def setup(bot):
    bot.add_cog(Markov(bot))
