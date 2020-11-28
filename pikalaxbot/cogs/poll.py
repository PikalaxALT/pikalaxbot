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
import aiohttp
import sys
import io
from discord.ext import commands, tasks
from . import BaseCog
import datetime
import traceback
import typing
import base64
import math
from collections import Counter

from .utils.errors import *
from pikalaxbot.utils.hastebin import mystbin
from .utils.converters import FutureTime


class BadPollTimeArgument(commands.BadArgument):
    pass


class PollTime(FutureTime, float):
    @classmethod
    async def convert(cls, ctx, argument):
        try:
            value = await FutureTime.convert(ctx, argument)
        except commands.ConversionError:
            value = float(argument)
        else:
            value = (value.dt - ctx.message.created_at).total_seconds()
        if value <= 0 or not math.isfinite(value):
            raise BadPollTimeArgument
        return value


class PollManager:
    __slots__ = (
        'bot',
        'channel_id',
        'context_id',
        'message',
        'owner_id',
        'options',
        'votes',
        'hash',
        'start_time',
        'stop_time',
        'emojis',
        'task',
        'unloading'
    )

    def __init__(self, *, bot, channel_id, context_id, owner_id, start_time, stop_time, my_hash=None, votes=None, options=None):
        self.bot = bot
        self.channel_id = channel_id
        self.context_id = context_id
        self.owner_id = owner_id
        self.start_time = start_time
        self.stop_time = stop_time
        self.hash = my_hash or base64.b32encode((hash(self) & 0xFFFFFFFF).to_bytes(4, 'little')).decode().rstrip('=')
        self.votes = votes or {}
        self.options = options or []
        self.emojis = [f'{i + 1}\u20e3' if i < 9 else '\U0001f51f' for i in range(len(options))]
        self.task = None
        self.unloading = False
        self.message = None

    def __iter__(self):
        yield self.hash
        yield self.channel_id
        yield self.owner_id
        yield self.context_id
        yield self.message_id
        yield self.start_time
        yield self.stop_time

    @classmethod
    async def from_command(cls, context, timeout, prompt, *options):
        this = cls(
            bot=context.bot,
            channel_id=context.channel.id,
            context_id=context.message.id,
            owner_id=context.author.id,
            start_time=context.message.created_at,
            stop_time=context.message.created_at + datetime.timedelta(seconds=timeout),
            options=options
        )
        end_time = this.stop_time.strftime('%d %b %Y at %H:%M:%S UTC')
        content = f'Vote using emoji reactions. ' \
                  f'Max one vote per user. ' \
                  f'To change your vote, clear your original selection first. ' \
                  f'The poll author may not cast a vote. ' \
                  f'The poll author may cancel the poll using ' \
                  f'`{context.prefix}{context.cog.cancel.qualified_name} {this.hash}` ' \
                  f'or by deleting this message.'
        description = '\n'.join(f'{emoji}: {option}' for emoji, option in zip(this.emojis, options))
        embed = discord.Embed(title=prompt, description=description, colour=0xf47fff)
        embed.set_footer(text='Poll ends at')
        embed.timestamp = end_time
        embed.set_author(name=context.author.display_name, icon_url=context.author.avatar_url)
        this.message = await context.send(content, embed=embed)
        for emoji in this.emojis:
            await this.message.add_reaction(emoji)
        return this

    @classmethod
    async def from_sql(cls, bot, sql, my_hash, channel_id, owner_id, context_id, message_id, start_time, stop_time):
        message = await bot.get_channel(channel_id).fetch_message(message_id)
        this = cls(
            bot=bot,
            channel_id=channel_id,
            context_id=context_id,
            owner_id=owner_id,
            start_time=start_time,
            stop_time=stop_time,
            my_hash=my_hash,
            votes=dict(await sql.fetch('select voter, option from poll_options where code = $1', my_hash)),
            options=[option.split(' ', 1)[1] for option in message.embeds[0].description.splitlines()]
        )
        this.message = message
        return this

    @property
    def message_id(self):
        if self.message:
            return self.message.id

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
        return hash((self.start_time.timestamp(), self.stop_time.timestamp(), self.channel_id, self.owner_id))

    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.message_id != self.message_id:
            return
        if payload.emoji.name not in self.emojis:
            return
        if payload.user_id in {self.owner_id, self.bot.user.id}:
            return
        if payload.user_id in self.votes:
            return
        selection = self.emojis.index(payload.emoji.name)
        self.votes[payload.user_id] = selection
        async with self.bot.sql as sql:
            await sql.execute('insert into poll_options (code, voter, option) values ($1, $2, $3)', self.hash, payload.user_id, selection)

    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if payload.message_id != self.message_id:
            return
        if payload.emoji.name not in self.emojis:
            return
        if payload.user_id in {self.owner_id, self.bot.user.id}:
            return
        selection = self.emojis.index(payload.emoji.name)
        if self.votes.get(payload.user_id) != selection:
            return
        self.votes.pop(payload.user_id)
        async with self.bot.sql as sql:
            await sql.execute('delete from poll_options where code = $1 and voter = $2', self.hash, payload.user_id)

    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent):
        if payload.message_id == self.message_id:
            self.message = None
            self.cancel()

    def start(self):
        self.unloading = False
        now = datetime.datetime.utcnow()
        if now > self.stop_time:
            self.bot.dispatch('poll_end', self)
            return
        self.bot.add_listener(self.on_raw_reaction_add)
        self.bot.add_listener(self.on_raw_reaction_remove)
        self.bot.add_listener(self.on_raw_message_delete)

        async def run():
            try:
                await asyncio.sleep((self.stop_time - datetime.datetime.utcnow()).total_seconds())
            finally:
                self.bot.remove_listener(self.on_raw_reaction_add)
                self.bot.remove_listener(self.on_raw_reaction_remove)
                self.bot.remove_listener(self.on_raw_message_delete)
                if not self.unloading:
                    self.bot.dispatch('poll_end', self)

        self.task = asyncio.create_task(run())

    def cancel(self, unloading=False):
        self.unloading = unloading
        self.task.cancel()

    @classmethod
    async def convert(cls, ctx, argument):
        mgr = discord.utils.get(ctx.cog.polls, hash=argument)
        if mgr is None:
            raise NoPollFound('The supplied code does not correspond to a running poll')
        return mgr


class Poll(BaseCog):
    """Commands for starting and managing opinion polls"""

    TIMEOUT = 60

    def __init__(self, bot):
        super().__init__(bot)
        self.polls: typing.List[PollManager] = []

    def cog_unload(self):
        self.cleanup_polls.cancel()
        for mgr in self.polls:
            mgr.cancel(True)

    async def init_db(self, sql):
        await sql.execute('create table if not exists polls (code text unique primary key, channel bigint, owner bigint, context bigint, message bigint, started timestamp, closes timestamp)')
        await sql.execute('create table if not exists poll_options (code text references polls(code), voter bigint, option integer)')
        self.cleanup_polls.start()

    @tasks.loop(seconds=60)
    async def cleanup_polls(self):
        self.polls = [poll for poll in self.polls if not poll.task or not poll.task.done()]

    @cleanup_polls.error
    async def cleanup_polls_error(self, error):
        s = ''.join(traceback.format_exception(error.__class__, error, error.__traceback__))
        content = f'Ignoring exception in Poll.cleanup_polls\n{s}'
        await self.bot.send_tb(content)

    @cleanup_polls.before_loop
    async def cache_polls(self):
        await self.bot.wait_until_ready()
        try:
            async with self.bot.sql as sql:
                for row in await sql.fetch('select * from polls'):
                    try:
                        mgr = await PollManager.from_sql(self.bot, sql, *row)
                        self.polls.append(mgr)
                        mgr.start()
                    except discord.HTTPException:
                        pass
        except Exception:
            s = traceback.format_exc()
            tb = f'Ignoring exception in Poll.cache_polls\n{s}'
            print(tb, file=sys.stderr)
            channel = self.bot.exc_channel
            if channel is None:
                return
            if len(tb) < 1990:
                await channel.send(f'```{tb}```')
            else:
                try:
                    url = await mystbin(tb, cs=self.bot.client_session)
                except aiohttp.ClientResponseError:
                    await channel.send('An error has occurred', file=discord.File(io.StringIO(tb)))
                else:
                    await channel.send(f'An error has occurred: {url}')

    @commands.group(name='poll', invoke_without_command=True)
    async def poll_cmd(self, ctx: commands.Context, timeout: typing.Optional[PollTime], prompt, *opts):
        """Create a poll with up to 10 options.  Poll will last for 60.0 seconds (or as specified),
        with sudden death tiebreakers as needed.  Use quotes to enclose multi-word
duration, prompt, and options."""

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
        async with ctx.bot.sql as sql:
            await sql.execute(
                'insert into polls (code, channel, owner, context, message, started, closes) '
                'values ($1, $2, $3, $4, $5, $6, $7)',
                *mgr
            )
        self.polls.append(mgr)
        mgr.start()

    @commands.max_concurrency(1, commands.BucketType.channel)
    @poll_cmd.command(name='new')
    async def interactive_poll_maker(self, ctx: commands.Context, timeout: PollTime = TIMEOUT):
        """Create a poll interactively"""

        embed = discord.Embed(
            title='Interactive Poll Maker',
            description=f'Poll created by {ctx.author.mention}\n\n'
                        f'React with :x: to cancel.',
            colour=discord.Colour.orange()
        )
        my_message = await ctx.send('Hello, you\'ve entered the interactive poll maker. '
                                    'Please enter your question below.',
                                    embed=embed)
        await my_message.add_reaction('\N{CROSS MARK}')
        accepted_emojis = ['\N{CROSS MARK}']

        def msg_check(msg):
            return msg.channel == ctx.channel and msg.author == ctx.author

        def rxn_check(rxn, usr):
            return rxn.message == my_message and usr == ctx.author and str(rxn) in accepted_emojis

        i = 0
        while i < 11:
            futs = [
                    self.bot.loop.create_task(self.bot.wait_for('message', check=msg_check)),
                    self.bot.loop.create_task(self.bot.wait_for('reaction_add', check=rxn_check))
                ]
            try:
                done, pending = await asyncio.wait(futs, timeout=60.0, return_when=asyncio.FIRST_COMPLETED)
                [fut.cancel() for fut in pending]
                params = done.pop().result()
            except KeyError:
                await my_message.delete()
                return await ctx.send('Request timed out')
            except Exception as e:
                await my_message.delete()
                return await ctx.send(f'Request failed with {e.__class__.__name__}: {e}')
            if isinstance(params, discord.Message):
                response = params.content.strip()
                if not response:
                    await ctx.send('Message has no content', delete_after=10)
                    continue
                if i > 0 and discord.utils.find(lambda f: f.value == response, embed.fields):
                    await ctx.send('Duplicate options are not allowed', delete_after=10)
                    continue
                embed.add_field(
                    name=i and f'Option {i}' or 'Question',
                    value=response
                )
                i += 1
                content = f'Hello, you\'ve entered the interactive poll maker. ' \
                          f'Please enter option {i} below.'
                if i == 3:
                    accepted_emojis.append('\N{WHITE HEAVY CHECK MARK}')
                    embed.description += '\nReact with :white_check_mark: to exit'
                await my_message.delete()
                if i > 10:
                    break
                my_message = await ctx.send(content, embed=embed)
                for emo in accepted_emojis:
                    await my_message.add_reaction(emo)
            else:
                r, u = params
                await my_message.delete()
                if str(r) == '\N{CROSS MARK}':
                    return await ctx.send('Poll creation cancelled by user', delete_after=10)
                break
        timeout += (datetime.datetime.utcnow() - ctx.message.created_at).total_seconds()
        mgr = await PollManager.from_command(ctx, timeout, *[field.value for field in embed.fields])
        async with ctx.bot.sql as sql:
            await sql.execute(
                'insert into polls (code, channel, owner, context, message, started, closes) '
                'values ($1, $2, $3, $4, $5, $6, $7)',
                *mgr
            )
        self.polls.append(mgr)
        mgr.start()

    @poll_cmd.error
    @interactive_poll_maker.error
    async def poll_create_error(self, ctx, error):
        if isinstance(error, BadPollTimeArgument):
            await ctx.send('Invalid value for timeout. Try something like `300`, `60m`, `1w`, ...')

    @poll_cmd.command()
    async def cancel(self, ctx: commands.Context, mgr: PollManager):
        """Cancel a running poll using a code. You must be the one who started the poll
        in the first place."""

        if ctx.author.id not in {mgr.owner_id, ctx.bot.owner_id}:
            raise NotPollOwner('You may not cancel this poll')
        mgr.cancel()

    @poll_cmd.command()
    async def show(self, ctx: commands.Context, mgr: PollManager):
        """Gets poll info using a code."""

        if mgr.message is not None:
            await ctx.send(mgr.message.jump_url)
        else:
            channel = self.bot.get_channel(mgr.channel_id)
            if channel is None:
                mgr.cancel()
                raise NoPollFound('Channel not found')
            await ctx.send(f'https://discord.gg/channels/{channel.guild.id}/{mgr.channel_id}/{mgr.message_id}\n'
                           f'⚠ This jump URL may be invalid ⚠')
    
    @show.error
    @cancel.error
    async def poll_access_error(self, ctx: commands.Context, exc: Exception):
        exc = getattr(exc, 'original', exc)
        await ctx.send(f'`{ctx.prefix}{ctx.invoked_with}` raised a(n) {exc.__class__.__name__}: {exc}')

    @poll_cmd.command()
    async def list(self, ctx: commands.Context):
        """Lists all polls"""

        s = '\n'.join(str(poll) for poll in self.polls if not poll.task.done())
        if s:
            await ctx.send(f'Running polls: [\n{s}\n]')
        else:
            await ctx.send('No running polls')

    @BaseCog.listener()
    async def on_poll_end(self, mgr: PollManager):
        now = datetime.datetime.utcnow()
        async with self.bot.sql as sql:
            await sql.execute('delete from poll_options where code = $1', mgr.hash)
            await sql.execute('delete from polls where code = $1', mgr.hash)
        if mgr in self.polls:
            self.polls.remove(mgr)
        channel = self.bot.get_channel(mgr.channel_id)
        if channel is None:
            return
        if mgr.message is None:
            return
        tally = Counter(mgr.votes.values())
        if now < mgr.stop_time:
            content = 'The poll was cancelled.'
            content2 = content
        else:
            try:
                winner = max(tally, key=lambda k: tally[k])
                content = f'Poll closed, the winner is {mgr.emojis[winner]}'
                content2 = f'Poll `{mgr.hash}` has ended. The winner is {mgr.emojis[winner]} with {tally[winner]} vote(s).\n\nFull results: {mgr.message.jump_url}'
            except (ValueError, IndexError):
                content = f'Poll closed, there is no winner'
                content2 = f'Poll `{mgr.hash}` has ended. No votes were recorded.\n\nFull results: {mgr.message.jump_url}'
        embed: discord.Embed = mgr.message.embeds[0]
        desc = [f'{line} ({tally[i]})' for i, line in enumerate(mgr.options)]
        embed.description = '\n'.join(desc)
        await mgr.message.edit(content=content, embed=embed)
        await channel.send(content2)


def setup(bot):
    bot.add_cog(Poll(bot))
