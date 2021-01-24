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
from .utils.converters import AliasedRoleConverter


class Hierarchy(commands.CheckFailure):
    pass


def bot_role_is_higher(ctx):
    if ctx.author == ctx.guild.owner:
        raise Hierarchy('Cannot manage roles of the guild owner')
    if ctx.me.top_role <= ctx.author.top_role:
        raise Hierarchy('Your top role is above mine in the hierarchy')
    print('\N{WHITE HEAVY CHECK MARK}')
    return True


class SelfAssignableRole(BaseCog):
    """Commands for roles that can be self-assigned using commands."""

    def cog_check(self, ctx):
        return commands.guild_only().predicate(ctx)

    async def init_db(self, sql):
        await sql.execute(
            'create table if not exists self_role ('
            'guild_id bigint not null, '
            'role_id bigint not null, '
            'alias varchar(32), '
            'unique (guild_id, role_id)'
            ')'
        )

    @commands.command()
    @commands.bot_has_permissions(manage_roles=True)
    @commands.check(bot_role_is_higher)
    async def iam(self, ctx: MyContext, *, role: AliasedRoleConverter):
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
    async def iamnot(self, ctx: MyContext, *, role: AliasedRoleConverter):
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
            async with self.bot.sql as sql:  # type: asyncpg.Connection
                await sql.execute('insert into self_role values ($1, $2, $3)', ctx.guild.id, role.id, alias)
        except asyncpg.UniqueViolationError:
            await ctx.send(f'Role "{role}" already self-assignable"')
        except asyncpg.DatatypeMismatchError:
            await ctx.send(f'Alias string too long, try something shorter')
        else:
            await ctx.send(f'Role "{role}" is now self-assignable')

    @commands.command()
    @commands.is_owner()
    async def rmar(self, ctx: MyContext, alias: str.lower):
        """Remove a role from the list of self-assignable roles"""
        async with self.bot.sql as sql:  # type: asyncpg.Connection
            status = await sql.execute(
                'delete from self_role '
                'where guild_id = $1 '
                'and alias = $2',
                ctx.guild.id,
                alias
            )
        if status == 'DELETE 0':
            await ctx.send(f'Role "{alias}" is not self-assignable"')
        else:
            await ctx.send(f'Role "{alias}" is no longer self-assignable')

    @commands.command()
    async def lsar(self, ctx: MyContext):
        """List self-assignable roles"""
        async with self.bot.sql as sql:  # type: asyncpg.Connection
            role_fmts = [
                f'    {alias}: {ctx.guild.get_role(role_id)}'
                for role_id, alias in await sql.fetch(
                    'select role_id, alias '
                    'from self_role '
                    'where guild_id = $1',
                    ctx.guild.id
                )
            ]
        msg = '\n'.join([f'Self-assignable roles for {ctx.guild}:'] + (role_fmts or ['    None']))
        await ctx.send(msg)

    @commands.command()
    @commands.is_owner()
    async def resetar(self, ctx: MyContext, _all=False):
        """Reset self-assignable roles"""
        async with self.bot.sql as sql:  # type: asyncpg.Connection
            await sql.execute(
                'delete from self_role '
                'where case '
                'when $2 then true '
                'else guild_id = $1 '
                'end',
                ctx.guild.id,
                _all
            )
        await ctx.message.add_reaction('☑')


def setup(bot: PikalaxBOT):
    bot.add_cog(SelfAssignableRole(bot))
