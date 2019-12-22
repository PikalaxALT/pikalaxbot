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

    @bot.before_invoke
    async def before_invoke(ctx):
        if ctx.cog:
            ctx.cog.fetch()

    @bot.after_invoke
    async def after_invoke(ctx):
        if ctx.cog:
            await ctx.cog.commit()

    bot.run()


if __name__ == '__main__':
    main()
