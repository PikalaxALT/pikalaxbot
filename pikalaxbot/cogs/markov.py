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

from sqlalchemy import Column, ForeignKey, UniqueConstraint, TEXT, BIGINT, INTEGER, BOOLEAN
from sqlalchemy.orm import relationship
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession, AsyncSessionTransaction


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
    def __init__(self, bot: PikalaxBOT, guild: discord.Guild):
        self.bot = bot
        self.guild = guild
        self._initialized = False
        self._init_fail = False
        self._config: typing.Optional[MarkovConfig] = None
        self._chain: typing.Optional[Chain] = None
        self._stored_msgs: set[str] = set()
        self._txn: typing.Optional[AsyncSessionTransaction] = None
        self._init_lock = asyncio.Lock()
        self._learned: dict[discord.TextChannel, typing.Optional[bool]] = {}

    @classmethod
    async def new(cls, bot: PikalaxBOT, guild: discord.Guild, on_mention=True, maxlen=256):
        self = cls(bot, guild)
        async with bot.sql_session as sess:  # type: AsyncSession
            self._config = MarkovConfig(guild_id=guild.id, on_mention=on_mention, maxlen=maxlen)
            sess.add(self._config)
            await sess.flush([self._config])
            await sess.refresh(self._config)
        return self

    async def learn_channel(self, channel: discord.TextChannel):
        if channel in self._learned and self._learned[channel] is not None:
            return
        self._learned[channel] = False
        await channel.history(limit=5000).map(self.learn).flatten()
        self._learned[channel] = True

    async def __ainit_internal(self):
        async with self.bot.sql_session as sess:
            self._config = await sess.get(MarkovConfig, self.guild.id)
        if self._config is not None:
            self._chain = Chain(store_lowercase=True)
            self._stored_msgs.clear()
            for ch, confch in zip(list(self.channels), list(self._config.channels)):
                if ch.permissions_for(self.guild.me).read_message_history:
                    asyncio.create_task(self.learn_channel(ch))
                else:
                    self._config.channels.remove(confch)
        else:
            self._init_fail = True
            raise MarkovNoConfig

    async def __ainit__(self):
        if not self._initialized:
            async with self._init_lock:
                if not self._initialized:
                    await self.__ainit_internal()
                    self._initialized = True
                elif self._init_fail:
                    raise MarkovNoConfig
        elif self._init_fail:
            raise MarkovNoConfig
        else:
            async with self.bot.sql_session as sess:
                await sess.refresh(self._config)
        return self

    def __bool__(self):
        return self._config is not None

    def __await__(self):
        return self.__ainit__().__await__()

    def __repr__(self):
        return '<{0.__class__.__name__}(maxlen={0.maxlen}, on_markov={0.on_mention}, ' \
               'channels={0.channels!r}, triggers={0.triggers!r}>'\
            .format(self)

    async def __aenter__(self):
        return await self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

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
        if message.channel in self.channels:
            self._stored_msgs.add(message.clean_content)
            self._chain.learn_str(message.clean_content)

    def forget(self, message: discord.Message):
        if message.channel in self.channels:
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

    @discord.utils.cached_property
    def trigger_pattern(self):
        def iter_trigger_patterns():
            if self.triggers:
                yield r'\b({})\b'.format('|'.join(self.triggers))
            if self.on_mention:
                yield '<@!{}>'.format(self.bot.user.id)

        return '|'.join(iter_trigger_patterns())

    async def add_channel(self, channel: discord.TextChannel):
        if channel not in self.channels:
            async with self.bot.sql_session:
                self._config.channels.append(MarkovChannels(channel_id=channel.id))
            return asyncio.create_task(self.learn_channel(channel))

    async def del_channel(self, channel: discord.TextChannel):
        if channel in self.channels:
            async with self.bot.sql_session:
                self._config.channels.pop(self.channels.index(channel))
                self._learned.pop(channel, None)
            return True
        return False

    async def add_trigger(self, trigger: str):
        if trigger not in self.triggers:
            async with self.bot.sql_session:
                self._config.triggers.append(MarkovTriggers(trigger=trigger))
            return True
        return False

    async def del_trigger(self, trigger: str):
        tr = discord.utils.get(self._config.triggers, trigger=trigger)
        if tr is not None:
            async with self.bot.sql_session:
                self._config.triggers.remove(tr)
            return True
        return False

    @staticmethod
    def exists(ctx: MyContext):
        if ctx.guild not in ctx.cog.markovs:
            raise MarkovNoConfig
        return True

    @staticmethod
    async def markovable(ctx: MyContext):
        if not MarkovManager.exists(ctx):
            return False
        mgr: MarkovManager = await ctx.cog.markovs[ctx.guild]
        if not ctx.prefix and not re.search(mgr.trigger_pattern, ctx.message.content, re.I):
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

    async def init_db(self, sql: AsyncConnection):
        await MarkovConfig.create(sql)
        await MarkovChannels.create(sql)
        await MarkovTriggers.create(sql)

    async def prepare_once(self):
        await super().prepare_once()
        await self.bot.wait_until_ready()
        eh_cog = self.bot.get_cog('ErrorHandling')
        for guild in self.bot.guilds:
            try:
                self.markovs[guild] = await MarkovManager(self.bot, guild)
            except MarkovNoConfig:
                pass
            except Exception as e:
                if not isinstance(e, commands.CommandError):
                    e = commands.CommandInvokeError(e)
                    e.__cause__ = e.original
                await eh_cog.send_tb(None, e)

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
        mgr = await self.markovs[ctx.guild]
        chain = mgr.generate(n_attempts=10) or 'An error has occurred.'
        embed = await self.get_prefix_help_embed(ctx)
        if recipient == ctx.author:
            await ctx.reply(chain, embed=embed)
        else:
            await ctx.send(f'{recipient.mention}: {chain}', embed=embed)

    @markov.error
    async def markov_error(self, ctx: MyContext, error: commands.CommandError):
        if isinstance(error, MarkovNoInit) and not self.no_init_error_cooldown.update_rate_limit(ctx.message):
            embed = await self.get_prefix_help_embed(ctx)
            await ctx.reply('Still compiling data for Markov, check again in a minute', embed=embed, delete_after=10)

    @commands.check_any(commands.is_owner(), commands.has_permissions(manage_guild=True))
    @markov.command('config')
    async def markov_init(self, ctx: MyContext, on_mention=True, maxlen=256):
        """Create or update guild Markov config"""
        try:
            async with self.markovs[ctx.guild] as mgr:
                mgr.on_mention = on_mention
                mgr.maxlen = maxlen
        except KeyError:
            self.markovs[ctx.guild] = await MarkovManager.new(self.bot, ctx.guild, on_mention, maxlen)
        await ctx.message.add_reaction('\N{white heavy check mark}')

    @commands.check_any(commands.is_owner(), commands.has_permissions(manage_guild=True))
    @commands.check(MarkovManager.exists)
    @markov.command('purge')
    async def markov_deinit(self, ctx: MyContext):
        """Delete an existing Markov config"""
        async with self.bot.sql_session as sess:
            mgr = self.markovs.pop(ctx.guild)
            sess.delete(mgr._config)
        await ctx.message.add_reaction('\N{white heavy check mark}')

    @commands.check_any(commands.is_owner(), commands.has_permissions(manage_guild=True))
    @commands.check(MarkovManager.exists)
    @markov.group('add', invoke_without_command=True)
    async def add_markov(self, ctx: MyContext, ch: discord.TextChannel):
        """Add a Markov channel by ID or mention"""
        if not ch.permissions_for(ctx.me).read_message_history:
            return await ctx.reply(f'Missing permissions to load {ch}')
        async with self.markovs[ctx.guild] as mgr:  # type: MarkovManager
            result = await mgr.add_channel(ch)
        if result:
            await ctx.reply(f'Added configuration for {ch}')
        else:
            await ctx.reply(f'Channel {ch} is already being tracked for Markov chains')

    @commands.check_any(commands.is_owner(), commands.has_permissions(manage_guild=True))
    @commands.check(MarkovManager.exists)
    @add_markov.command('trigger')
    async def add_trigger(self, ctx: MyContext, *, trigger):
        """Add a trigger phrase"""
        async with self.markovs[ctx.guild] as mgr:  # type: MarkovManager
            result = await mgr.add_trigger(trigger)
        if result:
            await ctx.reply('Added that trigger phrase')
        else:
            await ctx.reply('Trigger phrase already in use')

    @commands.check_any(commands.is_owner(), commands.has_permissions(manage_guild=True))
    @commands.check(MarkovManager.exists)
    @markov.group('del', invoke_without_command=True)
    async def del_markov(self, ctx: MyContext, ch: discord.TextChannel):
        """Remove a Markov channel by ID or mention"""
        async with self.markovs[ctx.guild] as mgr:  # type: MarkovManager
            result = await mgr.del_channel(ch)
        if result:
            await ctx.reply(f'Channel {ch} will no longer be learned')
        else:
            await ctx.reply(f'Channel {ch} is not being learned')

    @commands.check_any(commands.is_owner(), commands.has_permissions(manage_guild=True))
    @commands.check(MarkovManager.exists)
    @del_markov.command('trigger')
    async def del_trigger(self, ctx: MyContext, *, trigger):
        """Add a trigger phrase"""
        async with self.markovs[ctx.guild] as mgr:  # type: MarkovManager
            result = await mgr.del_trigger(trigger)
        if result:
            await ctx.reply('Removed that trigger phrase')
        else:
            await ctx.reply('Trigger phrase does not exist')

    @commands.check(MarkovManager.exists)
    @markov.command('triggers')
    async def trigger_list(self, ctx: MyContext):
        """List triggers for the current guild"""
        async with self.markovs[ctx.guild] as mgr:  # type: MarkovManager
            triggers = mgr.triggers
        await ctx.reply(', '.join(map(repr, triggers)))

    @commands.check(MarkovManager.exists)
    @markov.command('channels')
    async def channel_list(self, ctx: MyContext):
        """List triggers for the current guild"""
        async with self.markovs[ctx.guild] as mgr:  # type: MarkovManager
            channels = mgr.channels
        await ctx.reply(', '.join(map(operator.attrgetter('mention'), channels)))

    @BaseCog.listener()
    async def on_message(self, msg: discord.Message):
        if msg.author.bot:
            return
        ctx: MyContext = await self.bot.get_context(msg)
        if ctx.valid:
            return

        if mgr := self.markovs.get(msg.guild):
            await mgr
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
            await mgr
            mgr.forget(old)
            mgr.learn(new)

    @BaseCog.listener()
    async def on_message_delete(self, msg: discord.Message):
        if mgr := self.markovs.get(msg.guild):
            await mgr
            mgr.forget(msg)


def setup(bot: PikalaxBOT):
    bot.add_cog(Markov(bot))


def teardown(bot: PikalaxBOT):
    MarkovTriggers.unlink()
    MarkovChannels.unlink()
    MarkovConfig.unlink()
