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

import asyncio
import discord
from discord.ext import commands, tasks
from . import *
import datetime
import typing
import base64
import math
import aioitertools
import operator
import textwrap
import random
from collections import Counter

from .utils.errors import *
from .utils.converters import FutureTime

from sqlalchemy import Column, ForeignKey, INTEGER, BIGINT, TIMESTAMP, TEXT, bindparam, select, delete
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import StatementError
from sqlalchemy.orm import relationship


class Polls(BaseTable):
    id = Column(INTEGER, primary_key=True)
    channel = Column(BIGINT, nullable=False)
    owner = Column(BIGINT, nullable=False)
    context = Column(BIGINT, nullable=False)
    message = Column(BIGINT, nullable=False)
    started = Column(TIMESTAMP, nullable=False)
    closes = Column(TIMESTAMP, nullable=False)
    prompt = Column(TEXT, nullable=False)

    options = relationship('PollOptions', order_by='PollOptions.index', cascade='all, delete-orphan', backref='poll')
    votes = relationship('PollVotes', cascade='all, delete-orphan', backref='poll')

    @classmethod
    async def new_poll(
            cls,
            conn: AsyncConnection,
            context: MyContext,
            message: discord.Message,
            started: datetime.datetime,
            closes: datetime.datetime,
            prompt: str,
            *options: str
    ):
        statement = insert(cls).values(
            channel=context.channel.id,
            owner=context.author.id,
            context=context.message.id,
            message=message.id,
            started=started,
            closes=closes,
            prompt=prompt
        ).returning(cls.id)
        poll_id = await conn.scalar(statement)
        option_ids = await PollOptions.add_options(conn, poll_id, *options)
        return poll_id, option_ids

    @classmethod
    async def fetchall(cls, conn: AsyncConnection, bot: PikalaxBOT):
        statement = select(cls)
        result = await conn.execute(statement)
        for row in result.all():
            try:
                option_ids, options = zip(*(await PollOptions.get_options(conn, row.id)))
                votes = {vote.voter: options[option_ids.index(vote.option_id)] for vote in await PollVotes.get_votes(conn, row.id)}
                message = bot.get_channel(row.channel).get_partial_message(row.message)
                mgr = PollManager(
                    bot=bot,
                    channel_id=row.channel,
                    context_id=row.context,
                    owner_id=row.owner,
                    start_time=row.started,
                    stop_time=row.closes,
                    id_=row.id,
                    prompt=row.prompt,
                    options=options,
                    option_ids=option_ids,
                    votes=votes
                )
                mgr.message = message
                mgr.start()
                yield mgr
            except StatementError:
                pass

    @classmethod
    async def delete(cls, conn: AsyncConnection, poll_id: int):
        statement = delete(cls).where(cls.id == poll_id)
        await conn.execute(statement)


class PollOptions(BaseTable):
    id = Column(INTEGER, primary_key=True)
    poll_id = Column(INTEGER, ForeignKey(Polls.id, ondelete='CASCADE'))
    index = Column(INTEGER, nullable=False)
    txt = Column(TEXT, nullable=False)

    votes = relationship('PollVotes', cascade='all, delete-orphan', backref='option')

    @classmethod
    async def add_options(cls, conn: AsyncConnection, poll_id: int, *options: str):
        params = [{'poll_id': poll_id, 'index': i, 'txt': opt} for i, opt in enumerate(options, 1)]
        statement = insert(cls).values(
            poll_id=bindparam('poll_id'),
            index=bindparam('index'),
            txt=bindparam('txt')
        )
        result = await conn.execute(statement, params)
        return result.scalars().all()

    @classmethod
    async def get_options(cls, conn: AsyncConnection, poll_id: int):
        statement = select([cls.index, cls.txt]).where(cls.poll_id == poll_id).order_by(cls.index)
        result = await conn.execute(statement)
        return zip(*result.all())


class PollVotes(BaseTable):
    id = Column(INTEGER, primary_key=True)
    poll_id = Column(INTEGER, ForeignKey(Polls.id, ondelete='CASCADE'))
    option_id = Column(INTEGER, ForeignKey(PollOptions.id, ondelete='CASCADE'))
    voter = Column(BIGINT, nullable=False)

    @classmethod
    async def add_vote(cls, conn: AsyncConnection, poll_id: int, option_id: int, voter: int):
        statement = insert(cls).values(
            poll_id=poll_id,
            option_id=option_id,
            voter=voter
        ).on_conflict_do_nothing()
        await conn.execute(statement)

    @classmethod
    async def remove_vote(cls, conn: AsyncConnection, poll_id: int, option_id: int, voter: int):
        statement = delete(cls).where(
            cls.poll_id == poll_id,
            cls.option_id == option_id,
            cls.voter == voter
        )
        await conn.execute(statement)

    @classmethod
    async def get_votes(cls, conn: AsyncConnection, poll_id: int):
        statement = select(cls).where(cls.poll_id == poll_id)
        result = await conn.execute(statement)
        return result.all()


class BadPollTimeArgument(commands.BadArgument):
    pass


class PollTime(FutureTime, float):
    @classmethod
    async def convert(cls, ctx, argument):
        try:
            txt = await FutureTime.convert(ctx, argument)
        except commands.ConversionError:
            txt = float(argument)
        else:
            txt = (txt.dt - ctx.message.created_at).total_seconds()
        if txt <= 0 or not math.isfinite(txt):
            raise BadPollTimeArgument
        return txt


class PollManager:
    __slots__ = (
        'bot',
        'channel_id',
        'context_id',
        'message',
        'owner_id',
        'prompt',
        'options',
        'option_ids',
        'votes',
        'id',
        '_hash',
        '_message_id',
        'start_time',
        'stop_time',
        'emojis',
        'task',
        'unloading'
    )

    def __init__(
            self,
            *,
            bot: PikalaxBOT,
            channel_id: int,
            context_id: int,
            owner_id: int,
            start_time: datetime.datetime,
            stop_time: datetime.datetime,
            id_: int = None,
            votes: dict[int, int] = None,
            prompt: str = None,
            options: typing.Sequence[str] = None,
            option_ids: typing.Sequence[int] = None,
    ):
        self.bot = bot
        self.channel_id = channel_id
        self.context_id = context_id
        self.owner_id = owner_id
        self.start_time = start_time
        self.stop_time = stop_time
        self.id = id_
        self.prompt = prompt
        self.votes: dict[int, int] = votes or {}
        self.options: list[str] = options or []
        self.option_ids: list[int] = option_ids or []
        self.emojis = [f'{i + 1}\u20e3' if i < 9 else '\U0001f51f' for i in range(len(options))]
        self.task: typing.Optional[asyncio.Task] = None
        self.unloading = False
        self.message: typing.Union[discord.Message, discord.PartialMessage, None] = None

    @discord.utils.cached_slot_property('_hash')
    def hash(self):
        return base64.b32encode((hash(self) & 0xFFFFFFFF).to_bytes(4, 'little')).decode().rstrip('=')

    def __iter__(self):
        yield self.channel_id
        yield self.owner_id
        yield self.context_id
        yield self.message_id
        yield self.start_time
        yield self.stop_time
        yield self.prompt

    @classmethod
    async def from_command(cls, context: MyContext, timeout: float, prompt: str, *options: str):
        this = cls(
            bot=context.bot,
            channel_id=context.channel.id,
            context_id=context.message.id,
            owner_id=context.author.id,
            start_time=context.message.created_at,
            stop_time=context.message.created_at + datetime.timedelta(seconds=timeout),
            prompt=prompt,
            options=options
        )
        content = f'Vote using emoji reactions. ' \
                  f'Max one vote per user. ' \
                  f'To change your vote, clear your original selection first. ' \
                  f'The poll author may not cast a vote. ' \
                  f'The poll author may cancel the poll using ' \
                  f'`{context.prefix}{context.cog.cancel.qualified_name} {this.hash}` ' \
                  f'or by deleting this message.'
        description = '\n'.join(map('{0}: {1}'.format, this.emojis, options))
        embed = discord.Embed(title=prompt, description=description, colour=0xf47fff)
        embed.set_footer(text='Poll ends at')
        embed.timestamp = this.stop_time
        embed.set_author(name=context.author.display_name, icon_url=context.author.avatar_url)
        this.message = await context.send(content, embed=embed)
        for emoji in this.emojis:
            await this.message.add_reaction(emoji)
        try:
            async with context.bot.sql as sql:
                this.id, this.option_ids = await Polls.new_poll(
                    sql,
                    context,
                    this.message,
                    this.start_time,
                    this.stop_time,
                    prompt,
                    *options
                )
        except StatementError:
            await this.message.edit(content='An error occurred, the poll was cancelled.', embed=None)
            raise
        return this

    @discord.utils.cached_slot_property('_message_id')
    def message_id(self):
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
        async with self.bot.sql as sql:
            await PollVotes.add_vote(sql, self.id, self.option_ids[selection], payload.user_id)
        self.votes[payload.user_id] = selection

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
        async with self.bot.sql as sql:
            await PollVotes.remove_vote(sql, self.id, self.option_ids[selection], payload.user_id)
        self.votes.pop(payload.user_id)

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
    async def convert(cls, ctx: MyContext, argument: str):
        mgr: typing.Optional['PollManager'] = discord.utils.get(ctx.cog.polls, hash=argument)
        if mgr is None:
            raise NoPollFound('The supplied code does not correspond to a running poll')
        return mgr


class Poll(BaseCog):
    """Commands for starting and managing opinion polls"""

    TIMEOUT = 60

    def __init__(self, bot):
        super().__init__(bot)
        self.polls: list[PollManager] = []

    def cog_unload(self):
        self.cleanup_polls.cancel()
        for mgr in self.polls:
            mgr.cancel(True)

    async def init_db(self, sql):
        await Polls.create(sql)
        await PollOptions.create(sql)
        await PollVotes.create(sql)
        self.cleanup_polls.start()

    @tasks.loop(seconds=60)
    async def cleanup_polls(self):
        self.polls = [poll for poll in self.polls if not poll.task or not poll.task.done()]

    @cleanup_polls.error
    async def cleanup_polls_error(self, error: BaseException):
        await self.bot.send_tb(None, error, origin='Poll.cleanup_polls')

    @cleanup_polls.before_loop
    async def cache_polls(self):
        await self.bot.wait_until_ready()
        try:
            async with self.bot.sql as sql:
                self.polls = [mgr async for mgr in Polls.fetchall(sql, self.bot)]
        except Exception as e:
            await self.bot.send_tb(None, e, origin='Poll.cache_polls')

    @commands.group(name='poll', invoke_without_command=True)
    async def poll_cmd(self, ctx: MyContext, timeout: typing.Optional[PollTime], prompt, *opts):
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
        self.polls.append(mgr)
        mgr.start()

    @commands.max_concurrency(1, commands.BucketType.channel)
    @poll_cmd.command(name='new')
    async def interactive_poll_maker(self, ctx: MyContext, timeout: PollTime = TIMEOUT):
        """Create a poll interactively"""

        embed = discord.Embed(
            title='Interactive Poll Maker',
            description=f'Poll created by {ctx.author.mention}\n\n'
                        f'React with :x: to cancel.',
            colour=discord.Colour.orange()
        )
        content = 'Hello, you\'ve entered the interactive poll maker. Please enter your question below.'
        accepted_emojis = {'\N{CROSS MARK}'}

        async def get_poll_votes() -> typing.Union[str, bool]:
            deleted = True
            my_message: typing.Optional[discord.Message] = None

            def msg_check(msg: discord.Message):
                return msg.channel == ctx.channel and msg.author == ctx.author

            def rxn_check(rxn: discord.Reaction, usr: discord.User):
                return rxn.message == my_message and usr == ctx.author and str(rxn) in accepted_emojis

            while True:
                if deleted:
                    my_message = await ctx.send(content, embed=embed)
                    for emo in accepted_emojis:
                        await my_message.add_reaction(emo)
                    deleted = False
                futs = {
                    asyncio.create_task(self.bot.wait_for('message', check=msg_check)),
                    asyncio.create_task(self.bot.wait_for('reaction_add', check=rxn_check))
                }
                done, pending = await asyncio.wait(futs, timeout=60.0, return_when=asyncio.FIRST_COMPLETED)
                [fut.cancel() for fut in pending]
                params: typing.Union[discord.Message, tuple[discord.Reaction, discord.User]] = done.pop().result()
                if isinstance(params, discord.Message):
                    response = params.content.strip()
                    if not response:
                        await ctx.send('Message has no content', delete_after=10)
                        continue
                    if discord.utils.get(embed.fields, txt=response):
                        await ctx.send('Duplicate options are not allowed')
                        continue
                else:
                    response = str(params[0]) == '\N{CROSS MARK}'
                await my_message.delete()
                yield response
                deleted = True

        async for i, resp in aioitertools.zip(range(11), get_poll_votes()):
            if isinstance(resp, str):
                content = f'Hello, you\'ve entered the interactive poll maker. ' \
                          f'Please enter option {i + 1} below.'
                if i == 2:
                    accepted_emojis.add('\N{WHITE HEAVY CHECK MARK}')
                    embed.description += '\nReact with :white_check_mark: to exit'
                embed.add_field(
                    name='Question' if i == 0 else f'Option {1}',
                    value=resp
                )
            elif resp:
                return await ctx.send('Poll creation cancelled by user', delete_after=10)
            else:
                break
        timeout += (datetime.datetime.utcnow() - ctx.message.created_at).total_seconds()
        options = [field.value for field in embed.fields]
        mgr = await PollManager.from_command(ctx, timeout, *options)
        self.polls.append(mgr)
        mgr.start()

    @poll_cmd.error
    @interactive_poll_maker.error
    async def poll_create_error(self, ctx: MyContext, error: commands.CommandError):
        if isinstance(error, BadPollTimeArgument):
            await ctx.send('Invalid txt for timeout. Try something like `300`, `60m`, `1w`, ...')
        elif isinstance(error, (NotEnoughOptions, TooManyOptions)):
            await ctx.send(str(error))
        else:
            await self.bot.send_tb(ctx, error, origin=ctx.command.qualified_name)

    @poll_cmd.command()
    async def cancel(self, ctx: MyContext, mgr: PollManager):
        """Cancel a running poll using a code. You must be the one who started the poll
        in the first place."""

        if ctx.author.id not in {mgr.owner_id, ctx.bot.owner_id}:
            raise NotPollOwner('You may not cancel this poll')
        mgr.cancel()

    @poll_cmd.command()
    async def show(self, ctx: MyContext, mgr: PollManager):
        """Gets poll info using a code."""

        await ctx.send(mgr.message.jump_url)
    
    @show.error
    @cancel.error
    async def poll_access_error(self, ctx: MyContext, exc: Exception):
        exc = getattr(exc, 'original', exc)
        await ctx.send(f'`{ctx.prefix}{ctx.invoked_with}` raised a(n) {exc.__class__.__name__}: {exc}')

    @poll_cmd.command()
    async def list(self, ctx: MyContext):
        """Lists all polls"""

        s = textwrap.indent('\n'.join(str(poll) for poll in self.polls if not poll.task.done()), '  ')
        if s:
            await ctx.send(f'Running polls: [\n{s}\n]')
        else:
            await ctx.send('No running polls')

    @BaseCog.listener()
    async def on_poll_end(self, mgr: PollManager):
        now = datetime.datetime.utcnow()
        if mgr in self.polls:
            self.polls.remove(mgr)
        if (channel := mgr.message.channel) is None:
            return
        tally = Counter(mgr.votes.values())
        if now < mgr.stop_time:
            content2 = content = 'The poll was cancelled.'
        else:
            try:
                winner, count = max(tally.items(), key=operator.itemgetter(1))
                content = f'Poll closed, the winner is {mgr.emojis[winner]}'
                content2 = f'Poll `{mgr.hash}` has ended. ' \
                           f'The winner is {mgr.emojis[winner]} ' \
                           f'with {tally[winner]} vote(s).\n\n' \
                           f'Full results: {mgr.message.jump_url}'
            except (ValueError, IndexError):
                content = f'Poll closed, there is no winner'
                content2 = f'Poll `{mgr.hash}` has ended. ' \
                           f'No votes were recorded.\n\n' \
                           f'Full results: {mgr.message.jump_url}'
        owner: discord.Member = channel.guild.get_member(mgr.owner_id)
        desc = [f'{line} ({tally[i]})' for i, line in enumerate(mgr.options)]
        embed = discord.Embed(title=mgr.prompt, description='\n'.join(desc), colour=0xf47fff)
        embed.set_footer(text='Poll ends at')
        embed.timestamp = mgr.stop_time
        embed.set_author(name=owner.display_name, icon_url=owner.avatar_url)
        embed.description = '\n'.join(desc)
        try:
            await mgr.message.edit(content=content, embed=embed)
            await channel.send(content2)
        except RuntimeError:
            return
        except discord.HTTPException:
            pass
        async with self.bot.sql as sql:
            await Polls.delete(sql, mgr.id)

    @commands.is_owner()
    @poll_cmd.command('debug')
    async def poll_debug(self, ctx: MyContext, poll: PollManager):
        """Create a dummy reaction on a running poll"""

        user_id = random.choice([
            member.id for member in poll.message.guild.members
            if not member.bot
        ])
        if user_id in poll.votes:
            event = 'REACTION REMOVE'
            emoji = poll.emojis[poll.votes[user_id]]
        else:
            event = 'REACTION ADD'
            emoji = random.choice(poll.emojis)
        payload = discord.RawReactionActionEvent(
            {
                'guild_id': poll.message.guild.id,
                'channel_id': poll.channel_id,
                'message_id': poll.message_id,
                'user_id': user_id
            },
            discord.PartialEmoji(name=emoji),
            event
        )
        self.bot.dispatch('raw_' + event.lower().replace(' ', '_'), payload)
        await ctx.reply(f'Dispatched a {event} event')


def setup(bot: PikalaxBOT):
    bot.add_cog(Poll(bot))


def teardown(bot: PikalaxBOT):
    PollVotes.unlink()
    PollOptions.unlink()
    Polls.unlink()
