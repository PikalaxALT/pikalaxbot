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
import asyncpg
from . import *

from sqlalchemy import Column, UniqueConstraint, BIGINT, VARCHAR, select, delete
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import DBAPIError


class SelfRole(BaseTable):
    guild_id = Column(BIGINT, primary_key=True)
    role_id = Column(BIGINT, primary_key=True)
    alias = Column(VARCHAR(32))

    __table_args__ = (UniqueConstraint(guild_id, role_id),)

    @classmethod
    async def convert(cls, ctx: MyContext, argument: str):
        statement = select(cls.role_id).where(
            cls.guild_id == ctx.guild.id,
            cls.alias == argument
        )
        async with ctx.bot.sql as sql:  # type: AsyncConnection
            role_id = await sql.scalar(statement)
        if role_id is None:
            raise commands.RoleNotFound(f'No alias "{argument}" has been registered to a role')
        role: discord.Role = ctx.guild.get_role(role_id)
        if role is None:
            raise commands.RoleNotFound('Role aliased to "{argument}" does not exist')
        return role

    @classmethod
    async def add(cls, conn: AsyncConnection, alias: str, role: discord.Role):
        statement = insert(cls).values(
            guild_id=role.guild.id,
            role_id=role.id,
            alias=alias
        )
        await conn.execute(statement)

    @classmethod
    async def delete(cls, conn: AsyncConnection, guild: discord.Guild, alias: str):
        statement = delete(cls).where(
            cls.guild_id == guild.id,
            cls.alias == alias
        )
        return await conn.scalar(statement)

    @classmethod
    async def fetchall(cls, conn: AsyncConnection, guild: discord.Guild):
        statement = select([cls.role_id, cls.alias]).where(cls.guild_id == guild.id)
        result = await conn.execute(statement)
        return result.all()

    @classmethod
    async def purge(cls, conn: AsyncConnection, guild: discord.Guild, all_=False):
        statement = delete(cls).where(all_ or (cls.guild_id == guild.id))
        await conn.execute(statement)


class Hierarchy(commands.CheckFailure):
    pass


def bot_role_is_higher(ctx):
    if ctx.author == ctx.guild.owner:
        raise Hierarchy('Cannot manage roles of the guild owner')
    if ctx.me.top_role <= ctx.author.top_role:
        raise Hierarchy('Your top role is above mine in the hierarchy')
    print('\N{WHITE HEAVY CHECK MARK}')
    return True


class SelfAssignableRole(BaseCog, name='SelfRole'):
    """Commands for roles that can be self-assigned using commands."""

    def cog_check(self, ctx):
        return commands.guild_only().predicate(ctx)

    async def init_db(self, sql):
        await SelfRole.create(sql)

    @commands.command()
    @commands.bot_has_permissions(manage_roles=True)
    @commands.check(bot_role_is_higher)
    async def iam(self, ctx: MyContext, *, role: SelfRole):
        """Assign a role to yourself"""
        if role in ctx.author.roles:
            await ctx.send(f'You already have role "{role}"')
        else:
            self.log_debug('Adding role %s to %s', role, ctx.author)
            await ctx.author.add_roles(role, reason='Requested by user')
            await ctx.send(f'You now have the role "{role}"')

    @commands.command()
    @commands.bot_has_permissions(manage_roles=True)
    @commands.check(bot_role_is_higher)
    async def iamnot(self, ctx: MyContext, *, role: SelfRole):
        """Unassign a role from yourself"""
        if role not in ctx.author.roles:
            await ctx.send(f'You don\'t have the role "{role}"')
        else:
            self.log_debug('Removing role %s from %s', role, ctx.author)
            await ctx.author.remove_roles(role, reason='Requested by user')
            await ctx.send(f'You no longer have the role "{role}"')

    @iam.error
    @iamnot.error
    async def assign_roles_error(self, ctx: MyContext, exc: commands.CommandError):
        if isinstance(exc, (commands.BotMissingPermissions, commands.BadArgument, Hierarchy)):
            emoji = self.bot.command_error_emoji
            await ctx.send(f'**{exc.__class__.__name__}**: {exc} {emoji}', delete_after=10)
        self.log_tb(ctx, exc)

    @commands.command()
    @commands.is_owner()
    async def addar(self, ctx: MyContext, alias: str.lower, *, role: discord.Role):
        """Add a role to the list of self-assignable roles"""
        try:
            async with self.bot.sql as sql:
                await SelfRole.add(sql, alias, role)
        except DBAPIError as e:
            orig = e.orig
            if isinstance(orig, asyncpg.UniqueViolationError):
                await ctx.send(f'Role "{role}" already self-assignable"')
            elif isinstance(orig, asyncpg.DatatypeMismatchError):
                await ctx.send(f'Alias string too long, try something shorter')
            else:
                raise orig from None
        else:
            await ctx.send(f'Role "{role}" is now self-assignable')

    @commands.command()
    @commands.is_owner()
    async def rmar(self, ctx: MyContext, alias: str.lower):
        """Remove a role from the list of self-assignable roles"""
        async with self.bot.sql as sql:
            num = await SelfRole.delete(sql, ctx.guild, alias)
        if num == 0:
            await ctx.send(f'Role "{alias}" is not self-assignable"')
        else:
            await ctx.send(f'Role "{alias}" is no longer self-assignable')

    @commands.command()
    async def lsar(self, ctx: MyContext):
        """List self-assignable roles"""
        async with self.bot.sql as sql:
            role_fmts = [
                f'    {alias}: {ctx.guild.get_role(role_id)}'
                for role_id, alias in await SelfRole.fetchall(sql, ctx.guild)
            ]
        msg = '\n'.join([f'Self-assignable roles for {ctx.guild}:'] + (role_fmts or ['    None']))
        await ctx.send(msg)

    @commands.command()
    @commands.is_owner()
    async def resetar(self, ctx: MyContext, all_=False):
        """Reset self-assignable roles"""
        async with self.bot.sql as sql:
            await SelfRole.purge(sql, ctx.guild, all_=all_)
        await ctx.message.add_reaction('☑')


def setup(bot: PikalaxBOT):
    bot.add_cog(SelfAssignableRole(bot))


def teardown(bot: PikalaxBOT):
    SelfRole.unlink()
