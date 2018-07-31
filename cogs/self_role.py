import discord
from discord.ext import commands
from cogs import Cog


class Hierarchy(commands.CheckFailure):
    def __init__(self):
        super().__init__('Cannot run command due to hierarchy')


def bot_role_is_higher():
    def predicate(ctx):
        if ctx.author == ctx.guild.owner or ctx.guild.me.top_role <= ctx.author.top_role:
            raise Hierarchy
        return True

    return commands.check(predicate)


class AliasedRoleConverter(commands.Converter):
    async def convert(self, ctx, argument):
        role_id = ctx.cog.roles.get(str(ctx.guild.id), {}).get(argument.lower())
        if role_id is None:
            raise commands.BadArgument(f'No alias "{argument}" has been registered to a role')
        return discord.utils.get(ctx.guild.roles, id=role_id)


class SelfAssignableRole(Cog):
    roles = {}
    config_attrs = 'roles',

    def __local_check(self, ctx):
        if ctx.guild is None:
            raise commands.NoPrivateMessage('This command cannot be used in private messages.')
        return True

    @commands.command()
    @commands.bot_has_permissions(manage_roles=True)
    @bot_role_is_higher()
    async def iam(self, ctx: commands.Context, role: AliasedRoleConverter):
        """Assign a role to yourself"""
        if role in ctx.author.roles:
            await ctx.send(f'You already have role "{role}"')
        else:
            self.bot.logger.debug(f'Adding role {role} to {ctx.author}')
            await ctx.author.add_roles(role, reason='Requested by user')
            await ctx.send(f'You now have the role "{role}"')

    @commands.command()
    @commands.bot_has_permissions(manage_roles=True)
    @bot_role_is_higher()
    async def iamnot(self, ctx: commands.Context, role: AliasedRoleConverter):
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
        if isinstance(exc, (commands.BotMissingPermissions, commands.BadArgument)):
            emoji = self.bot.command_error_emoji
            await ctx.send(f'**{exc.__class__.__name__}**: {exc} {emoji}')

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
