from discord.ext import commands

from cogs import BaseCog
from utils.paginator import HelpPaginator


class Help(BaseCog):
    def __init__(self, bot):
        super().__init__(bot)
        self.help_cmd = commands.command(**bot.help_attrs)(self._help)
        self.help_cmd.error(self.help_error)

    async def _help(self, ctx: commands.Context, *, command=None):
        """Shows help about a command or the bot"""
        print('User invoked the help command owo')

        if command is None:
            p = await HelpPaginator.from_bot(ctx)
        else:
            entity = self.bot.get_cog(command) or self.bot.get_command(command)

            if entity is None:
                clean = command.replace('@', '@\u200b')
                return await ctx.send(f'Command or category "{clean}" not found.')
            elif isinstance(entity, commands.Command):
                p = await HelpPaginator.from_command(ctx, entity)
            else:
                p = await HelpPaginator.from_cog(ctx, entity)

        await p.paginate()

    async def help_error(self, ctx, exc):
        self.log_tb(ctx, exc)
        if hasattr(exc, 'orig'):
            exc = exc.orig
        await ctx.send(exc)


def setup(bot):
    help_name = bot.help_attrs['name']
    bot.remove_command(help_name)
    bot.add_cog(Help(bot))


def teardown(bot):
    bot.command(**bot.help_attrs)(commands.bot._default_help_command)
