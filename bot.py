import asyncio
import discord
import argparse
import glob
import logging
import os
import sys
from discord.client import log
from utils import sql
from utils.botclass import PikalaxBOT


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--logfile', default='bot.log')
    parser.add_argument('--debug', action='store_true')
    args = parser.parse_args()

    bot = PikalaxBOT(__file__)

    handler = logging.FileHandler(args.logfile, mode='w')
    fmt = logging.Formatter('%(asctime)s (PID:%(process)s) - %(levelname)s - %(message)s')
    handler.setFormatter(fmt)
    log.addHandler(handler)

    dname = os.path.dirname(__file__) or '.'
    for cogfile in glob.glob(f'{dname}/cogs/*.py'):
        if os.path.isfile(cogfile) and '__init__' not in cogfile:
            extn = f'cogs.{os.path.splitext(os.path.basename(cogfile))[0]}'
            if extn.split('.')[1] not in bot.disabled_cogs:
                try:
                    bot.load_extension(extn)
                except discord.ClientException:
                    log.warning(f'Failed to load cog "{extn}"')
                else:
                    log.info(f'Loaded cog "{extn}"')
            else:
                log.info(f'Skipping disabled cog "{extn}"')

    sql.db_init()

    log.info('Starting bot')
    bot.run()


if __name__ == '__main__':
    main()
