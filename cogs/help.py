from discord.ext import commands

from cogs import BaseCog
from utils.paginator import HelpPaginator


class Help(BaseCog):
    def __init__(self, bot):
        super().__init__(bot)
        self.bot.command(**bot.help_attrs)(self._help)

    async def _help(self, ctx: commands.Context, *, command=None):
        """Shows help about a command or the bot"""

        try:
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
        except Exception as e:
            await ctx.send(e)


def setup(bot):
    bot.remove_command(bot.settings.help_name)
    bot.add_cog(Help(bot))


def teardown(bot):
    bot.command(**bot.help_attrs)(commands.bot._default_help_command)
