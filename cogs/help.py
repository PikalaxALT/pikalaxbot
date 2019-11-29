from discord.ext import commands


class MyHelpCommand(commands.DefaultHelpCommand):
    def get_command_signature(self, command):
        return '{0.clean_prefix}{1.qualified_name} {1.signature}'.format(self, command)

    async def on_help_command_error(self, ctx, error):
        await ctx.bot.owner.send(f'**{error.__class__.__name__}**: {error} {ctx.bot.command_error_emoji}')
        await ctx.send(f'An error has occurred. {ctx.bot.owner} has been notified.')


class Help(commands.Cog):
    def __init__(self, bot):
        self._original_help_command = bot.help_command
        self.bot = bot
        bot.help_command = MyHelpCommand(command_attrs={'name': bot.settings.help_name})
        # bot.help_command.cog = self

    def cog_unload(self):
        self.bot.help_command = self._original_help_command


def setup(bot):
    bot.add_cog(Help(bot))
