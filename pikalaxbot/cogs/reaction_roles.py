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

from sqlalchemy import Column, ForeignKey, UniqueConstraint, BIGINT, TEXT, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import StatementError
from sqlalchemy.orm import relationship, Session


class ReactionSchema(BaseTable):
    guild = Column(BIGINT, primary_key=True)
    channel = Column(BIGINT)
    message = Column(BIGINT)

    roles = relationship('ReactionRoles', backref='schema', cascade='all, delete-orphan')


class ReactionRoles(BaseTable):
    guild = Column(BIGINT, ForeignKey(ReactionSchema.guild, ondelete='CASCADE'), primary_key=True)
    emoji = Column(TEXT, nullable=False)
    role = Column(BIGINT, nullable=False)

    __table_args__ = (UniqueConstraint(guild, emoji, role),)


def get_config_sync(sess: Session, guild_id: discord.Guild):
    return sess.scalar(select(ReactionSchema).where(ReactionSchema.guild == guild_id))


def reaction_roles_initialized():
    async def predicate(ctx: MyContext):
        async with ctx.bot.sql_session as sess:  # type: AsyncSession
            ctx.rroles_cfg = await sess.run_sync(get_config_sync, ctx.guild.id)
            if ctx.rroles_cfg is None:
                raise NotInitialized(
                    'Reaction roles is not configured. To configure, use `{}rrole register`.'.format(
                        (await ctx.bot.get_prefix(ctx.message))[0]
                    )
                )
        return True
    return commands.check(predicate)


def reaction_roles_not_initialized():
    async def predicate(ctx: MyContext):
        async with ctx.bot.sql_session as sess:  # type: AsyncSession
            cfg = await sess.run_sync(get_config_sync, ctx.guild.id)
            if cfg is not None:
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

    async def resolve_payload(self, payload: discord.RawReactionActionEvent):
        guild: discord.Guild = self.bot.get_guild(payload.guild_id)
        member: typing.Optional[discord.Member] = guild.get_member(payload.user_id)
        async with self.bot.sql_session as sess:  # type: AsyncSession
            cfg = await sess.run_sync(get_config_sync, payload.guild_id)
            if cfg is None:
                role = None
            else:
                role: typing.Optional[discord.Role] = guild.get_role(discord.utils.get(cfg.roles, emoji=str(payload.emoji)))
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
            f'{role.emoji} - {ctx.guild.get_role(role.role).mention}'
            for role in ctx.rroles_cfg.roles
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
            async with self.bot.sql_session as sess:  # type: AsyncSession
                embed = await self.make_embed(ctx)
                message = await channel.send(embed=embed)
                cfg = ReactionSchema(
                    guild=ctx.guild.id,
                    channel=channel.id,
                    message=message.id
                )
                sess.add(cfg)
            await ctx.message.add_reaction('✅')

    @reaction_roles_initialized()
    @commands.has_permissions(manage_roles=True)
    @rrole.command(name='drop')
    async def unregister_role_bot(self, ctx: MyContext):
        """Drops the role reaction registration in this guild"""

        async with self.bot.sql_session as sess:  # type: AsyncSession
            await sess.refresh(ctx.rroles_cfg)
            channel: discord.TextChannel = ctx.guild.get_channel(ctx.rroles_cfg.channel)
            if channel is None:
                raise InitializationInvalid('Reaction roles channel not found')
            message: discord.PartialMessage = channel.get_partial_message(ctx.rroles_cfg.message)
            sess.delete(ctx.rroles_cfg)
            await message.delete()
        await ctx.message.add_reaction('✅')

    @reaction_roles_initialized()
    @rrole.command(name='add')
    async def add_role(self, ctx: MyContext, emoji: typing.Union[discord.Emoji, str], *, role: discord.Role):
        """Register a role to an emoji in the current guild"""

        async with self.bot.sql_session as sess:  # type: AsyncSession
            channel: discord.TextChannel = ctx.guild.get_channel(ctx.rroles_cfg.channel)
            if channel is None:
                raise InitializationInvalid('Reaction roles channel not found')
            message: discord.PartialMessage = channel.get_partial_message(ctx.rroles_cfg.message)
            try:
                await sess.refresh(ctx.rroles_cfg)
                ctx.rroles_cfg.roles.append(
                    ReactionRoles(
                        emoji=str(emoji),
                        role=role.id
                    )
                )
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

        async with self.bot.sql_session as sess:  # type: AsyncSession
            await sess.refresh(ctx.rroles_cfg)
            channel: discord.TextChannel = ctx.guild.get_channel(ctx.rroles_cfg.channel)
            if channel is None:
                raise InitializationInvalid('Reaction roles channel not found')
            message: discord.PartialMessage = channel.get_partial_message(ctx.rroles_cfg.message)
            if isinstance(emoji_or_role, discord.Role):
                kw = {'role': emoji_or_role.id}
            else:
                kw = {'emoji': str(emoji_or_role)}
            rrole: typing.Optional[ReactionRoles] = discord.utils.get(ctx.rroles_cfg.roles, **kw)
            if rrole is None:
                raise RoleOrEmojiNotFound(emoji_or_role)
            try:
                await message.remove_reaction(rrole.emoji, ctx.me)
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


def teardown(bot: PikalaxBOT):
    ReactionRoles.unlink()
    ReactionSchema.unlink()
