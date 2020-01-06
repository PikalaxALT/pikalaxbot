import discord
from discord.ext import commands
from . import BaseCog
import collections
import typing
from .utils.errors import *


class ReactionRoles(BaseCog):
    def __init__(self, bot):
        super().__init__(bot)
        self.reaction_schema = {}
        self.reaction_roles = collections.defaultdict(dict)
    
    async def cog_check(self, ctx):
        if not ctx.me.guild_permissions.manage_roles:
            raise commands.BotMissingPermissions(['manage_roles'])
        return True

    async def init_db(self, sql):
        await sql.execute("create table if not exists reaction_schema (guild integer unique not null primary key, channel integer, message integer)")
        await sql.execute("create table if not exists reaction_roles (guild integer not null primary key, emoji text, role integer)")
        c = await sql.execute("select * from reaction_schema")
        for guild, channel, message in await c.fetchall():
            self.reaction_schema[guild] = (channel, message)
        c = await sql.execute("select * from reaction_roles")
        for guild, emoji, role in await c.fetchall():
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

    @commands.command(name='register')
    @commands.has_permissions(manage_roles=True)
    async def register_role_bot(self, ctx: commands.Context, channel: typing.Optional[discord.TextChannel]):
        """Register the role reaction bot to the specified channel (default: the current channel)"""
        if ctx.guild.id in self.reaction_schema:
            raise AlreadyInitialized
        channel = channel or ctx.channel
        if channel.permissions_for(ctx.me).send_messages:
            message = await channel.send('React to the following emoji to get the associated roles:')
            self.reaction_schema[ctx.guild.id] = (channel.id, message.id)
            with self.bot.sql as sql:
                await sql.execute("insert into reaction_schema values (?, ?, ?)", (ctx.guild.id, channel.id, message.id))
            await ctx.message.add_reaction('✅')

    @commands.command(name='drop')
    @commands.has_permissions(manage_roles=True)
    async def unregister_role_bot(self, ctx: commands.Context):
        """Drops the role reaction registration in this guild"""
        if ctx.guild.id not in self.reaction_schema:
            raise NotInitialized
        channel_id, message_id = self.reaction_schema[ctx.guild.id]
        channel = ctx.guild.get_channel(channel_id)
        message = await channel.fetch_message(message_id)
        await message.delete()
        self.reaction_schema.pop(ctx.guild.id)
        self.reaction_roles.pop(ctx.guild.id, None)
        with self.bot.sql as sql:
            await sql.execute("delete from reaction_schema where guild = ?", (ctx.guild.id,))
            await sql.execute("delete from reaction_roles where guild = ?", (ctx.guild.id,))
        await ctx.message.add_reaction('✅')

    @commands.command(name='add-role')
    async def add_role(self, ctx: commands.Context, emoji: typing.Union[discord.Emoji, str], *, role: discord.Role):
        """Register a role to an emoji in the current guild"""
        if ctx.guild.id not in self.reaction_schema:
            raise NotInitialized
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
            await sql.execute("insert into reaction_roles values (?, ?, ?)", (ctx.guild.id, str(emoji), role.id))
        await ctx.message.add_reaction('✅')
    
    @commands.command('drop-role')
    async def drop_role(self, ctx: commands.Context, *, emoji_or_role: typing.Union[discord.Emoji, discord.Role, str]):
        if ctx.guild.id not in self.reaction_schema:
            raise NotInitialized
        channel_id, message_id = self.reaction_schema[ctx.guild.id]
        channel = ctx.guild.get_channel(channel_id)
        if channel is None:
            raise InitializationInvalid
        try:
            message = await channel.fetch_message(message_id)
        except discord.HTTPException:
            raise InitializationInvalid
        if isinstance(emoji_or_role, discord.Role):
            role = emoji_or_role
            for emoji, role_id in self.reaction_roles[ctx.guild.id].items():
                if role_id == role.id:
                    break
            else:
                raise RoleOrEmojiNotFound
        else:
            emoji = emoji_or_role
            role = self.reaction_roles.get(str(emoji))
            if role is None:
                raise RoleOrEmojiNotFound
        self.reaction_roles[ctx.guild.id].pop(str(emoji))
        await message.remove_reaction(emoji)
        with self.bot.sql as sql:
            await sql.execute("delete from reaction_roles where guild = ? and emoji = ?", (ctx.guild.id, str(emoji)))
        await ctx.message.add_reaction('✅')

    async def cog_command_error(self, ctx, error):
        await ctx.send(f'**{error.__class__.__name__}:** {error}')


def setup(bot):
    bot.add_cog(ReactionRoles(bot))
