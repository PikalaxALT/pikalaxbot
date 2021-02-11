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

import discord
from discord.ext import commands
from . import *
import typing
from .utils.errors import *

from sqlalchemy import Column, ForeignKey, BIGINT, TEXT, select, delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.exc import StatementError, NoResultFound


class ReactionSchema(BaseTable):
    guild = Column(BIGINT, primary_key=True)
    channel = Column(BIGINT)
    message = Column(BIGINT)

    @classmethod
    async def register(
            cls,
            conn: AsyncConnection,
            guild: discord.Guild,
            channel: discord.TextChannel,
            message: discord.Message
    ):
        statement = insert(cls).values(
            guild=guild.id,
            channel=channel.id,
            message=message.id
        )
        await conn.execute(statement)

    @classmethod
    async def unregister(cls, conn: AsyncConnection, guild: discord.Guild):
        statement = delete(cls).where(cls.guild == guild.id)
        await conn.execute(statement)

    @classmethod
    async def get_cfg(cls, conn: AsyncConnection, guild_id: int):
        statement = select([cls.channel, cls.message]).where(cls.guild == guild_id)
        result = await conn.execute(statement)
        return result.one()


class ReactionRoles(BaseTable):
    guild = Column(BIGINT, ForeignKey(ReactionSchema, ondelete='CASCADE'))
    emoji = Column(TEXT, nullable=False)
    role = Column(BIGINT, unique=True, nullable=False)

    @classmethod
    async def from_emoji(cls, conn: AsyncConnection, emoji: str):
        statement = select(cls.role).where(cls.emoji == emoji)
        return await conn.scalar(statement)

    @classmethod
    async def mappings(cls, conn: AsyncConnection, guild_id: int):
        statement = select([cls.emoji, cls.role]).where(cls.guild == guild_id)
        result = await conn.execute(statement)
        return result.all()

    @classmethod
    async def add(cls, conn: AsyncConnection, guild: discord.Guild, emoji: str, role: discord.Role):
        statement = insert(cls).values(
            guild=guild.id,
            emoji=emoji,
            role=role.id
        )
        await conn.execute(statement)

    @classmethod
    async def remove(
            cls,
            conn: AsyncConnection,
            guild: discord.Guild,
            emoji_or_role: typing.Union[discord.Emoji, discord.Role, str]
    ):
        kwargs = {cls.guild: guild.id}
        if isinstance(emoji_or_role, discord.Role):
            kwargs[cls.role] = emoji_or_role.id
        else:
            kwargs[cls.emoji] = str(emoji_or_role)
        statement = delete(cls).where(**kwargs).returning(cls.emoji)
        return await conn.scalar(statement)


def reaction_roles_initialized():
    async def predicate(ctx: MyContext):
        try:
            await ctx.cog.get_reaction_config(ctx.guild.id)
        except NoResultFound:
            raise NotInitialized(
                'Reaction roles is not configured. To configure, use `{}rrole register`.'.format(
                    (await ctx.bot.get_prefix(ctx.message))[0]
                )
            ) from None
        return True
    return commands.check(predicate)


def reaction_roles_not_initialized():
    async def predicate(ctx: MyContext):
        try:
            await ctx.cog.get_reaction_config(ctx.guild.id)
        except NoResultFound:
            pass
        else:
            raise AlreadyInitialized(
                'Reaction roles is already configured. To reconfigure, use `{}rrole drop` first.'.format(
                    (await ctx.bot.get_prefix(ctx.message))[0]
                )
            )
        return True
    return commands.check(predicate)


class ReactionRolesCog(BaseCog, name='ReactionRoles'):
    """Commands and functionality for reaction roles."""
    
    async def cog_check(self, ctx):
        return all([await check.predicate(ctx) for check in {
            commands.guild_only(),
            commands.bot_has_guild_permissions(manage_roles=True)
        }])

    async def init_db(self, sql):
        await ReactionSchema.create(sql)
        await ReactionRoles.create(sql)

    async def get_role_id_by_emoji(self, payload: discord.RawReactionActionEvent) -> typing.Optional[int]:
        async with self.bot.sql as sql:
            return await ReactionRoles.from_emoji(sql, str(payload.emoji))

    async def get_guild_role_mappings(self, guild_id: int):
        async with self.bot.sql as sql:
            return await ReactionRoles.mappings(sql, guild_id)

    async def get_reaction_config(self, guild_id: int):
        async with self.bot.sql as sql:
            return await ReactionSchema.get_cfg(sql, guild_id)

    async def resolve_payload(self, payload: discord.RawReactionActionEvent):
        guild: discord.Guild = self.bot.get_guild(payload.guild_id)
        member: typing.Optional[discord.Member] = guild.get_member(payload.user_id)
        role: typing.Optional[discord.Role] = guild.get_role(await self.get_role_id_by_emoji(payload))
        return member, role

    @BaseCog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        member, role = await self.resolve_payload(payload)
        if member and role:
            await member.add_roles(role, reason='Reaction Roles')

    @BaseCog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        member, role = await self.resolve_payload(payload)
        if member and role:
            await member.remove_roles(role, reason='Reaction Roles')

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
                await ReactionSchema.register(sql, ctx.guild, channel, message)
            await ctx.message.add_reaction('✅')

    @reaction_roles_initialized()
    @commands.has_permissions(manage_roles=True)
    @rrole.command(name='drop')
    async def unregister_role_bot(self, ctx: MyContext):
        """Drops the role reaction registration in this guild"""

        channel_id, message_id = await self.get_reaction_config(ctx.guild.id)
        channel: discord.TextChannel = ctx.guild.get_channel(channel_id)
        if channel is None:
            raise InitializationInvalid('Reaction roles channel not found')
        message: discord.PartialMessage = channel.get_partial_message(message_id)
        await message.delete()
        async with self.bot.sql as sql:
            await ReactionSchema.unregister(sql, ctx.guild)
        await ctx.message.add_reaction('✅')

    @reaction_roles_initialized()
    @rrole.command(name='add')
    async def add_role(self, ctx: MyContext, emoji: typing.Union[discord.Emoji, str], *, role: discord.Role):
        """Register a role to an emoji in the current guild"""

        channel_id, message_id = await self.get_reaction_config(ctx.guild.id)
        channel: discord.TextChannel = ctx.guild.get_channel(channel_id)
        if channel is None:
            raise InitializationInvalid('Reaction roles channel not found')
        message: discord.PartialMessage = channel.get_partial_message(message_id)
        async with self.bot.sql as sql:
            try:
                await ReactionRoles.add(sql, ctx.guild, str(emoji), role)
                await message.add_reaction(emoji)
            except StatementError:
                raise ReactionAlreadyRegistered('Role or emoji already registered with reaction roles') from None
            except discord.NotFound as e:
                exc = {
                    10008: InitializationInvalid('Reaction roles message not found'),
                    10014: RoleOrEmojiNotFound(emoji)
                }.get(e.code, e)
                raise exc from None
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
            raise InitializationInvalid('Reaction roles channel not found')
        message: discord.PartialMessage = channel.get_partial_message(message_id)
        async with self.bot.sql as sql:
            try:
                emoji = await ReactionRoles.remove(sql, ctx.guild, emoji_or_role)
                if emoji is None:
                    raise RoleOrEmojiNotFound(emoji_or_role)
                await message.remove_reaction(emoji, ctx.me)
            except discord.NotFound as e:
                exc = {
                    10008: InitializationInvalid('Reaction roles message not found'),
                    10014: RoleOrEmojiNotFound(emoji_or_role)
                }.get(e.code, e)
                raise exc from None
        embed = await self.make_embed(ctx)
        await message.edit(embed=embed)
        await ctx.message.add_reaction('✅')


def setup(bot: PikalaxBOT):
    bot.add_cog(ReactionRolesCog(bot))
