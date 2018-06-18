import asyncio
import discord
import argparse
import glob
import logging
import re
import os
import sys
from discord.client import log
from utils import sql
from utils.botclass import PikalaxBOT


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--logfile', default='bot.log')
    parser.add_argument('--rollback', action='store_true')
    parser.add_argument('--debug', action='store_true')
    args = parser.parse_args()

    bot = PikalaxBOT(__file__)
    bot.rollback = args.rollback

    handler = logging.FileHandler(args.logfile, mode='a')
    fmt = logging.Formatter('%(asctime)s (PID:%(process)s) - %(levelname)s - %(message)s')
    handler.setFormatter(fmt)
    log.addHandler(handler)
    log.setLevel(logging.DEBUG if args.debug else logging.INFO)

    help_bak = bot.remove_command('help')
    help_bak.name = 'pikahelp'
    bot.add_command(help_bak)

    dname = os.path.dirname(__file__) or '.'
    for cogfile in glob.glob(f'{dname}/cogs/*.py'):
        if os.path.isfile(cogfile) and '__init__' not in cogfile:
            extn = re.sub(r'.*/cogs/(\w+).py', 'cogs.\\1', cogfile)
            try:
                bot.load_extension(extn)
            except discord.ClientException:
                log.warning(f'Failed to load cog "{extn}"')
            else:
                log.info(f'Loaded cog "{extn}"')

    sql.db_init()

    log.info('Starting bot')
    bot.run()


if __name__ == '__main__':
    main()
