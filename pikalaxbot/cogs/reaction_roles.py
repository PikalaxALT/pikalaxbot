import discord
from discord.ext import commands
from . import *
import typing
import asyncpg
from .utils.errors import *


def reaction_roles_initialized():
    async def predicate(ctx: MyContext):
        if not await ctx.cog.get_reaction_config(ctx.guild.id):
            raise NotInitialized
        return True
    return commands.check(predicate)


def reaction_roles_not_initialized():
    async def predicate(ctx: MyContext):
        if await ctx.cog.get_reaction_config(ctx.guild.id):
            raise AlreadyInitialized
        return True
    return commands.check(predicate)


class ReactionRoles(BaseCog):
    """Commands and functionality for reaction roles."""
    
    def cog_check(self, ctx):
        return all(check.predicate(ctx) for check in {
            commands.guild_only(),
            commands.bot_has_guild_permissions(manage_roles=True)
        })

    async def init_db(self, sql):
        await sql.execute(
            "create table if not exists reaction_schema ("
            "guild bigint unique not null primary key, "
            "channel bigint, "
            "message bigint"
            ")"
        )
        await sql.execute(
            "create table if not exists reaction_roles ("
            "guild bigint not null references reaction_schema(guild) deferrable initially deferred, "
            "emoji text not null, "
            "role bigint unique not null"
            ")"
        )

    async def get_role_id_by_emoji(self, payload: discord.RawReactionActionEvent) -> typing.Optional[int]:
        async with self.bot.sql as sql:  # type: asyncpg.Connection
            return await sql.fetchval(
                'select role '
                'from reaction_roles '
                'where guild = $1 '
                'and emoji = $2',
                payload.guild_id,
                str(payload.emoji)
            )

    async def get_guild_role_mappings(self, guild_id: int) -> list[tuple[str, int]]:
        async with self.bot.sql as sql:  # type: asyncpg.Connection
            return await sql.fetch(
                'select emoji, role '
                'from reaction_roles '
                'where guild = $1',
                guild_id
            )

    async def get_reaction_config(self, guild_id: int) -> typing.Optional[tuple[int, int]]:
        async with self.bot.sql as sql:  # type: asyncpg.Connection
            return await sql.fetchrow(
                'select channel, message '
                'from reaction_schema '
                'where guild = $1',
                guild_id
            )

    @BaseCog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if role_id := await self.get_role_id_by_emoji(payload):
            await self.bot.http.add_role(
                payload.guild_id,
                payload.user_id,
                role_id,
                reason='Reaction Roles'
            )

    @BaseCog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if role_id := await self.get_role_id_by_emoji(payload):
            await self.bot.http.remove_role(
                payload.guild_id,
                payload.user_id,
                role_id,
                reason='Reaction Roles'
            )

    async def make_embed(self, ctx: MyContext):
        roles_str = '\n'.join(
            f'{emoji} - {ctx.guild.get_role(role).mention}'
            for emoji, role in await self.get_guild_role_mappings(ctx.guild.id)
        ) or 'None configured yet'
        return discord.Embed(
            title=f'Reaction Roles in {ctx.guild}',
            description=f'React to the following emoji to get the associated roles:\n\n{roles_str}',
            colour=0xf47fff
        )

    @commands.group()
    async def rrole(self, ctx: MyContext):
        """Commands related to reaction roles"""

    @reaction_roles_not_initialized()
    @commands.has_permissions(manage_roles=True)
    @rrole.command(name='register')
    async def register_role_bot(self, ctx: MyContext, channel: discord.TextChannel = None):
        """Register the role reaction bot to the specified channel (default: the current channel)"""

        channel = channel or ctx.channel
        if channel.permissions_for(ctx.me).send_messages:
            embed = await self.make_embed(ctx)
            message = await channel.send(embed=embed)
            async with self.bot.sql as sql:
                await sql.execute(
                    "insert into reaction_schema "
                    "values ($1, $2, $3)",
                    ctx.guild.id,
                    channel.id,
                    message.id
                )
            await ctx.message.add_reaction('✅')

    @reaction_roles_initialized()
    @commands.has_permissions(manage_roles=True)
    @rrole.command(name='drop')
    async def unregister_role_bot(self, ctx: MyContext):
        """Drops the role reaction registration in this guild"""

        channel_id, message_id = await self.get_reaction_config(ctx.guild.id)
        channel: discord.TextChannel = ctx.guild.get_channel(channel_id)
        if channel is None:
            raise InitializationInvalid
        message: discord.PartialMessage = channel.get_partial_message(message_id)
        await message.delete()
        async with self.bot.sql as sql:  # type: asyncpg.Connection
            await sql.execute("delete from reaction_roles where guild = $1", ctx.guild.id)
            await sql.execute("delete from reaction_schema where guild = $1", ctx.guild.id)
        await ctx.message.add_reaction('✅')

    @reaction_roles_initialized()
    @rrole.command(name='add')
    async def add_role(self, ctx: MyContext, emoji: typing.Union[discord.Emoji, str], *, role: discord.Role):
        """Register a role to an emoji in the current guild"""

        channel_id, message_id = await self.get_reaction_config(ctx.guild.id)
        channel: discord.TextChannel = ctx.guild.get_channel(channel_id)
        if channel is None:
            raise InitializationInvalid
        message: discord.PartialMessage = channel.get_partial_message(message_id)
        try:
            async with self.bot.sql as sql:  # type: asyncpg.Connection
                async with sql.transaction():
                    await sql.execute(
                        "insert into reaction_roles "
                        "values ($1, $2, $3)",
                        ctx.guild.id,
                        str(emoji),
                        role.id
                    )
                    await message.add_reaction(emoji)
        except asyncpg.UniqueViolationError as e:
            raise ReactionAlreadyRegistered from e
        except discord.HTTPException as e:
            raise InitializationInvalid from e
        embed = await self.make_embed(ctx)
        await message.edit(embed=embed)
        await ctx.message.add_reaction('✅')

    @reaction_roles_initialized()
    @rrole.command('remove')
    async def drop_role(self, ctx: MyContext, *, emoji_or_role: typing.Union[discord.Emoji, discord.Role, str]):
        """Unregister a role or emoji from the current guild"""

        channel_id, message_id = await self.get_reaction_config(ctx.guild.id)
        channel: discord.TextChannel = ctx.guild.get_channel(channel_id)
        if channel is None:
            raise InitializationInvalid
        message: discord.PartialMessage = channel.get_partial_message(message_id)
        try:
            async with self.bot.sql as sql:  # type: asyncpg.Connection
                async with sql.transaction():
                    if isinstance(emoji_or_role, discord.Role):
                        emoji = await sql.execute(
                            "delete from reaction_roles "
                            "where guild = $1 "
                            "and role = $2 "
                            "returning emoji",
                            ctx.guild.id,
                            emoji_or_role.id
                        )
                    else:
                        emoji = await sql.execute(
                            "delete from reaction_roles "
                            "where guild = $1 "
                            "and emoji = $2 "
                            "returning emoji",
                            ctx.guild.id,
                            str(emoji_or_role)
                        )
                    if emoji is None:
                        raise RoleOrEmojiNotFound
                    await message.remove_reaction(emoji, ctx.me)
        except discord.HTTPException as e:
            raise InitializationInvalid from e
        embed = await self.make_embed(ctx)
        await message.edit(embed=embed)
        await ctx.message.add_reaction('✅')

    async def cog_command_error(self, ctx: MyContext, error: commands.CommandError):
        await ctx.send(f'**{error.__class__.__name__}:** {error}')


def setup(bot: PikalaxBOT):
    bot.add_cog(ReactionRoles(bot))
