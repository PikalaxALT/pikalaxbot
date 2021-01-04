import discord
from discord.ext import commands
import sys
import difflib
from . import *


class ErrorHandling(BaseCog):
    """Error handling extension"""

    filter_excs = commands.CheckFailure, commands.MaxConcurrencyReached
    handle_excs = commands.UserInputError, commands.DisabledCommand, commands.CommandNotFound

    @BaseCog.listener()
    async def on_error(self, event: str, *args, **kwargs):
        exc_info = sys.exc_info()
        exc: BaseException = exc_info[1]
        await self.bot.wait_until_ready()
        embed = None
        if event == 'on_message':
            message: discord.Message
            message, = args
            embed = discord.Embed(
                colour=discord.Colour.red()
            ).add_field(
                name='Author',
                value=message.author.mention,
                inline=False
            ).add_field(
                name='Channel',
                value=message.channel.mention,
                inline=False
            ).add_field(
                name='Invoked with',
                value='`'
                      + (message.content if len(message.content) < 100 else message.content[:97] + '...')
                      + '`',
                inline=False
            ).add_field(
                name='Invoking message',
                value=message.jump_url,
                inline=False
            )
        await self.bot.send_tb(None, exc, origin=event, embed=embed)

    async def handle_command_error(self, ctx: MyContext, exc: commands.CommandError):
        if isinstance(exc, commands.MissingRequiredArgument):
            msg = f'`{exc.param}` is a required argument that is missing.'
        elif isinstance(exc, commands.TooManyArguments):
            msg = f'Too many arguments for `{ctx.command}`'
        elif isinstance(exc, (commands.BadArgument, commands.BadUnionArgument, commands.ArgumentParsingError)):
            msg = f'Got a bad argument for `{ctx.command}`: {exc}'
            await ctx.send_help(ctx.command)
        elif isinstance(exc, commands.DisabledCommand):
            msg = f'Command "{ctx.command}" is disabled.'
        elif isinstance(exc, commands.CommandNotFound):
            if not ctx.prefix:
                return
            if ctx.invoked_with.lower().startswith('fix') and self.bot.get_cog('Fix'):
                return
            q20_cog = self.bot.get_cog('Q20Game')
            if q20_cog and q20_cog[ctx.channel.id].running:
                return

            async def filter_commands(iterable):
                res = []
                for command in iterable:
                    try:
                        flag = await command.can_run(ctx)
                        if flag:
                            res.append(command.qualified_name)
                    except commands.CommandError:
                        pass
                return res

            matches = difflib.get_close_matches(
                ctx.invoked_with,
                await filter_commands(self.bot.walk_commands()),
                n=1,
                cutoff=0.5
            )
            if not matches:
                return
            msg = f'I don\'t have a command called `{ctx.invoked_with}`. Did you mean `{matches[0]}`?'
        else:
            msg = f'An unhandled error {exc} has occurred'
        await ctx.reply(f'{msg} {self.bot.command_error_emoji}', delete_after=10, mention_author=False)

    @BaseCog.listener()
    async def on_command_error(self, ctx: MyContext, exc: commands.CommandError):
        if isinstance(exc, commands.CommandInvokeError):
            exc = exc.original

        if isinstance(exc, self.filter_excs):
            return

        if ctx.cog and BaseCog._get_overridden_method(ctx.cog.cog_command_error) is not None:
            return

        if hasattr(ctx.command, 'on_error'):
            return

        if isinstance(exc, self.handle_excs):
            return await self.handle_command_error(ctx, exc)

        embed = discord.Embed(title='Command error details')
        embed.add_field(name='Author', value=ctx.author.mention, inline=False)
        if ctx.guild:
            embed.add_field(name='Channel', value=ctx.channel.mention, inline=False)
        embed.add_field(name='Invoked with', value='`' + ctx.message.content + '`', inline=False)
        embed.add_field(name='Invoking message', value=ctx.message.jump_url if ctx.guild else "is a dm", inline=False)
        await self.bot.send_tb(ctx, exc, origin=f'command {ctx.command}', embed=embed)


def setup(bot: PikalaxBOT):
    bot.add_cog(ErrorHandling(bot))
