import discord
from discord.ext import commands, menus
from . import *
from .utils.menus import *
import typing
import random
from collections import Counter

from sqlalchemy import Column, ForeignKey, UniqueConstraint, CheckConstraint, BIGINT, VARCHAR, TEXT, INTEGER, TIMESTAMP
from sqlalchemy import select
from sqlalchemy.orm import relationship, Session
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession


AnyMessage = typing.Union[discord.Message, discord.PartialMessage]


class StarboardError(commands.CommandError):
    pass


class NoStarConfig(StarboardError):
    pass


class MessageNotFound(StarboardError):
    pass


class StarConfig(BaseTable):
    id = Column(INTEGER, primary_key=True)
    guild = Column(BIGINT, unique=True)
    channel = Column(BIGINT, nullable=False)
    created_at = Column(TIMESTAMP)
    threshold = Column(INTEGER, default=2)
    emoji = Column(TEXT, default='\N{white medium star}')

    __table_args__ = (
        UniqueConstraint(guild),
        CheckConstraint(threshold >= 2)
    )

    posts = relationship(
        lambda: StarPosts,
        cascade='all, delete-orphan',
        backref='config',
        lazy='immediate',
        innerjoin=True
    )


class StarPosts(BaseTable):
    id = Column(INTEGER, primary_key=True)
    conf_id = Column(INTEGER, ForeignKey(StarConfig.id))
    channel = Column(BIGINT)
    message = Column(BIGINT)
    author = Column(BIGINT)
    author_name = Column(VARCHAR(32))
    author_avatar = Column(TEXT)
    content = Column(VARCHAR(2000))
    image = Column(TEXT)
    board_post = Column(BIGINT)

    users = relationship(
        lambda: StarUsers,
        cascade='all, delete-orphan',
        backref='post',
        lazy='immediate',
        innerjoin=True
    )
    __table_args__ = (
        UniqueConstraint(message),
    )

    @staticmethod
    def star_emoji(stars: int):
        if 5 > stars >= 0:
            return '\N{WHITE MEDIUM STAR}'
        elif 10 > stars >= 5:
            return '\N{GLOWING STAR}'
        elif 25 > stars >= 10:
            return '\N{DIZZY SYMBOL}'
        else:
            return '\N{SPARKLES}'

    def prepare_message(self) -> typing.Optional[dict[str, typing.Union[str, discord.Embed]]]:
        num_votes = len(self.users)
        if num_votes >= self.config.threshold:
            emoji = self.star_emoji(num_votes)
            return {
                'content': f'{emoji} **{num_votes}** ID: {self.message}',
                'embed': discord.Embed(
                    description=self.content,
                    timestamp=discord.utils.snowflake_time(self.message),
                    colour=0xF8D66A
                ).set_author(
                    name=self.author_name,
                    icon_url=self.author_avatar
                ).add_field(
                    name='Original',
                    value=f'[Jump!](https://discord.com/channels/{self.config.guild}/{self.channel}/{self.message})'
                )
            }

    async def add_user(self, user_id: int):
        if user_id == self.author:
            return
        if discord.utils.get(self.users, person=user_id):
            return
        self.users.append(StarUsers(
            post_id=self.id,
            person=user_id
        ))
        fields = self.prepare_message()
        if fields:
            board_channel: discord.TextChannel = self.bot.get_channel(self.channel)
            if self.board_post:
                await board_channel.get_partial_message(self.board_post).edit(**fields)
            else:
                self.board_post = (await board_channel.send(**fields)).id

    async def remove_user(self, sess: AsyncSession, user_id: int):
        user = discord.utils.get(self.users, person=user_id)
        if user is None:
            return
        sess.delete(user)
        if self.board_post:
            msg: discord.PartialMessage = self.bot.get_channel(self.channel).get_partial_message(self.board_post)
            fields = self.prepare_message()
            if fields:
                await msg.edit(**fields)
            else:
                await msg.delete()


class StarUsers(BaseTable):
    id = Column(INTEGER, primary_key=True)
    post_id = Column(INTEGER, ForeignKey(StarPosts.id))
    person = Column(BIGINT)

    __table_args__ = (UniqueConstraint(post_id, person),)


class StarWhoPageSource(menus.ListPageSource):
    def __init__(self, members: list[typing.Optional[discord.Member]]):
        self._missing = members.count(None)
        self._total = len(members)
        pag = commands.Paginator('', '', max_size=1900)
        for i, member in enumerate(filter(None, members), 1):
            pag.add_line(f'{i}. {member}')
        super().__init__(pag.pages, per_page=1)

    def format_page(self, menu: NavMenuPages, page: str):
        return discord.Embed(
            title=f'{self._total} stars ({self._missing} left server)',
            description=f'{page}\n\nConfused? React with \N{INFORMATION SOURCE} for more info.',
            colour=discord.Colour.blurple()
        ).set_footer(
            text=f'Page {menu.current_page + 1}/{self.get_max_pages()} ({self._total - self._missing}) entries'
        )


class Stars(BaseCog):
    """Commands related to the starboard."""

    MEDALS = '\N{FIRST PLACE MEDAL}', '\N{SECOND PLACE MEDAL}', '\N{THIRD PLACE MEDAL}'

    async def init_db(self, sql: AsyncConnection):
        await StarConfig.create(sql)
        await StarPosts.create(sql)
        await StarUsers.create(sql)

    async def get_or_create_post(self, conf: StarConfig, channel_id: int, message_id: int):
        post: typing.Optional[StarPosts] = discord.utils.get(conf.posts, message=message_id) \
                                           or discord.utils.get(conf.posts, board_post=message_id)
        if post is None:
            message: discord.Message = await self.bot.get_channel(channel_id).fetch_message(message_id)
            post = StarPosts(
                channel=channel_id,
                message=message_id,
                author=message.author.id,
                author_name=message.author.display_name,
                author_avatar=str(message.author.avatar_url),
                content=message.content or '\u200b'
            )
            if message.attachments and message.attachments[0].height:
                post.image = str(message.attachments[0].proxy_url)
            conf.posts.append(post)
        return post

    @BaseCog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.guild_id is None:
            return
        async with self.bot.sql_session as sess:
            conf = await sess.get(StarConfig, payload.guild_id)
            if conf is not None and str(payload.emoji) == conf.emoji:
                post = await self.get_or_create_post(conf, payload.channel_id, payload.message_id)
                await post.add_user(payload.user_id)

    @BaseCog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if payload.guild_id is None:
            return
        async with self.bot.sql_session as sess:
            conf = await sess.get(StarConfig, payload.guild_id)
            if conf is not None and str(payload.emoji) == conf.emoji:
                post = await self.get_or_create_post(conf, payload.channel_id, payload.message_id)
                await post.remove_user(sess, payload.user_id)

    @commands.group('star', invoke_without_command=True)
    async def star_grp(self, ctx: MyContext, message: discord.Message):
        """Stars a message by ID."""

        if ctx.guild != message.guild:
            return await ctx.send('Attempting to star a message not in this server')
        async with self.bot.sql_session as sess:
            cfg = await sess.get(StarConfig, ctx.guild.id)
            if cfg is not None:
                post = await self.get_or_create_post(cfg, message.channel.id, message.id)
                if post.author == ctx.author.id:
                    return await ctx.send('You cannot star your own message.')
                await post.add_user(ctx.author.id)

    @commands.bot_has_permissions(add_reactions=True, manage_channels=True)
    @commands.has_permissions(manage_guild=True)
    @star_grp.command('config')
    async def star_config(
            self,
            ctx: MyContext,
            channel: typing.Optional[discord.TextChannel],
            threshold: typing.Optional[int],
            emoji: typing.Optional[typing.Union[discord.Emoji, str]]
    ):
        """Setup or update the server's starboard config."""

        if channel is not None:
            if channel.guild != ctx.guild:
                return await ctx.send('That channel is in another guild!')
            perms = channel.permissions_for(ctx.guild.me)
            if not perms.send_messages:
                return await ctx.send('I cannot send messages in that channel!')
        async with self.bot.sql_session as sess:
            if emoji:
                try:
                    await ctx.message.add_reaction(emoji)
                except discord.HTTPException:
                    return await ctx.send(f'Invalid emoji: {emoji}')
            cfg = await sess.get(StarConfig, ctx.guild.id)
            if cfg is None:
                if channel is None:
                    channel = await ctx.guild.create_text_channel(
                        'starboard',
                        overwrites={
                            ctx.guild.default_role: discord.PermissionOverwrite(send_messages=False),
                            ctx.guild.me: discord.PermissionOverwrite(send_messages=True)
                        },
                        reason='Create starboard'
                    )
                cfg = StarConfig(
                    guild=ctx.guild.id,
                    channel=channel.id,
                    created_at=ctx.message.created_at
                )
                sess.add(cfg)
                await sess.refresh(cfg)
            elif channel is not None:
                cfg.channel = channel.id
            if threshold is not None:
                cfg.threshold = threshold
            if emoji is not None:
                cfg.emoji = emoji
        await ctx.message.add_reaction('\N{WHITE HEAVY CHECK MARK}')

    @star_grp.command('random')
    async def star_random(self, ctx: MyContext):
        """Show a random starred post on this server."""

        async with self.bot.sql_session as sess:
            cfg = await sess.get(StarConfig, ctx.guild.id)
            if cfg is None:
                return await ctx.send('This server is not configured for starboard')
            posts: list[StarPosts] = [post for post in cfg.posts if len(post.users) >= cfg.threshold]
            if not posts:
                return await ctx.send('No starred posts in this server')
            post = random.choice(posts)
        await ctx.send(**post.prepare_message())

    @star_grp.command('show')
    async def star_show(self, ctx: MyContext, message_id: int):
        """Show a starred post by message ID."""

        async with self.bot.sql_session as sess:
            cfg = await sess.get(StarConfig, ctx.guild.id)
            if cfg is None:
                return await ctx.send('This server is not configured for starboard')
            post: typing.Optional[StarPosts] = discord.utils.get(cfg.posts, message=message_id)
            if post is None:
                return await ctx.send('No starred post found with that ID')
            fields = post.prepare_message()
            if not fields:
                return await ctx.send('No starred post found with that ID')
        await ctx.send(**fields)

    async def guild_stats(self, cfg: StarConfig, ctx: MyContext):
        posts = sorted(cfg.posts, lambda p: len(p.users), reverse=True)
        all_users = [user for post in posts for user in post.users]
        givers = sorted(Counter(all_users).items(), key=lambda t: t[1], reverse=True)
        receivers = sorted(
            Counter(user.post.author for user in all_users).items(),
            key=lambda t: t[1],
            reverse=True
        )
        embed = discord.Embed(
            title='Server Starboard Stats',
            description=f'{len(posts)} messages starred with a total of {len(all_users)} stars.',
            timestamp=cfg.created_at,
            colour=0xF8D66A
        ).set_footer(
            text='Adding stars since'
        )
        if posts:
            embed.add_field(
                name='Top Starred Posts',
                value='\n'.join(
                    f'{medal}: {post.id} ({len(post.users)} stars)'
                    for medal, post in zip(self.MEDALS, posts)
                ),
                inline=False
            ).add_field(
                name='Top Star Receivers',
                value='\n'.join(
                    f'{medal}: <@!{x[0]}> ({x[1]} stars)'
                    for medal, x in zip(self.MEDALS, receivers)
                ),
                inline=False
            ).add_field(
                name='Top Star Givers',
                value='\n'.join(
                    f'{medal}: <@!{x[0]}> ({x[1]} stars)'
                    for medal, x in zip(self.MEDALS, givers)
                ),
                inline=False
            )
        await ctx.send(embed=embed)

    async def member_stats(self, cfg: StarConfig, ctx: MyContext, member: discord.Member):
        nstars_given = sum(1 for post in cfg.posts for star in post.users if star.person == member.id)
        messages_starred: list[StarPosts] = sorted(
            [post for post in cfg.posts if post.author == member.id],
            key=lambda x: len(x.users),
            reverse=True
        )
        nstars_received = sum(1 for post in messages_starred for _ in post.users)
        embed = discord.Embed(
            colour=0xF8D66A
        ).set_author(
            name=member.display_name,
            icon_url=member.avatar_url
        ).add_field(
            name='Messages Starred',
            value=str(len(messages_starred))
        ).add_field(
            name='Stars Received',
            value=str(nstars_received)
        ).add_field(
            name='Stars Given',
            value=str(nstars_given)
        ).add_field(
            name='Top Starred Posts',
            value='\n'.join(
                f'{medal}: {post.message} ({len(post.users)})'
                for medal, post in zip(self.MEDALS, messages_starred)
            )
        )
        await ctx.send(embed=embed)

    @star_grp.command('stats')
    async def star_stats(self, ctx: MyContext, member: discord.Member = None):
        """Show starboard stats for this server or for a specific member."""
        async with self.bot.sql_session as sess:
            cfg = await sess.get(StarConfig, ctx.guild.id)
            if cfg is None:
                return await ctx.send('This server is not configured for starboard')
            if member is None:
                await self.guild_stats(cfg, ctx)
            else:
                await self.member_stats(cfg, ctx, member)

    @star_grp.command('who')
    async def star_who(self, ctx: MyContext, message_id: int):
        """Show who starred a specific post."""

        async with self.bot.sql_session as sess:
            cfg = await sess.get(StarConfig, ctx.guild.id)
            if cfg is None:
                return await ctx.send('This server is not configured for starboard')
            post: typing.Optional[StarPosts] = discord.utils.get(cfg.posts, message=message_id)
            if post is None:
                return await ctx.send('No starred post found with that ID')
            members = [ctx.guild.get_member(user.person) for user in post.users]
        menu = NavMenuPages(StarWhoPageSource(members), delete_message_after=True, clear_reactions_after=True)
        await menu.start(ctx)


def setup(bot: PikalaxBOT):
    bot.add_cog(Stars(bot))


def teardown(bot: PikalaxBOT):
    StarUsers.unlink()
    StarPosts.unlink()
    StarConfig.unlink()
