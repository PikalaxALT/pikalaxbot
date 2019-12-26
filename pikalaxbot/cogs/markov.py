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

import re

import discord
from discord.ext import commands

from . import BaseCog
from .utils.markov import Chain


class Markov(BaseCog):
    markov_channels = set()
    config_attrs = 'markov_channels',

    def __init__(self, bot):
        super().__init__(bot)
        self.initialized = False
        self.storedMsgsSet = set()
        self.chain = Chain(store_lowercase=True)
        self.bot.loop.create_task(self.init_chain())

    def cog_check(self, ctx: commands.Context):
        if not self.initialized:
            return False
        if ctx.author.bot:
            return False
        if len(self.markov_channels) == 0:
            return False
        if ctx.prefix is not None:
            return ctx.invoked_with == self.markov.name or ctx.command.parent == self.markov
        if ctx.command != self.markov:
            return False
        if ctx.me.mentioned_in(ctx.message):
            return True
        name_grp = '|'.join({ctx.me.name, ctx.guild.me.display_name})
        if not name_grp:
            raise commands.CheckFailure('Something fucked up!!')
        pat = re.compile(rf'\b({name_grp})\b', re.I)
        return pat.search(ctx.message.clean_content) is not None

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

    def learn_markov(self, message):
        if message.channel.id in self.markov_channels:
            self.storedMsgsSet.add(message.clean_content)
            self.chain.learn_str(message.clean_content)

    def forget_markov(self, message):
        if message.channel.id in self.markov_channels:
            self.chain.unlearn_str(message.clean_content)

    async def learn_markov_from_history(self, channel: discord.TextChannel):
        if channel.permissions_for(channel.guild.me).read_message_history:
            async for msg in channel.history(limit=5000):
                self.learn_markov(msg)
            self.bot.logger.info(f'Markov: Initialized channel {channel}')
            return True
        self.bot.logger.error(f'Markov: missing ReadMessageHistory permission for {channel}')
        return False

    async def init_chain(self):
        await self.fetch()
        await self.bot.wait_until_ready()
        for ch in list(self.markov_channels):
            self.bot.logger.debug('%d', ch)
            channel = self.bot.get_channel(ch)
            if channel is None:
                self.bot.logger.error(f'Markov: unable to find text channel {ch:d}')
                self.markov_channels.discard(ch)
            else:
                await self.learn_markov_from_history(channel)
        self.initialized = True

    @commands.group(hidden=True)
    async def markov(self, ctx):
        """Generate a random word Markov chain."""
        if ctx.invoked_subcommand is None:
            chain = self.gen_msg(len_max=250, n_attempts=10)
            if chain:
                await ctx.send(f'{ctx.author.mention}: {chain}')
            else:
                await ctx.send(f'{ctx.author.mention}: An error has occurred.')

    @markov.command(name='add')
    @commands.is_owner()
    async def add_markov(self, ctx: commands.Context, ch: discord.TextChannel):
        """Add a Markov channel by ID or mention"""
        if ch.id in self.markov_channels:
            await ctx.send(f'Channel {ch} is already being tracked for Markov chains')
        else:
            async with ctx.typing():
                if await self.learn_markov_from_history(ch):
                    await ctx.send(f'Successfully initialized {ch}')
                    self.markov_channels.add(ch.id)
                else:
                    await ctx.send(f'Missing permissions to load {ch}')

    @markov.command(name='delete')
    @commands.is_owner()
    async def del_markov(self, ctx: commands.Context, ch: discord.TextChannel):
        """Remove a Markov channel by ID or mention"""
        if ch.id in self.markov_channels:
            await ctx.send(f'Channel {ch} will no longer be learned')
            self.markov_channels.discard(ch.id)
        else:
            await ctx.send(f'Channel {ch} is not being learned')

    @commands.Cog.listener()
    async def on_message(self, msg: discord.Message):
        self.learn_markov(msg)
        ctx: commands.Context = await self.bot.get_context(msg)
        if ctx.command == self.markov:
            return
        ctx.command = self.markov
        await self.bot.invoke(ctx)

    @commands.Cog.listener()
    async def on_message_edit(self, old, new):
        # Remove old message
        self.forget_markov(old)
        self.learn_markov(new)

    @commands.Cog.listener()
    async def on_message_delete(self, msg):
        self.forget_markov(msg)


def setup(bot):
    bot.add_cog(Markov(bot))
