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

from .utils.errors import *
from .utils.converters import FutureTime

from sqlalchemy import Column, ForeignKey, INTEGER, BIGINT, TIMESTAMP, TEXT, select, UniqueConstraint
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import relationship, Session


class PollNotStarted(commands.CommandError):
    pass


class Polls(BaseTable):
    id = Column(INTEGER, primary_key=True)
    channel = Column(BIGINT, nullable=False)
    owner = Column(BIGINT, nullable=False)
    context = Column(BIGINT, nullable=False)
    message = Column(BIGINT, nullable=False)
    started = Column(TIMESTAMP, nullable=False)
    closes = Column(TIMESTAMP, nullable=False)
    prompt = Column(TEXT, nullable=False)

    options = relationship(
        'PollOptions',
        order_by='PollOptions.index',
        cascade='all, delete-orphan',
        backref='poll',
        lazy='immediate'
    )
    votes = relationship(
        'PollVotes',
        cascade='all, delete-orphan',
        backref='poll',
        lazy='immediate'
    )

    EMOJIS = [
        '1\N{COMBINING ENCLOSING KEYCAP}',
        '2\N{COMBINING ENCLOSING KEYCAP}',
        '3\N{COMBINING ENCLOSING KEYCAP}',
        '4\N{COMBINING ENCLOSING KEYCAP}',
        '5\N{COMBINING ENCLOSING KEYCAP}',
        '6\N{COMBINING ENCLOSING KEYCAP}',
        '7\N{COMBINING ENCLOSING KEYCAP}',
        '8\N{COMBINING ENCLOSING KEYCAP}',
        '9\N{COMBINING ENCLOSING KEYCAP}',
        '\N{KEYCAP TEN}',
    ]

    def start(self, bot: PikalaxBOT):
        self._bot = bot
        task = asyncio.create_task(discord.utils.sleep_until(self.closes))

        def raw_reaction_check(payload: discord.RawReactionActionEvent):
            if payload.message_id != self.message:
                return False
            if str(payload.emoji) not in self.EMOJIS[:len(self.options)]:
                return False
            if payload.user_id in {self.owner, bot.user.id}:
                return False
            return True

        @bot.listen()
        async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
            async with bot.sql_session as sess:
                await sess.refresh(self)
                if not raw_reaction_check(payload):
                    return
                if discord.utils.get(self.votes, voter=payload.user_id) is not None:
                    return
                selection = self.EMOJIS.index(str(payload.emoji))
                self.options[selection].votes.append(PollVotes(voter=payload.user_id))

        @bot.listen()
        async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent):
            async with bot.sql_session as sess:
                await sess.refresh(self)
                if not raw_reaction_check(payload):
                    return
                selection = self.EMOJIS.index(str(payload.emoji))
                option = self.options[selection]
                if (vote := discord.utils.get(option.votes, voter=payload.user_id)) is None:
                    return
                sess.delete(vote)

        @bot.listen()
        async def on_raw_message_delete(payload: discord.RawMessageDeleteEvent):
            if payload.message_id == self.message:
                task.cancel()

        def on_task_done(t: asyncio.Task):
            bot.remove_listener(on_raw_reaction_add)
            bot.remove_listener(on_raw_reaction_remove)
            bot.remove_listener(on_raw_message_delete)
            try:
                t.result()
            except asyncio.CancelledError:
                if t._cancel_message == 'unloading':
                    return
            bot.dispatch('poll_end', self)

        task.add_done_callback(on_task_done)
        self._task = task

    def cancel(self, unloading=False):
        try:
            return self._task.cancel('unloading' if unloading else None)
        except AttributeError:
            raise PollNotStarted(f'Poll {self} has not started') from None

    @discord.utils.cached_slot_property('_hash')
    def hash(self):
        return base64.b32encode((hash(self) & 0xFFFFFFFF).to_bytes(4, 'little')).decode().rstrip('=')

    def __hash__(self):
        return hash((self.started.timestamp(), self.closes.timestamp(), self.channel, self.owner))

    def __str__(self):
        return '<{0.__class__.__name__} hash={0.hash}, channel={1}>'.format(self, self._bot.get_channel(self.channel))

    @classmethod
    async def from_command(
            cls,
            ctx: MyContext,
            duration: float,
            prompt: str,
            *options: str
    ):
        started = datetime.datetime.utcnow()
        closes = started + datetime.timedelta(seconds=duration)
        hash_ = base64.b32encode((hash((
            started.timestamp(),
            closes.timestamp(),
            ctx.channel.id,
            ctx.author.id
        )) & 0xFFFFFFFF).to_bytes(4, 'little')).decode().rstrip('=')
        prefix, *_ = await ctx.bot.get_prefix(ctx.message)
        content = f'Vote using emoji reactions. ' \
                  f'Max one vote per user. ' \
                  f'To change your vote, clear your original selection first. ' \
                  f'The poll author may not cast a vote. ' \
                  f'The poll author may cancel the poll using ' \
                  f'`{prefix}{ctx.cog.cancel.qualified_name} {hash_}` ' \
                  f'or by deleting this message.'
        embed = discord.Embed(
            title=prompt,
            description='\n'.join(map('{0}: {1}'.format, cls.EMOJIS, options)),
            colour=0xF47FFF,
            timestamp=closes
        ).set_footer(
            text='Poll ends at'
        ).set_author(
            name=ctx.author.display_name,
            icon_url=ctx.author.avatar_url
        )
        message = await ctx.send(content, embed=embed)
        for emoji, option in zip(cls.EMOJIS, options):
            await message.add_reaction(emoji)
        self = Polls(
            channel=ctx.channel.id,
            owner=ctx.author.id,
            context=ctx.message.id,
            message=message.id,
            started=started,
            closes=closes,
            prompt=prompt,
            options=[
                PollOptions(
                    index=i,
                    txt=option
                ) for i, option in enumerate(options, 1)
            ]
        )
        async with ctx.bot.sql_session as sess:  # type: AsyncSession
            sess.add(self)
            await sess.flush()
            self.start(ctx.bot)
        return self

    @classmethod
    async def convert(cls, ctx: MyContext, argument: str):
        self: typing.Optional[cls] = discord.utils.get(ctx.cog.polls, hash=argument)
        if self is None:
            raise NoPollFound('The supplied code does not correspond to a running poll')
        return self


class PollOptions(BaseTable):
    id = Column(INTEGER, primary_key=True)
    poll_id = Column(INTEGER, ForeignKey(Polls.id, ondelete='CASCADE'))
    index = Column(INTEGER, nullable=False)
    txt = Column(TEXT, nullable=False)

    votes = relationship('PollVotes', cascade='all, delete-orphan', backref='option', lazy='immediate')


class PollVotes(BaseTable):
    id = Column(INTEGER, primary_key=True)
    poll_id = Column(INTEGER, ForeignKey(Polls.id, ondelete='CASCADE'))
    option_id = Column(INTEGER, ForeignKey(PollOptions.id, ondelete='CASCADE'))
    voter = Column(BIGINT, nullable=False)

    __table_args__ = (UniqueConstraint(poll_id, voter),)


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


class Poll(BaseCog):
    """Commands for starting and managing opinion polls"""

    TIMEOUT = 60

    def __init__(self, bot):
        super().__init__(bot)
        self.polls: list[Polls] = []

    def cog_unload(self):
        self.cleanup_polls.cancel()
        for poll in self.polls:
            poll.cancel(True)

    async def init_db(self, sql):
        await Polls.create(sql)
        await PollOptions.create(sql)
        await PollVotes.create(sql)

        self.cleanup_polls.start()

    @tasks.loop(seconds=60)
    async def cleanup_polls(self):
        self.polls = [poll for poll in self.polls if not hasattr(poll, '_task') or not poll._task.done()]

    @cleanup_polls.error
    async def cleanup_polls_error(self, error: BaseException):
        await self.bot.get_cog('ErrorHandling').send_tb(None, error, origin='Poll.cleanup_polls')

    @cleanup_polls.before_loop
    async def cache_polls(self):
        await self.bot.wait_until_ready()
        try:
            async with self.bot.sql_session as sess:
                def fetch_polls(sync_sess: Session):
                    return sync_sess.execute(select(Polls)).scalars().all()
                
                self.polls = await sess.run_sync(fetch_polls)
                for poll in self.polls:
                    poll.start(self.bot)
        except Exception as e:
            await self.bot.get_cog('ErrorHandling').send_tb(None, e, origin='Poll.cache_polls')

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
        poll = await Polls.from_command(ctx, timeout, prompt, *options)
        self.polls.append(poll)

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
        poll = await Polls.from_command(ctx, timeout, *options)
        self.polls.append(poll)

    @poll_cmd.error
    @interactive_poll_maker.error
    async def poll_create_error(self, ctx: MyContext, error: commands.CommandError):
        if isinstance(error, BadPollTimeArgument):
            await ctx.send('Invalid txt for timeout. Try something like `300`, `60m`, `1w`, ...')
        elif isinstance(error, (NotEnoughOptions, TooManyOptions)):
            await ctx.send(str(error))
        else:
            await self.bot.get_cog('ErrorHandling').send_tb(ctx, error, origin=ctx.command.qualified_name)

    @poll_cmd.command()
    async def cancel(self, ctx: MyContext, poll: Polls):
        """Cancel a running poll using a code. You must be the one who started the poll
        in the first place."""

        if ctx.author.id not in {poll.owner, ctx.bot.owner_id}:
            raise NotPollOwner('You may not cancel this poll')
        poll.cancel()

    @poll_cmd.command()
    async def show(self, ctx: MyContext, poll: Polls):
        """Gets poll info using a code."""

        message: discord.PartialMessage = self.bot.get_channel(poll.channel).get_partial_message(poll.message)
        await ctx.send(message.jump_url)
    
    @show.error
    @cancel.error
    async def poll_access_error(self, ctx: MyContext, exc: Exception):
        exc = getattr(exc, 'original', exc)
        await ctx.send(f'`{ctx.prefix}{ctx.invoked_with}` raised a(n) {exc.__class__.__name__}: {exc}')

    @poll_cmd.command()
    async def list(self, ctx: MyContext):
        """Lists all polls"""

        async with self.bot.sql_session as sess:  # type: AsyncSession
            [await sess.refresh(poll) for poll in self.polls]
            s = textwrap.indent('\n'.join(str(poll) for poll in self.polls if hasattr(poll, '_task') and not poll._task.done()), '  ')
        if s:
            await ctx.send(f'Running polls: [\n{s}\n]')
        else:
            await ctx.send('No running polls')

    @BaseCog.listener()
    async def on_poll_end(self, poll: Polls):
        async with self.bot.sql_session as sess:  # type: AsyncSession
            await sess.refresh(poll)
            now = datetime.datetime.utcnow()
            if poll in self.polls:
                self.polls.remove(poll)
            if (channel := self.bot.get_channel(poll.channel)) is None:
                return
            tally = [len(option.votes) for option in poll.options]
            message = channel.get_partial_message(poll.message)
            if now < poll.closes:
                content2 = content = 'The poll was cancelled.'
            else:
                if poll.votes:
                    winner, count = max(enumerate(tally), key=operator.itemgetter(1))
                    content = f'Poll closed, the winner is {poll.EMOJIS[winner]}'
                    content2 = f'Poll `{poll.hash}` has ended. ' \
                               f'The winner is {poll.EMOJIS[winner]} ' \
                               f'with {tally[winner]} vote(s).\n\n' \
                               f'Full results: {message.jump_url}'
                else:
                    content = f'Poll closed, there is no winner'
                    content2 = f'Poll `{poll.hash}` has ended. ' \
                               f'No votes were recorded.\n\n' \
                               f'Full results: {message.jump_url}'
            owner: discord.Member = channel.guild.get_member(poll.owner)
            embed = discord.Embed(
                title=poll.prompt,
                description='\n'.join(map('{.txt} ({})'.format, poll.options, tally)),
                colour=0xf47fff,
                timestamp=poll.closes
            ).set_footer(
                text='Poll ended at'
            ).set_author(
                name=owner.display_name,
                icon_url=owner.avatar_url
            )
            try:
                await message.edit(content=content, embed=embed)
                await channel.send(content2)
            except RuntimeError:
                return
            except discord.HTTPException:
                pass
            sess.delete(poll)

    @commands.is_owner()
    @poll_cmd.command('debug')
    async def poll_debug(self, ctx: MyContext, poll: Polls):
        """Create a dummy reaction on a running poll"""

        guild = self.bot.get_channel(poll.channel).guild
        user_id = random.choice([
            member.id for member in guild.members
            if not member.bot
        ])
        vote = discord.utils.get(poll.votes, voter=user_id)
        if user_id in poll.votes:
            event = 'REACTION REMOVE'
            emoji = poll.EMOJIS[vote.option.index - 1]
        else:
            event = 'REACTION ADD'
            emoji = random.choice(poll.EMOJIS[:len(poll.options)])
        payload = discord.RawReactionActionEvent(
            {
                'guild_id': guild.id,
                'channel_id': poll.channel,
                'message_id': poll.message,
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
