# PikalaxBOT - A Discord bot in discord.py
# Copyright (C) 2018  PikalaxALT
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
from . import BaseCog
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
    roles = {}
    config_attrs = 'roles',

    def cog_check(self, ctx):
        if ctx.guild is None:
            raise commands.NoPrivateMessage('This command cannot be used in private messages.')
        return True

    @commands.command()
    @commands.bot_has_permissions(manage_roles=True)
    @commands.check(bot_role_is_higher)
    async def iam(self, ctx: commands.Context, *, role: AliasedRoleConverter):
        """Assign a role to yourself"""
        if role in ctx.author.roles:
            await ctx.send(f'You already have role "{role}"')
        else:
            self.bot.logger.debug(f'Adding role {role} to {ctx.author}')
            await ctx.author.add_roles(role, reason='Requested by user')
            await ctx.send(f'You now have the role "{role}"')

    @commands.command()
    @commands.bot_has_permissions(manage_roles=True)
    @commands.check(bot_role_is_higher)
    async def iamnot(self, ctx: commands.Context, *, role: AliasedRoleConverter):
        """Unassign a role from yourself"""
        if role not in ctx.author.roles:
            await ctx.send(f'You don\'t have the role "{role}"')
        else:
            self.bot.logger.debug(f'Removing role {role} from {ctx.author}')
            await ctx.author.remove_roles(role, reason='Requested by user')
            await ctx.send(f'You no longer have the role "{role}"')

    @iam.error
    @iamnot.error
    async def assign_roles_error(self, ctx: commands.Context, exc: BaseException):
        if isinstance(exc, (commands.BotMissingPermissions, commands.BadArgument, Hierarchy)):
            emoji = self.bot.command_error_emoji
            await ctx.send(f'**{exc.__class__.__name__}**: {exc} {emoji}', delete_after=10)
        self.log_tb(ctx, exc)

    @commands.command()
    @commands.is_owner()
    async def addar(self, ctx: commands.Context, alias: str.lower, *, role: discord.Role):
        """Add a role to the list of self-assignable roles"""
        if str(ctx.guild.id) not in self.roles:
            self.roles[str(ctx.guild.id)] = {alias: role.id}
        elif alias in self.roles[str(ctx.guild.id)]:
            return await ctx.send(f'Role "{role}" already self-assignable"')
        else:
            self.roles[str(ctx.guild.id)][alias] = role.id
        await ctx.send(f'Role "{role}" is now self-assignable')

    @commands.command()
    @commands.is_owner()
    async def rmar(self, ctx: commands.Context, alias: str.lower):
        """Remove a role from the list of self-assignable roles"""
        if str(ctx.guild.id) not in self.roles:
            self.roles[str(ctx.guild.id)] = {}
        if alias not in self.roles[str(ctx.guild.id)]:
            return await ctx.send(f'Role "{alias}" is self-assignable"')
        self.roles[str(ctx.guild.id)].pop(alias)
        await ctx.send(f'Role "{alias}" is no longer self-assignable')

    @commands.command()
    async def lsar(self, ctx):
        """List self-assignable roles"""
        if str(ctx.guild.id) not in self.roles:
            self.roles[str(ctx.guild.id)] = {}
        msg = f'Self-assignable roles for {ctx.guild}:\n'
        roles = self.roles.get(str(ctx.guild.id), {})
        if roles:
            for alias, role_id in roles.items():
                role = discord.utils.get(ctx.guild.roles, id=role_id)
                msg += f'    {alias}: {role}\n'
        else:
            msg += f'    None\n'
        await ctx.send(msg)

    @commands.command()
    @commands.is_owner()
    async def resetar(self, ctx):
        """Reset self-assignable roles"""
        self.roles = {}
        await ctx.message.add_reaction('☑')


def setup(bot):
    bot.add_cog(SelfAssignableRole(bot))
