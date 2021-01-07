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
import typing

import discord
from discord.ext import commands

from . import *
from .utils.markov import Chain


class MarkovNoInit(commands.CheckFailure):
    pass


class Markov(BaseCog):
    """Commands and listeners for generating random word Markov chains."""

    markov_channels: set[int] = set()
    config_attrs = 'markov_channels',

    def __init__(self, bot):
        super().__init__(bot)
        self.initialized = False
        self.storedMsgsSet: set[str] = set()
        self.chain = Chain(store_lowercase=True)
        self._init_task = self.bot.loop.create_task(self.init_chain())
        self.prefix_reminder_cooldown = commands.CooldownMapping.from_cooldown(1, 600, commands.BucketType.channel)
        self.no_init_error_cooldown = commands.CooldownMapping.from_cooldown(1, 60, commands.BucketType.channel)

    def cog_unload(self):
        self._init_task and self._init_task.cancel()

    def cog_check(self, ctx: MyContext):
        def inner():
            # If a command was invoked directly, the check passes.
            if ctx.invoked_with == self.markov.name:
                return True
            # Invoked from on_message without command.
            name_grp = '|'.join({ctx.me.name, ctx.me.display_name, 'doot'})
            return re.search(rf'\b({name_grp})|<@!?{self.bot.user.id}>\b', ctx.message.clean_content, re.I) is not None

        if not inner():
            return False

        # Check that the cog is initialized
        if not self.initialized:
            raise MarkovNoInit
        return True

    async def cog_command_error(self, ctx: MyContext, error: commands.CommandError):
        if isinstance(error, MarkovNoInit) and not self.no_init_error_cooldown.update_rate_limit(ctx.message):
            embed = await self.get_prefix_help_embed(ctx)
            await ctx.reply('Still compiling data for Markov, check again in a minute', embed=embed, delete_after=10)

    def gen_msg(self, len_max=64, n_attempts=5):
        longest = ''
        lng_cnt = 0
        chain = self.chain
        if chain:
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

    def learn_markov(self, message: discord.Message):
        if message.channel.id in self.markov_channels:
            self.storedMsgsSet.add(message.clean_content)
            self.chain.learn_str(message.clean_content)

    def forget_markov(self, message: discord.Message):
        if message.channel.id in self.markov_channels:
            self.chain.unlearn_str(message.clean_content)

    async def learn_markov_from_history(self, channel: discord.TextChannel):
        if channel.permissions_for(channel.guild.me).read_message_history:
            async for msg in channel.history(limit=5000):
                self.learn_markov(msg)
            self.log_info('Markov: Initialized channel %s', channel)
            return True
        self.log_error('Markov: missing ReadMessageHistory permission for %s', channel)
        return False

    async def init_chain(self):
        await self.bot.wait_until_ready()
        await self.fetch()
        for ch in list(self.markov_channels):
            self.log_debug('%d', ch)
            channel = self.bot.get_channel(ch)
            if channel is None:
                self.log_error('Markov: unable to find text channel %d', ch)
                self.markov_channels.discard(ch)
            else:
                await self.learn_markov_from_history(channel)
        self.initialized = True
        self._init_task = None

    async def get_prefix_help_embed(self, ctx: MyContext):
        first_word = ctx.message.content.split()[0]
        mentions = {f'<@{self.bot.user.id}>', f'<@!{self.bot.user.id}>'}
        if first_word in mentions \
                and not ctx.prefix \
                and not self.prefix_reminder_cooldown.update_rate_limit(ctx.message):
            prefix, *_ = await self.bot.get_prefix(ctx.message)
            return discord.Embed(description=f'Trying to get one of my commands? Type `{prefix}help`', colour=0xf47fff)

    @commands.check(lambda ctx: len(ctx.cog.markov_channels) != 0)
    @commands.group(hidden=True, invoke_without_command=True)
    async def markov(self, ctx: MyContext, *, recipient: typing.Optional[discord.Member]):
        """Generate a random word Markov chain."""
        recipient = recipient or ctx.author
        chain = self.gen_msg(len_max=250, n_attempts=10) or 'An error has occurred.'
        embed = await self.get_prefix_help_embed(ctx)
        if recipient == ctx.author:
            await ctx.reply(chain, embed=embed)
        else:
            await ctx.send(f'{recipient.mention}: {chain}', embed=embed)

    @markov.command(name='add')
    @commands.is_owner()
    async def add_markov(self, ctx: MyContext, ch: discord.TextChannel):
        """Add a Markov channel by ID or mention"""
        if ch.id in self.markov_channels:
            await ctx.reply(f'Channel {ch} is already being tracked for Markov chains')
        else:
            async with ctx.typing():
                if await self.learn_markov_from_history(ch):
                    await ctx.reply(f'Successfully initialized {ch}')
                    self.markov_channels.add(ch.id)
                else:
                    await ctx.reply(f'Missing permissions to load {ch}')

    @markov.command(name='delete')
    @commands.is_owner()
    async def del_markov(self, ctx: MyContext, ch: discord.TextChannel):
        """Remove a Markov channel by ID or mention"""
        if ch.id in self.markov_channels:
            await ctx.reply(f'Channel {ch} will no longer be learned')
            self.markov_channels.discard(ch.id)
        else:
            await ctx.reply(f'Channel {ch} is not being learned')

    @BaseCog.listener()
    async def on_message(self, msg: discord.Message):
        if msg.author.bot:
            return
        ctx: MyContext = await self.bot.get_context(msg)
        if ctx.valid:
            return
        self.learn_markov(msg)
        ctx.command = self.markov
        try:
            if await self.markov.can_run(ctx):
                await self.markov(ctx, recipient=None)
        except Exception as e:
            if not isinstance(e, commands.CommandError):
                e = commands.CommandInvokeError(e)
                e.__cause__ = e.original
            await self.cog_command_error(ctx, e)

    @BaseCog.listener()
    async def on_message_edit(self, old: discord.Message, new: discord.Message):
        # Remove old message
        self.forget_markov(old)
        self.learn_markov(new)

    @BaseCog.listener()
    async def on_message_delete(self, msg: discord.Message):
        self.forget_markov(msg)


def setup(bot: PikalaxBOT):
    bot.add_cog(Markov(bot))
