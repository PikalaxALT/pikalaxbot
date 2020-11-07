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
import sys
import os

from . import PikalaxBOT
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
    bot.init_extensions()

    @bot.event
    async def on_ready():
        print(f'Logged in as {bot.user}')

    bot.run()
    return not bot.reboot_after


if __name__ == '__main__':
    sys.exit(main())
