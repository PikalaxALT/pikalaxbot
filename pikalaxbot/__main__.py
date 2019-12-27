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


def main():
    """The main function that runs the bot.

    Syntax:
        python3.6 bot.py [--settings SETTINGSFILE] [--logfile LOGFILE]

    --settings SETTINGSFILE: a JSON file denoting the bot's settings.  See README.md for details.  Defaults to settings.json
    --logfile LOGFILE: the file to which the logging module will output bot events.  This file will be overwritten.
        Defaults to bot.log
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('--settings', default='settings.json')
    parser.add_argument('--logfile', default='bot.log')
    args = parser.parse_args()

    bot = PikalaxBOT(args.settings, args.logfile)

    @bot.event
    async def on_ready():
        print(f'Logged in as {bot.user}')

    async def send_tb(tb):
        channel = bot.exc_channel
        if channel is None:
            return
        if len(tb) < 1990:
            await channel.send(f'```{tb}```')
        else:
            try:
                url = await bot.hastebin(tb)
            except aiohttp.ClientResponseError:
                await channel.send('An error has occurred', file=discord.File(StringIO(tb)))
            else:
                await channel.send(f'An error has occurred: {url}')

    @bot.event
    async def on_error(event, *args, **kwargs):
        s = traceback.format_exc()
        content = f'Ignoring exception in {event}\n{s}'
        print(content, file=sys.stderr)
        await send_tb(content)

    async def handle_command_error(ctx: commands.Context, exc: PikalaxBOT.handle_excs):
        if isinstance(exc, commands.MissingRequiredArgument):
            msg = f'`{exc.param}` is a required argument that is missing.'
        elif isinstance(exc, commands.TooManyArguments):
            msg = f'Too many arguments for `{ctx.command}`'
        elif isinstance(exc, (commands.BadArgument, commands.BadUnionArgument, commands.ArgumentParsingError)):
            msg = f'Got a bad argument for `{ctx.command}`'
        else:
            msg = f'An unhandled error {exc} has occurred'
        await ctx.send(f'{msg} {bot.command_error_emoji}', delete_after=10)

    @bot.event
    async def on_command_error(ctx: commands.Context, exc: Exception):
        if isinstance(exc, PikalaxBOT.filter_excs):
            return

        if isinstance(exc, PikalaxBOT.handle_excs):
            return await handle_command_error(ctx, exc)

        bot.log_tb(ctx, exc)
        exc = getattr(exc, 'original', exc)
        lines = ''.join(traceback.format_exception(exc.__class__, exc, exc.__traceback__))
        print(lines)
        lines = f'Ignoring exception in command {ctx.command}:\n{lines}'
        await send_tb(lines)

    try:
        bot.run()
    finally:
        if not bot.reboot_after:
            os.system('systemctl stop pikalaxbot')


if __name__ == '__main__':
    main()
