import discord
from discord.ext import commands
from . import *
import collections
import typing
from .utils.errors import *


def reaction_roles_initialized():
    def predicate(ctx: MyContext):
        if ctx.guild.id not in ctx.cog.reaction_schema:
            raise NotInitialized
        return True
    return predicate


def reaction_roles_not_initialized():
    def predicate(ctx: MyContext):
        if ctx.guild.id in ctx.cog.reaction_schema:
            raise AlreadyInitialized
        return True
    return predicate


class ReactionRoles(BaseCog):
    """Commands and functionality for reaction roles."""

    def __init__(self, bot):
        super().__init__(bot)
        self.reaction_schema: dict[int, tuple[int, int]] = {}
        self.reaction_roles: dict[int, dict[str, int]] = collections.defaultdict(dict)
    
    def cog_check(self, ctx):
        return all(check.predicate(ctx) for check in {commands.guild_only(), commands.bot_has_guild_permissions(manage_roles=True)})

    async def init_db(self, sql):
        await sql.execute("create table if not exists reaction_schema (guild bigint unique not null primary key, channel bigint, message bigint)")
        await sql.execute("create table if not exists reaction_roles (guild bigint not null references reaction_schema(guild), emoji text, role bigint)")
        async for guild, channel, message in sql.cursor('select * from reaction_schema'):
            self.reaction_schema[guild] = (channel, message)
        async for guild, emoji, role in sql.cursor('select * from reaction_roles'):
            self.reaction_roles[guild][emoji] = role

    def validate_reaction(self, payload: discord.RawReactionActionEvent):
        if payload.guild_id not in self.reaction_schema:
            return False
        channel_id, message_id = self.reaction_schema[payload.guild_id]
        if channel_id != payload.channel_id or message_id != payload.message_id:
            return False
        registered_roles = self.reaction_roles[payload.guild_id]
        if str(payload.emoji) not in registered_roles:
            return False
        return True

    @BaseCog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if not self.validate_reaction(payload):
            return
        guild: discord.Guild = self.bot.get_guild(payload.guild_id)
        role: discord.Role = guild.get_role(self.reaction_roles[payload.guild_id][str(payload.emoji)])
        author: discord.Member = guild.get_member(payload.user_id)
        await author.add_roles(role)

    @BaseCog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if not self.validate_reaction(payload):
            return
        guild: discord.Guild = self.bot.get_guild(payload.guild_id)
        role: discord.Role = guild.get_role(self.reaction_roles[payload.guild_id][str(payload.emoji)])
        author: discord.Member = guild.get_member(payload.user_id)
        await author.remove_roles(role)

    @reaction_roles_not_initialized()
    @commands.has_permissions(manage_roles=True)
    @commands.command(name='register')
    async def register_role_bot(self, ctx: MyContext, channel: typing.Optional[discord.TextChannel]):
        """Register the role reaction bot to the specified channel (default: the current channel)"""

        channel = channel or ctx.channel
        if channel.permissions_for(ctx.me).send_messages:
            message = await channel.send('React to the following emoji to get the associated roles:')
            self.reaction_schema[ctx.guild.id] = (channel.id, message.id)
            with self.bot.sql as sql:
                await sql.execute("insert into reaction_schema values ($1, $2, $3)", ctx.guild.id, channel.id, message.id)
            await ctx.message.add_reaction('✅')

    @reaction_roles_initialized()
    @commands.has_permissions(manage_roles=True)
    @commands.command(name='drop')
    async def unregister_role_bot(self, ctx: MyContext):
        """Drops the role reaction registration in this guild"""

        channel_id, message_id = self.reaction_schema[ctx.guild.id]
        await self.bot.http.delete_message(channel_id, message_id, reason='Requested to unregister roles bot')
        self.reaction_schema.pop(ctx.guild.id)
        self.reaction_roles.pop(ctx.guild.id, None)
        with self.bot.sql as sql:
            await sql.execute("delete from reaction_roles where guild = $1", ctx.guild.id)
            await sql.execute("delete from reaction_schema where guild = $1", ctx.guild.id)
        await ctx.message.add_reaction('✅')

    @reaction_roles_initialized()
    @commands.command(name='add-role')
    async def add_role(self, ctx: MyContext, emoji: typing.Union[discord.Emoji, str], *, role: discord.Role):
        """Register a role to an emoji in the current guild"""

        channel_id, message_id = self.reaction_schema[ctx.guild.id]
        channel = ctx.guild.get_channel(channel_id)
        if channel is None:
            raise InitializationInvalid
        try:
            message = await channel.fetch_message(message_id)
        except discord.HTTPException:
            raise InitializationInvalid
        if any(str(reaction.emoji) == emoji for reaction in message.reactions):
            raise ReactionAlreadyRegistered
        await message.add_reaction(emoji)
        with self.bot.sql as sql:
            await sql.execute("insert into reaction_roles values ($1, $2, $3)", ctx.guild.id, str(emoji), role.id)
        await ctx.message.add_reaction('✅')

    @reaction_roles_initialized()
    @commands.command('drop-role')
    async def drop_role(self, ctx: MyContext, *, emoji_or_role: typing.Union[discord.Emoji, discord.Role, str]):
        """Unregister a role or emoji from the current guild"""

        channel_id, message_id = self.reaction_schema[ctx.guild.id]
        channel = ctx.guild.get_channel(channel_id)
        if channel is None:
            raise InitializationInvalid
        try:
            message = await channel.fetch_message(message_id)
        except discord.HTTPException:
            raise InitializationInvalid
        if isinstance(emoji_or_role, discord.Role):
            try:
                emoji, role_id = discord.utils.find(lambda t: t[0] == emoji_or_role.id, self.reaction_roles[ctx.guild.id].items())
            except ValueError:
                raise RoleOrEmojiNotFound
        else:
            if self.reaction_roles[ctx.guild.id].get(str(emoji := emoji_or_role)) is None:
                raise RoleOrEmojiNotFound
        self.reaction_roles[ctx.guild.id].pop(str(emoji))
        await message.remove_reaction(emoji)
        with self.bot.sql as sql:
            await sql.execute("delete from reaction_roles where guild = $1 and emoji = $2", ctx.guild.id, str(emoji))
        await ctx.message.add_reaction('✅')

    async def cog_command_error(self, ctx: MyContext, error: commands.CommandError):
        await ctx.send(f'**{error.__class__.__name__}:** {error}')


def setup(bot: PikalaxBOT):
    bot.add_cog(ReactionRoles(bot))
