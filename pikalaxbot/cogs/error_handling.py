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
from discord.ext import commands, menus
import sys
import difflib
from . import *
from ..constants import *
from ..context import FakeContext
import typing
import traceback


class ErrorHandling(BaseCog):
    """Error handling extension"""

    filter_excs = commands.CheckFailure, commands.MaxConcurrencyReached
    handle_excs = commands.UserInputError, commands.DisabledCommand, commands.CommandNotFound

    exc_channel = EXC_CHANNEL_ID
    config_attrs = 'exc_channel',

    async def send_tb(
            self,
            ctx: typing.Optional[MyContext],
            exc: BaseException,
            *,
            origin: typing.Optional[str] = None,
            embed: typing.Optional[discord.Embed] = None
    ):
        msg = f'Ignoring exception in {origin}' if origin is not None else ''
        self.log_error(msg, exc_info=(exc.__class__, exc, exc.__traceback__))
        channel = self.bot.get_channel(self.exc_channel)
        if channel is None:
            return
        if ctx is None:
            owner = await self.bot.get_owner()
            if isinstance(owner, set):
                owner = owner.pop()
            ctx = FakeContext(channel.guild, channel, None, owner, self.bot)
        elif embed is None:
            embed = ctx.prepare_command_error_embed()
        paginator = commands.Paginator()
        msg and paginator.add_line(msg)
        for line in traceback.format_exception(exc.__class__, exc, exc.__traceback__):
            paginator.add_line(line.rstrip('\n'))

        class TracebackPageSource(menus.ListPageSource):
            def format_page(self, menu: menus.MenuPages, page: str):
                return {'content': page, 'embed': embed}

        menu_ = menus.MenuPages(TracebackPageSource(paginator.pages, per_page=1))
        await menu_.start(ctx, channel=channel)

    @BaseCog.listener()
    async def on_error(self, event: str, *args, **kwargs):
        _, exc, _ = sys.exc_info()  # type: BaseException
        await self.bot.wait_until_ready()
        if event == 'on_message':
            ctx = await self.bot.get_context(*args)
            embed = ctx.prepare_command_error_embed()
        else:
            ctx = embed = None
        await self.send_tb(ctx, exc, origin=event, embed=embed)

    async def handle_command_error(self, ctx: MyContext, exc: commands.CommandError):
        if isinstance(exc, commands.MissingRequiredArgument):
            msg = f'`{exc.param}` is a required argument that is missing.'
        elif isinstance(exc, commands.TooManyArguments):
            msg = f'Too many arguments for `{ctx.command}`'
        elif isinstance(exc, (commands.BadArgument, commands.BadUnionArgument, commands.ArgumentParsingError)):
            msg = f'Got a bad argument for `{ctx.command}`: {exc}'
            await ctx.send_help(ctx.command)
            await self.send_tb(ctx, exc)
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
    async def on_command_error(self, ctx: MyContext, exc: commands.CommandError, *, suppress_on_local=True):
        if isinstance(exc, commands.CommandInvokeError):
            exc = exc.original

        if isinstance(exc, self.filter_excs):
            return

        if suppress_on_local and ctx.has_local_error_handler():
            return

        if isinstance(exc, self.handle_excs):
            return await self.handle_command_error(ctx, exc)

        embed = ctx.prepare_command_error_embed()
        await self.send_tb(ctx, exc, origin=f'command {ctx.command}', embed=embed)

    @BaseCog.listener()
    async def on_cog_db_init_error(self, cog: BaseCog, error: Exception):
        # await self.bot.wait_until_ready()
        # await self.send_tb(None, error, origin=f'db init for cog {cog.qualified_name}:')
        msg = f'Ignoring exception in db init for cog {cog.qualified_name}:'
        self.log_error(msg, exc_info=(error.__class__, error, error.__traceback__))


def setup(bot: PikalaxBOT):
    bot.add_cog(ErrorHandling(bot))
