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
    parser.add_argument('--settings', default='settings.json')
    parser.add_argument('--logfile', default='bot.log')
    parser.add_argument('--debug', action='store_true')
    args = parser.parse_args()

    bot = PikalaxBOT(args)

    log.info('Starting bot')
    bot.run()


if __name__ == '__main__':
    main()
