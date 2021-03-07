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

import re
import typing
import asyncio
import operator

import discord
from discord.ext import commands

from . import *
from .utils.markov import Chain

from sqlalchemy import Column, ForeignKey, UniqueConstraint, TEXT, BIGINT, INTEGER, BOOLEAN, select, inspect
from sqlalchemy.orm import relationship, InstanceState
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession


class MarkovConfig(BaseTable):
    guild_id = Column(BIGINT, primary_key=True)
    maxlen = Column(INTEGER, default=256)
    on_mention = Column(BOOLEAN, default=True)

    channels = relationship('MarkovChannels', backref='config', cascade='all, delete-orphan', lazy='selectin')
    triggers = relationship('MarkovTriggers', backref='config', cascade='all, delete-orphan', lazy='selectin')


class MarkovChannels(BaseTable):
    id = Column(INTEGER, primary_key=True)
    guild_id = Column(BIGINT, ForeignKey(MarkovConfig.guild_id))
    channel_id = Column(BIGINT)

    __table_args__ = (UniqueConstraint(guild_id, channel_id),)


class MarkovTriggers(BaseTable):
    id = Column(INTEGER, primary_key=True)
    guild_id = Column(BIGINT, ForeignKey(MarkovConfig.guild_id))
    trigger = Column(TEXT)

    __table_args__ = (UniqueConstraint(guild_id, trigger),)


class MarkovNoInit(commands.CheckFailure):
    pass


class MarkovNoConfig(commands.CommandError):
    pass


class MarkovManager:
    def __init__(self, cog: 'Markov', guild: discord.Guild):
        self.cog = cog
        self.guild = guild
        if guild is None:
            raise MarkovNoConfig
        self._initialized = False
        self._init_fail = False
        self._config: typing.Optional[MarkovConfig] = None
        self._chain: typing.Optional[Chain] = None
        self._stored_msgs: set[str] = set()
        self._init_lock = asyncio.Lock()
        self._learned: dict[discord.TextChannel, typing.Optional[bool]] = {}

    async def learn_channel(self, channel: discord.TextChannel):
        if channel in self._learned and self._learned[channel] is not None:
            return
        self._learned[channel] = False
        await channel.history(limit=5000).map(self.learn).flatten()
        self._learned[channel] = True

    def prepare(self):
        self._chain = Chain(store_lowercase=True)
        self._stored_msgs.clear()
        for ch, confch in zip(list(self.channels), list(self._config.channels)):
            if ch.permissions_for(self.guild.me).read_message_history:
                asyncio.create_task(self.learn_channel(ch))
            else:
                self.cog.log_warning('Markov: Removing channel %s (%d) due to missing permissions', ch, ch.id)
                self._config.channels.remove(confch)
        self._initialized = True

    @classmethod
    def from_session(cls, cog: 'Markov', conf: MarkovConfig):
        guild = cog.bot.get_guild(conf.guild_id)
        self = cls(cog, guild)
        self._config = conf
        self.prepare()
        return self

    @classmethod
    async def new(cls, cog: 'Markov', guild: discord.Guild, on_mention=True, maxlen=256):
        self = cls(cog, guild)
        async with cog.sql_session as sess:  # type: AsyncSession
            self._config = MarkovConfig(guild_id=guild.id, on_mention=on_mention, maxlen=maxlen)
            sess.add(self._config)
        # Commit or rollback/raise happens here
        async with self:
            pass
        return self

    async def __aenter__(self):
        state: InstanceState = inspect(self._config)
        if state.expired_attributes:
            async with self.cog.sql_session as sess:
                await sess.refresh(self)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_val is None:
            state: InstanceState = inspect(self._config)
            if state.modified:
                async with self.cog.sql_session as sess:
                    await sess.flush([self._config])

    def __bool__(self):
        return self._config is not None

    def __repr__(self):
        return '<{0.__class__.__name__}(maxlen={0.maxlen}, on_markov={0.on_mention}, ' \
               'channels={0.channels!r}, triggers={0.triggers!r}>'\
            .format(self)

    @property
    def channels(self) -> list[discord.TextChannel]:
        return [self.guild.get_channel(c.channel_id) for c in self._config.channels]

    @property
    def triggers(self) -> set[str]:
        me = self.guild.me
        return set(t.trigger.lower() for t in self._config.triggers) | {me.name.lower(), me.display_name.lower()}

    @property
    def maxlen(self):
        return self._config.maxlen

    @maxlen.setter
    def maxlen(self, value: int):
        self._config.maxlen = value

    @property
    def on_mention(self):
        return self._config.on_mention

    @on_mention.setter
    def on_mention(self, value: bool):
        self._config.on_mention = value

    @property
    def initialized(self):
        return self._initialized and not self._init_fail and any(self._learned.values())

    def learn(self, message: discord.Message):
        self._stored_msgs.add(message.clean_content)
        self._chain.learn_str(message.clean_content)

    def forget(self, message: discord.Message):
        self._chain.unlearn_str(message.clean_content)
        self._stored_msgs.discard(message.clean_content)

    def generate(self, *, n_attempts=5):
        longest = ''
        lng_cnt = 0
        chain = self._chain
        if chain:
            for i in range(n_attempts):
                cur = chain.generate(self.maxlen)
                if len(cur) > lng_cnt:
                    msg = ' '.join(cur)
                    if i == 0 or msg not in self._stored_msgs:
                        lng_cnt = len(cur)
                        longest = msg
                        if lng_cnt == self.maxlen:
                            break
        return longest

    @property
    def trigger_pattern(self):
        def iter_trigger_patterns():
            if self.triggers:
                yield r'\b({})\b'.format('|'.join(self.triggers))
            if self.on_mention:
                yield '<@!{}>'.format(self.cog.bot.user.id)

        return '|'.join(iter_trigger_patterns())

    def add_channel(self, channel: discord.TextChannel):
        if channel not in self.channels:
            self._config.channels.append(MarkovChannels(channel_id=channel.id))
            return asyncio.create_task(self.learn_channel(channel))

    def del_channel(self, channel: discord.TextChannel):
        if channel in self.channels:
            self._config.channels.pop(self.channels.index(channel))
            self._learned.pop(channel, None)
            return True
        return False

    def add_trigger(self, trigger: str):
        if trigger not in self.triggers:
            self._config.triggers.append(MarkovTriggers(trigger=trigger))
            return True
        return False

    def del_trigger(self, trigger: str):
        tr = discord.utils.get(self._config.triggers, trigger=trigger)
        if tr is not None:
            self._config.triggers.remove(tr)
            return True
        return False

    async def purge(self):
        async with self.cog.sql_session as sess:
            sess.delete(self._config)

    @staticmethod
    def exists(ctx: MyContext):
        if ctx.guild not in ctx.cog.markovs:
            raise MarkovNoConfig
        return True

    @staticmethod
    async def markovable(ctx: MyContext):
        if not MarkovManager.exists(ctx):
            return False
        async with ctx.cog.markovs[ctx.guild] as mgr:  # type: MarkovManager
            if ctx.command != Markov.markov \
                    or not ctx.prefix and not re.search(mgr.trigger_pattern, ctx.message.content, re.I):
                return False
            if not mgr.initialized:
                raise MarkovNoInit
        return True


class Markov(BaseCog):
    """Commands and listeners for generating random word Markov chains."""

    def __init__(self, bot):
        super().__init__(bot)
        self.markovs: dict[discord.Guild, MarkovManager] = {}
        self.prefix_reminder_cooldown = commands.CooldownMapping.from_cooldown(1, 600, commands.BucketType.channel)
        self.no_init_error_cooldown = commands.CooldownMapping.from_cooldown(1, 60, commands.BucketType.channel)

    async def prepare_once(self):
        await super().prepare_once()
        await self.wait_until_ready()
        async with self.sql_session as sess:  # type: AsyncSession
            result = await sess.execute(select(MarkovConfig))
            for conf in result.scalars().all():
                try:
                    mgr = MarkovManager.from_session(self, conf)
                except MarkovNoConfig:
                    sess.delete(conf)
                    self.log_warning('Markov init: Removing guild %d because I cannot see it', conf.guild_id)
                else:
                    self.markovs[mgr.guild] = mgr

    async def get_prefix_help_embed(self, ctx: MyContext):
        first_word = ctx.message.content.split()[0]
        mentions = {f'<@{self.bot.user.id}>', f'<@!{self.bot.user.id}>'}
        if first_word in mentions \
                and not ctx.prefix \
                and not self.prefix_reminder_cooldown.update_rate_limit(ctx.message):
            prefix, *_ = await self.bot.get_prefix(ctx.message)
            return discord.Embed(description=f'Trying to get one of my commands? Type `{prefix}help`', colour=0xf47fff)

    @commands.check(MarkovManager.markovable)
    @commands.group(hidden=True, invoke_without_command=True)
    async def markov(self, ctx: MyContext, *, recipient: typing.Optional[discord.Member]):
        """Generate a random word Markov chain."""
        recipient = recipient or ctx.author
        async with self.markovs[ctx.guild] as mgr:
            chain = mgr.generate(n_attempts=10) or 'An error has occurred.'
        embed = await self.get_prefix_help_embed(ctx)
        if recipient == ctx.author:
            await ctx.reply(chain, embed=embed)
        else:
            await ctx.send(f'{recipient.mention}: {chain}', embed=embed)

    @commands.check_any(commands.is_owner(), commands.has_permissions(manage_guild=True))
    @markov.command('config')
    async def markov_init(self, ctx: MyContext, on_mention=True, maxlen=256):
        """Create or update guild Markov config"""
        try:
            async with self.markovs[ctx.guild] as mgr:
                mgr.on_mention = on_mention
                mgr.maxlen = maxlen
        except KeyError:
            self.markovs[ctx.guild] = await MarkovManager.new(self, ctx.guild, on_mention, maxlen)
        await ctx.message.add_reaction('\N{white heavy check mark}')

    @commands.check_any(commands.is_owner(), commands.has_permissions(manage_guild=True))
    @commands.check(MarkovManager.exists)
    @markov.command('purge')
    async def markov_deinit(self, ctx: MyContext):
        """Delete an existing Markov config"""
        await self.markovs.pop(ctx.guild).purge()
        await ctx.message.add_reaction('\N{white heavy check mark}')

    @commands.check_any(commands.is_owner(), commands.has_permissions(manage_guild=True))
    @commands.check(MarkovManager.exists)
    @markov.group('add', invoke_without_command=True)
    async def add_markov(self, ctx: MyContext, ch: discord.TextChannel):
        """Add a Markov channel by ID or mention"""
        if not ch.permissions_for(ctx.me).read_message_history:
            return await ctx.reply(f'Missing permissions to load {ch}')
        async with self.markovs[ctx.guild] as mgr:
            result = mgr.add_channel(ch)
        if result:
            await ctx.reply(f'Added configuration for {ch}')
        else:
            await ctx.reply(f'Channel {ch} is already being tracked for Markov chains')

    @commands.check_any(commands.is_owner(), commands.has_permissions(manage_guild=True))
    @commands.check(MarkovManager.exists)
    @add_markov.command('trigger')
    async def add_trigger(self, ctx: MyContext, *, trigger):
        """Add a trigger phrase"""
        async with self.markovs[ctx.guild] as mgr:
            result = mgr.add_trigger(trigger)
        if result:
            await ctx.reply('Added that trigger phrase')
        else:
            await ctx.reply('Trigger phrase already in use')

    @commands.check_any(commands.is_owner(), commands.has_permissions(manage_guild=True))
    @commands.check(MarkovManager.exists)
    @markov.group('del', invoke_without_command=True)
    async def del_markov(self, ctx: MyContext, ch: discord.TextChannel):
        """Remove a Markov channel by ID or mention"""
        async with self.markovs[ctx.guild] as mgr:
            result = mgr.del_channel(ch)
        if result:
            await ctx.reply(f'Channel {ch} will no longer be learned')
        else:
            await ctx.reply(f'Channel {ch} is not being learned')

    @commands.check_any(commands.is_owner(), commands.has_permissions(manage_guild=True))
    @commands.check(MarkovManager.exists)
    @del_markov.command('trigger')
    async def del_trigger(self, ctx: MyContext, *, trigger):
        """Add a trigger phrase"""
        async with self.markovs[ctx.guild] as mgr:
            result = mgr.del_trigger(trigger)
        if result:
            await ctx.reply('Removed that trigger phrase')
        else:
            await ctx.reply('Trigger phrase does not exist')

    @commands.check(MarkovManager.exists)
    @markov.command('triggers')
    async def trigger_list(self, ctx: MyContext):
        """List triggers for the current guild"""
        async with self.markovs[ctx.guild] as mgr:
            triggers = mgr.triggers
        await ctx.reply(', '.join(map(repr, triggers)))

    @commands.check(MarkovManager.exists)
    @markov.command('channels')
    async def channel_list(self, ctx: MyContext):
        """List triggers for the current guild"""
        async with self.markovs[ctx.guild] as mgr:
            channels = mgr.channels
        await ctx.reply(', '.join(map(operator.attrgetter('mention'), channels)))

    @BaseCog.listener()
    async def on_message(self, msg: discord.Message):
        if msg.author.bot:
            return
        ctx: MyContext = await self.bot.get_context(msg)
        if ctx.prefix:
            return

        if mgr := self.markovs.get(msg.guild):
            async with mgr:
                if msg.channel in mgr.channels:
                    mgr.learn(msg)

            ctx.command = self.markov
            try:
                if await self.markov.can_run(ctx):
                    await self.markov(ctx, recipient=None)
            except Exception as e:
                if not isinstance(e, commands.CommandError):
                    e = commands.CommandInvokeError(e)
                    e.__cause__ = e.original
                await self.markov_error(ctx, e)

    @BaseCog.listener()
    async def on_message_edit(self, old: discord.Message, new: discord.Message):
        if mgr := self.markovs.get(new.guild):
            async with mgr:
                if old.channel in mgr.channels:
                    mgr.forget(old)
                    mgr.learn(new)

    @BaseCog.listener()
    async def on_message_delete(self, msg: discord.Message):
        if mgr := self.markovs.get(msg.guild):
            async with mgr:
                if msg.channel in mgr.channels:
                    mgr.forget(msg)

    @BaseCog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        if guild in self.markovs:
            await self.markovs.pop(guild).purge()

    @commands.check(MarkovManager.markovable)
    @commands.command(aliases=['tr'])
    async def typeracer(self, ctx: MyContext):
        """Type out a Markov chain"""

        async with self.markovs[ctx.guild] as mgr:
            chain = mgr.generate()

        embed = discord.Embed(
            title='Typeracer! Type this out fast:',
            description='```\n{}\n```'.format(chain.replace(' ', '\xa0')),
            colour=discord.Colour.orange()
        )
        msg = await ctx.send(embed=embed)

        def check(m: discord.Message):
            return m.channel == ctx.channel and m.clean_content == chain

        try:
            winner: discord.Message = await self.bot.wait_for(
                'message',
                check=check,
                timeout=10.0 + 0.35 * len(chain)
            )
        except asyncio.TimeoutError:
            embed.colour = discord.Colour.red()
            embed.add_field(name='Too bad...', value='The game timed out while you were busy typing.')
        else:
            embed.colour = discord.Colour.green()
            embed.add_field(
                name='Winner!',
                value=f'{winner.author.mention} got it right in {(winner.created_at - msg.created_at).total_seconds()}s!'
            )
        await msg.edit(embed=embed)

    @markov.error
    @typeracer.error
    async def markov_error(self, ctx: MyContext, error: commands.CommandError):
        if isinstance(error, MarkovNoInit) and not self.no_init_error_cooldown.update_rate_limit(ctx.message):
            embed = await self.get_prefix_help_embed(ctx)
            await ctx.reply('Still compiling data for Markov, check again in a minute', embed=embed, delete_after=10)
