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

"""
This is a semiprivate bot intended to run on a small number of servers.
If you wish to use it for your own bot, please contact the owner via Discord
at PikalaxALT#5823.
"""

import argparse
import discord
from discord.ext import commands
import traceback
import aiohttp
import sys
import os
from io import StringIO

from . import PikalaxBOT
from .utils.hastebin import mystbin
from .cogs.utils.errors import CogOperationError
from .cogs import BaseCog

__dir__ = os.path.dirname(__file__) or '.'
with open(os.path.join(os.path.dirname(__dir__), 'version.txt')) as fp:
    __version__ = fp.read().strip()


def main():
    """The main function that runs the bot.

    Syntax:
        python3.6 bot.py [--version] [--settings SETTINGSFILE] [--logfile LOGFILE] [--sqlfile SQLFILE]

    --version: Prints the version string and exits.
    --settings SETTINGSFILE: a JSON file denoting the bot's settings.  See README.md for details.  Defaults to settings.json
    --logfile LOGFILE: the file to which the logging module will output bot events.  This file will be overwritten.
        Defaults to bot.log
    --sqlfile SQLFILE: the database location. Defaults to data/db.sql
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('--settings', default='settings.json')
    parser.add_argument('--logfile', default='bot.log')
    parser.add_argument('--sqlfile', default='pikalaxbot/data/db.sql')
    parser.add_argument('--version', action='store_true')
    args = parser.parse_args()
    if args.version:
        with open('../version.txt') as fp:
            version = fp.read().rstrip()
        print(f'{os.path.basename(os.path.dirname(__file__))} v{version}')
        return

    bot = PikalaxBOT(args.settings, args.logfile, args.sqlfile)

    @bot.event
    async def on_ready():
        print(f'Logged in as {bot.user}')

    async def send_tb(tb, embed=None):
        channel = bot.exc_channel
        if channel is None:
            return
        if len(tb) < 1990:
            await channel.send(f'```{tb}```', embed=embed)
        else:
            try:
                url = await mystbin(tb)
            except aiohttp.ClientResponseError:
                await channel.send('An error has occurred', file=discord.File(StringIO(tb)), embed=embed)
            else:
                await channel.send(f'An error has occurred: {url}', embed=embed)

    @bot.event
    async def on_error(event, *args, **kwargs):
        s = traceback.format_exc()
        content = f'Ignoring exception in {event}\n{s}'
        print(content, file=sys.stderr)
        embed = None
        if event == 'on_message':
            message, = args
            embed = discord.Embed()
            embed.colour = discord.Colour.red()
            embed.add_field(name='Author', value=message.author.mention, inline=False)
            embed.add_field(name='Channel', value=message.channel.mention, inline=False)
            embed.add_field(name='Invoked with', value='`'
                            + (message.content if len(message.content) < 100 else message.content[:97] + '...')
                            + '`', inline=False)
            embed.add_field(name='Invoking message', value=message.jump_url, inline=False)
        await send_tb(content, embed=embed)

    async def handle_command_error(ctx: commands.Context, exc: PikalaxBOT.handle_excs):
        if isinstance(exc, commands.MissingRequiredArgument):
            msg = f'`{exc.param}` is a required argument that is missing.'
        elif isinstance(exc, commands.TooManyArguments):
            msg = f'Too many arguments for `{ctx.command}`'
        elif isinstance(exc, (commands.BadArgument, commands.BadUnionArgument, commands.ArgumentParsingError)):
            msg = f'Got a bad argument for `{ctx.command}`'
        elif isinstance(exc, CogOperationError):
            for cog, original in exc.cog_errors.items():
                if not original:
                    continue
                bot.log_tb(ctx, exc)
                orig = getattr(original, 'original', original)
                lines = ''.join(traceback.format_exception(orig.__class__, orig, orig.__traceback__))
                print(lines)
                lines = f'Ignoring exception in {exc.mode}ing {cog}:\n{lines}'
                await send_tb(lines)
            return
        elif isinstance(exc, commands.DisabledCommand):
            msg = f'Command "{ctx.command}" is disabled.'
        else:
            msg = f'An unhandled error {exc} has occurred'
        await ctx.send(f'{msg} {bot.command_error_emoji}', delete_after=10)

    @bot.event
    async def on_command_error(ctx: commands.Context, exc: Exception):
        if isinstance(exc, PikalaxBOT.filter_excs):
            return

        if isinstance(exc, PikalaxBOT.handle_excs):
            return await handle_command_error(ctx, exc)

        if ctx.cog and BaseCog._get_overridden_method(ctx.cog.cog_command_error) is not None:
            return

        bot.log_tb(ctx, exc)
        exc = getattr(exc, 'original', exc)
        lines = ''.join(traceback.format_exception(exc.__class__, exc, exc.__traceback__))
        print(lines)
        lines = f'Ignoring exception in command {ctx.command}:\n{lines}'
        embed = discord.Embed(title='Command error details')
        embed.add_field(name='Author', value=ctx.author.mention, inline=False)
        embed.add_field(name='Channel', value=ctx.channel.mention, inline=False)
        embed.add_field(name='Invoked with', value='`' + ctx.message.content + '`', inline=False)
        embed.add_field(name='Invoking message', value=ctx.message.jump_url, inline=False)
        await send_tb(lines, embed=embed)

    bot.run()
    return not bot.reboot_after


if __name__ == '__main__':
    sys.exit(main())
