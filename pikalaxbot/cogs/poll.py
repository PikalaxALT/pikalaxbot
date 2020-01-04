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
import binascii
from discord.ext import commands
from . import BaseCog
import datetime
import typing
import traceback
import typing
import base64
from collections import Counter

from .utils.errors import *


class PollManager:
    __slots__ = (
        'bot',
        'channel_id',
        'context_id',
        'message_id',
        'message',
        'owner_id',
        'options',
        'votes',
        'hash',
        'start_time',
        'stop_time',
        'emojis',
        'task',
        'done_callback'
    )

    @classmethod
    async def from_command(cls, context, timeout, prompt, *options):
        this = cls()
        this.bot = context.bot
        this.channel_id = context.channel.id
        this.context_id = context.message.id
        this.owner_id = context.author.id
        this.options = options
        this.start_time = datetime.datetime.utcnow()
        this.hash = base64.b32encode((hash(this) & 0xFFFFFFFF).to_bytes(4, 'little')).decode().rstrip('=')
        this.votes = {}
        this.emojis = [f'{i + 1}\u20e3' if i < 9 else '\U0001f51f' for i in range(len(options))]
        content = f'Vote using emoji reactions. ' \
                  f'You have {timeout:d} seconds from when the last option appears. ' \
                  f'Max one vote per user. ' \
                  f'To change your vote, clear your original selection first. ' \
                  f'The poll author may not cast a vote. ' \
                  f'The poll author may cancel the poll using `{context.prefix}{context.cog.cancel.qualified_name} {this.hash}`'
        description = '\n'.join(f'{emoji}: {option}' for emoji, option in zip(this.emojis, options))
        embed = discord.Embed(title=prompt, description=description)
        embed.set_author(name=context.author.display_name, icon_url=context.author.avatar_url)
        this.message = await context.send(content, embed=embed)
        for emoji in this.emojis:
            await this.message.add_reaction(emoji)
        this.message_id = this.message.id
        this.stop_time = datetime.datetime.utcnow() + datetime.timedelta(seconds=timeout)
        this.start()
        async with this.bot.sql as sql:
            await sql.execute('insert into polls (code, channel, owner, context, message, started, closes) values (?, ?, ?, ?, ?, ?, ?)', (this.hash, this.channel_id, this.owner_id, this.context_id, this.message_id, this.start_time.timestamp(), this.stop_time.timestamp()))
        return this

    @classmethod
    async def from_sql(cls, bot, sql, my_hash, channel_id, owner_id, context_id, message_id, start_time, stop_time):
        this = cls()
        this.bot = bot
        this.channel_id = channel_id
        this.context_id = context_id
        this.message_id = message_id
        try:
            this.message = await bot.get_channel(channel_id).fetch_message(message_id)
            this.options = [option.split(' ', 1)[1] for option in this.message.embeds[0].description.splitlines()]
        except discord.HTTPException:
            this.message = None
            this.options = []
        this.owner_id = owner_id
        this.votes = dict(await sql.execute('select (voter, option) from poll_options where code = ?', (my_hash,)))
        this.hash = my_hash
        this.start_time = datetime.datetime.fromtimestamp(start_time)
        this.stop_time = datetime.datetime.fromtimestamp(stop_time)
        this.start()
        return this

    def __eq__(self, other):
        if isinstance(other, PollManager):
            return hash(self) == hash(other)
        if isinstance(other, str):
            return self.hash == other
        raise NotImplementedError

    def __repr__(self):
        return f'<{self.__class__.__name__} object with code {self.hash} and {len(self.options)} options>'

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash((self.start_time.timestamp(), self.channel_id, self.owner_id))

    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.message_id != self.message_id:
            return
        if payload.emoji.name not in self.emojis:
            return
        if payload.user_id == self.owner_id:
            return
        if payload.user_id in self.votes:
            return
        selection = self.emojis.index(payload.emoji.name)
        self.votes[payload.user_id] = selection
        async with self.bot.sql as sql:
            await sql.execute('insert into poll_options (code, voter, option) values (?, ?, ?)', (self.hash, payload.user_id, selection))

    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if payload.message_id != self.message_id:
            return
        if payload.emoji.name not in self.emojis:
            return
        if payload.user_id == self.owner_id:
            return
        selection = self.emojis.index(payload.emoji.name)
        if self.votes.get(payload.user_id) != selection:
            return
        self.votes.pop(payload.user_id)
        async with self.bot.sql as sql:
            await sql.execute('delete from poll_options where code = ? and voter = ?', (self.hash, payload.user_id))

    def start(self):
        now = datetime.datetime.utcnow()
        if now > self.stop_time:
            self.bot.dispatch('poll_end', self)
            return
        self.bot.add_listener(self.on_raw_reaction_add)
        self.bot.add_listener(self.on_raw_reaction_remove)
        self.task = asyncio.create_task(asyncio.sleep((self.stop_time - now).total_seconds()))

        def done_callback():
            self.bot.remove_listener(self.on_raw_reaction_add)
            self.bot.remove_listener(self.on_raw_reaction_remove)
            self.bot.dispatch('poll_end', self)

        self.done_callback = done_callback
        self.task.add_done_callback(self.done_callback)

    def cancel(self):
        self.task.cancel()


class Poll(BaseCog):
    TIMEOUT = 60

    def __init__(self, bot):
        super().__init__(bot)
        self.polls: typing.List[PollManager] = []
        bot.loop.create_task(self.cache_polls())

    def cog_unload(self):
        for mgr in self.polls:
            mgr.task.remove_done_callback(mgr.done_callback)
            mgr.cancel()

    async def init_db(self, sql):
        await sql.execute('create table if not exists polls (code text, channel integer, owner integer, context integer, message integer, started timestamp, closes timestamp)')
        await sql.execute('create table if not exists poll_options (code text, voter integer, option integer)')

    async def cache_polls(self):
        await self.bot.wait_until_ready()
        async with self.bot.sql as sql:
            for row in await sql.execute('select * from polls'):
                mgr = await PollManager.from_sql(self.bot, sql, *row)
                self.polls.append(mgr)

    @commands.group(name='poll', invoke_without_command=True)
    async def poll_cmd(self, ctx: commands.Context, timeout: typing.Optional[int], prompt, *opts):
        """Create a poll with up to 10 options.  Poll will last for 60 seconds, with sudden death
        tiebreakers as needed.  Use quotes to enclose multi-word prompt and options.
        Optionally, pass an int before the prompt to indicate the number of seconds the poll lasts."""
        timeout = timeout or Poll.TIMEOUT
        # Do it this way because `set` does weird things with ordering
        options = []
        for opt in opts:
            if opt not in options:
                options.append(opt)
        nopts = len(options)
        if nopts > 10:
            raise TooManyOptions('Too many options!')
        if nopts < 2:
            raise NotEnoughOptions('Not enough unique options!')
        mgr = await PollManager.from_command(ctx, timeout, prompt, *options)
        self.polls.append(mgr)

    @poll_cmd.command()
    async def cancel(self, ctx: commands.Context, code):
        """Cancel a running poll using a code. You must be the one who started the poll
        in the first place."""
        mgr = discord.utils.get(self.polls, hash=code)
        if mgr is None:
            raise NoPollFound('The supplied code does not correspond to a running poll')
        if mgr.owner_id != ctx.author.id:
            raise NotPollOwner('You may not cancel this poll')
        mgr.cancel()

    @poll_cmd.command()
    async def show(self, ctx: commands.Context, code):
        """Gets poll info using a code."""
        mgr = discord.utils.get(self.polls, hash=code)
        if mgr is None:
            raise NoPollFound('The supplied code does not correspond to a running poll')
        if mgr.message is not None:
            await ctx.send(mgr.message.jump_url)
        else:
            channel = self.bot.get_channel(mgr.channel_id)
            if channel is None:
                mgr.cancel()
                raise NoPollFound('Channel not found')
            await ctx.send(f'https://discord.gg/channels/{channel.guild.id}/{mgr.channel_id}/{mgr.message_id}\n'
                           f'⚠ This jump URL may be invalid ⚠')

    async def cog_command_error(self, ctx, exc):
        handled_excs = \
            TooManyOptions, \
            NotEnoughOptions, \
            ReactionIntegrityError, \
            commands.CheckFailure, \
            asyncio.CancelledError, \
            asyncio.TimeoutError, \
            NotPollOwner, \
            NoPollFound, \
            binascii.Error
        exc = getattr(exc, 'original', exc)
        await ctx.send(f'{exc.__class__.__name__}: {exc} {self.bot.command_error_emoji}', delete_after=10)
        if not isinstance(exc, handled_excs):
            tb = ''.join(traceback.format_exception(exc.__class__, exc, exc.__traceback__, 4))
            embed = discord.Embed(color=discord.Color.red(), title='Poll exception', description=f'```\n{tb}\n```')
            embed.add_field(name='Author', value=ctx.author.mention)
            embed.add_field(name='Channel', value=ctx.channel.mention)
            embed.add_field(name='Message', value=ctx.message.jump_url)
            await self.bot.owner.send(embed=embed)

    @BaseCog.listener()
    async def on_poll_end(self, mgr: PollManager):
        now = datetime.datetime.utcnow()
        async with self.bot.sql as sql:
            await sql.execute('delete from polls where code = ?', (mgr.hash,))
            await sql.execute('delete from poll_options where code = ?', (mgr.hash,))
        if mgr in self.polls:
            self.polls.remove(mgr)
        channel = self.bot.get_channel(mgr.channel_id)
        if channel is None:
            return
        tally = Counter(mgr.votes.values())
        winner = max(tally, key=lambda k: tally[k])
        if mgr.message is None:
            return
        if now < mgr.stop_time:
            content = 'The poll was cancelled.'
            content2 = content
        else:
            content = f'Poll closed, the winner is {mgr.emojis[winner]}'
            content2 = f'Poll `{mgr.hash}` has ended. The winner is {mgr.emojis[winner]} with {tally[winner]} votes.\n\nFull results: {mgr.message.jump_url}'
        embed: discord.Embed = mgr.message.embeds[0]
        desc = [f'{line} ({tally[i]}' for i, line in enumerate(mgr.options)]
        embed.description = '\n'.join(desc)
        await mgr.message.edit(content=content, embed=embed)
        await channel.send(content2)


def setup(bot):
    bot.add_cog(Poll(bot))
