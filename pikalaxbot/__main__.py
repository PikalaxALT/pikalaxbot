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

"""
This is a semiprivate bot intended to run on a small number of servers.
If you wish to use it for your own bot, please contact the owner via Discord
at PikalaxALT#5823.
"""

import discord
from discord.ext import commands
import argparse
import sys
import os
import glob
from collections.abc import Generator
import typing
import logging
from .utils.prefix import *

from . import __dirname__, __version__
from .bot import PikalaxBOT


def filter_extensions(bot: PikalaxBOT) -> Generator[tuple[str, str], typing.Any, None]:
    disabled_cogs = bot.settings.disabled_cogs
    if 'jishaku' not in disabled_cogs:
        yield 'jishaku', 'Jishaku'
    for cogfile in glob.glob(f'{__dirname__}/cogs/*.py'):
        if os.path.isfile(cogfile) and '__init__' not in cogfile:
            cogname = os.path.splitext(os.path.basename(cogfile))[0]
            if cogname not in disabled_cogs:
                extn = f'pikalaxbot.cogs.{cogname}'
                yield extn, cogname.title().replace('_', '')


def init_extensions(bot: PikalaxBOT):
    # Load cogs
    bot.log_info('Loading extensions')

    for extn, cogname in filter_extensions(bot):
        try:
            bot.load_extension(extn)
        except commands.ExtensionNotFound:
            bot.log_error('Unable to find extn "%s"', cogname)
        except commands.ExtensionFailed as e:
            e = e.original
            bot.log_error('Failed to load extn "%s"', cogname, exc_info=(e.__class__, e, e.__traceback__))
        else:
            bot.log_info(f'Loaded extn "{cogname}"')


class BotArgs(argparse.Namespace):
    settings: str
    logfile: str
    version: bool
    log_level: int


def main():
    parser = argparse.ArgumentParser(prog="pikalaxbot", description="A Discord bot. Yeah.",
                                     epilog="For more help, contact PikalaxALT#5823 on the discord.py server.")
    parser.add_argument('-s', '--settings', default='settings.json',
                        help="a JSON file denoting the bot's settings. "
                             "See README.md for details. "
                             "Defaults to %(default)s")
    parser.add_argument('-l', '--logfile', default='bot.log',
                        help="the file to which the logging module will output bot events. "
                             "This file will be overwritten. "
                             "Defaults to %(default)s")
    parser.add_argument('-v', '--version', action='store_true',
                        help="Prints the version string and exits.")
    parser.add_argument('-d', '--debug', action='store_const', dest='log_level',
                        const=logging.DEBUG, default=logging.INFO,
                        help="set debug log level")
    args = parser.parse_args(namespace=BotArgs())
    if args.version:
        print(f'{parser.prog} v{__version__}')
        return

    bot = PikalaxBOT(
        settings_file=args.settings,
        logfile=args.logfile,
        command_prefix=command_prefix,
        pokeapi_file='file:{}?mode=ro'.format(os.path.join(os.path.dirname(__dirname__), 'pokeapi', 'db.sqlite3')),
        case_insensitive=True,
        # d.py 1.5.0: Declare gateway intents
        intents=discord.Intents(
            members=True,
            messages=True,
            guilds=True,
            emojis=True,
            reactions=True,
            voice_states=True,
            presences=True
        ),
        log_level=args.log_level
    )
    init_extensions(bot)
    bot.run()
    return not bot.reboot_after


if __name__ == '__main__':
    sys.exit(main())
