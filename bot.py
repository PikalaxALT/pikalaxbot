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

from utils.botclass import PikalaxBOT


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

    @bot.event
    async def on_command_error(ctx: commands.Context, exc: Exception):
        filter_excs = commands.CommandNotFound, commands.CheckFailure
        if not isinstance(exc, filter_excs):
            bot.log_tb(ctx, exc)
            lines = ''.join(traceback.format_tb(exc.__traceback__))
            await send_tb(lines)

    @bot.before_invoke
    async def before_invoke(ctx):
        if ctx.cog:
            ctx.cog.fetch()

    @bot.after_invoke
    async def after_invoke(ctx):
        if ctx.cog:
            await ctx.cog.commit()

    try:
        bot.run()
    finally:
        if not bot.reboot_after:
            os.system('systemctl stop pikalaxbot')


if __name__ == '__main__':
    main()
