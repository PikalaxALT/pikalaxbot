import discord
from discord.ext import commands
from utils.default_cog import Cog


class SelfAssignableRole(Cog):
    roles = {}
    config_attrs = 'roles',

    @commands.command()
    @commands.bot_has_permissions(manage_roles=True)
    async def iam(self, ctx: commands.Context, *, role: discord.Role):
        """Assign a role to yourself"""
        if role.id not in self.roles.get(ctx.guild.id, []):
            await ctx.send(f'Role "{role}" is not self-assignable')
        elif role in ctx.author.roles:
            await ctx.send(f'You already have role "{role}"')
        else:
            await ctx.author.add_roles(role, reason='Requested by user')
            await ctx.send(f'You now have the role "{role}"')

    @commands.command()
    @commands.bot_has_permissions(manage_roles=True)
    async def iamnot(self, ctx: commands.Context, *, role: discord.Role):
        """Unassign a role from yourself"""
        if role.id not in self.roles.get(ctx.guild.id, []):
            await ctx.send(f'Role "{role}" is not self-assignable')
        elif role not in ctx.author.roles:
            await ctx.send(f'You don\'t have the role "{role}"')
        else:
            await ctx.author.remove_roles(role, reason='Requested by user')
            await ctx.send(f'You no longer have the role "{role}"')

    @commands.command()
    @commands.is_owner()
    async def addar(self, ctx: commands.Context, *, role: discord.Role):
        """Add a role to the list of self-assignable roles"""
        if ctx.guild.id not in self.roles:
            self.roles[ctx.guild.id] = [role.id]
        elif role.id in self.roles[ctx.guild.id]:
            return await ctx.send(f'Role "{role}" already self-assignable"')
        else:
            self.roles[ctx.guild.id].append(role.id)
        await ctx.send(f'Role "{role}" is now self-assignable')

    @commands.command()
    @commands.is_owner()
    async def rmar(self, ctx: commands.Context, *, role: discord.Role):
        """Remove a role from the list of self-assignable roles"""
        if ctx.guild.id not in self.roles:
            self.roles[ctx.guild.id] = []
        if role.id not in self.roles[ctx.guild.id]:
            return await ctx.send(f'Role "{role}" is self-assignable"')
        self.roles[ctx.guild.id].remove(role.id)
        await ctx.send(f'Role "{role}" is no longer self-assignable')

    @commands.command()
    async def lsar(self, ctx):
        """List self-assignable roles"""
        if ctx.guild.id not in self.roles:
            self.roles[ctx.guild.id] = []
        roles = ', '.join(str(discord.utils.get(ctx.guild.roles, id=role)) for role in self.roles[ctx.guild.id])
        await ctx.send(f'Self-assignable roles for {ctx.guild}:\n'
                       f'{roles if roles else None}')


def setup(bot):
    bot.add_cog(SelfAssignableRole(bot))
