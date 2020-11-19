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

import discord
from discord.ext import commands
import argparse
import sys
import os
import glob
import traceback

from . import PikalaxBOT, __dirname__, __version__


async def _command_prefix(bot, message):
    if message.guild is None:
        return ''
    if message.guild.id not in bot.guild_prefixes:
        async with bot.sql as sql:
            await sql.execute('insert or ignore into prefixes values (?, ?)', (message.guild.id, bot.settings.prefix))
            async with sql.execute('select prefix from prefixes where guild = ?', (message.guild.id,)) as cur:
                bot.guild_prefixes[message.guild.id], = await cur.fetchone()
    return bot.guild_prefixes[message.guild.id]


def filter_extensions(bot):
    disabled_cogs = bot.settings.disabled_cogs
    if 'jishaku' not in disabled_cogs:
        yield 'jishaku', 'Jishaku'
    for cogfile in glob.glob(f'{__dirname__}/cogs/*.py'):
        if os.path.isfile(cogfile) and '__init__' not in cogfile:
            cogname = os.path.splitext(os.path.basename(cogfile))[0]
            if cogname not in disabled_cogs:
                extn = f'pikalaxbot.cogs.{cogname}'
                yield extn, cogname.title().replace('_', '')
    if 'ext.pokeapi' not in disabled_cogs:
        yield 'pikalaxbot.ext.pokeapi', 'PokeAPI'


def init_extensions(bot):
    # Load cogs
    bot.log_info('Loading extensions')

    for extn, cogname in filter_extensions(bot):
        try:
            bot.load_extension(extn)
        except commands.ExtensionNotFound:
            bot.logger.error(f'Unable to find extn "{cogname}"')
        except commands.ExtensionFailed as e:
            bot.logger.warning(f'Failed to load extn "{cogname}"')
            for line in traceback.format_exception(e.__class__, e, e.__traceback__):
                bot.logger.warning(line)
        else:
            bot.log_info(f'Loaded extn "{cogname}"')


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
    parser.add_argument('--sqlfile', default=f'{__dirname__}/data/db.sql')
    parser.add_argument('--version', action='store_true')
    args = parser.parse_args()
    if args.version:
        print(f'{os.path.basename(os.path.dirname(__file__))} v{__version__}')
        return

    bot = PikalaxBOT(
        args.settings,
        args.logfile,
        args.sqlfile,
        command_prefix=_command_prefix,
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
        )
    )
    init_extensions(bot)
    bot.run()
    return not bot.reboot_after


if __name__ == '__main__':
    sys.exit(main())
