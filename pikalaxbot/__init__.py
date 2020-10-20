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

import asyncio
import discord
from discord.ext import commands
import logging
import os
import glob
import traceback
from io import StringIO
import aiohttp
from .utils.hastebin import mystbin
from .utils.config_io import Settings
from .utils.sql import connect
from .utils.logging_mixin import LoggingMixin

from .cogs.utils.errors import *


__all__ = ('PikalaxBOT',)
__dir__ = os.path.dirname(__file__) or '.'


async def _command_prefix(bot, message):
    if message.guild is None:
        return ''
    if message.guild.id not in bot.guild_prefixes:
        async with bot.sql as sql:
            bot.guild_prefixes[message.guild.id] = await sql.get_prefix(bot, message)
    return bot.guild_prefixes[message.guild.id]


class PikalaxBOT(LoggingMixin, commands.Bot):
    filter_excs = commands.CommandNotFound, commands.CheckFailure, commands.MaxConcurrencyReached
    handle_excs = commands.UserInputError, CogOperationError, commands.DisabledCommand

    def __init__(self, settings_file, logfile, sqlfile, *, loop=None):
        # Load settings
        loop = loop or asyncio.get_event_loop()
        self.settings = Settings(settings_file, loop=loop)
        disabled_cogs = self.settings.disabled_cogs
        super().__init__(
            _command_prefix,
            case_insensitive=True,
            loop=loop,
            activity=discord.Game(self.settings.game),
            # d.py 1.5.0: Declare gateway intents
            intents=discord.Intents(
                members=True,
                messages=True,
                guilds=True,
                emojis=True,
                reactions=True,
                typing=True,
                voice_states=True,
                presences=True
            )
        )
        self.guild_prefixes = {}
        self._sql = sqlfile

        # Set up logger
        self.logger.setLevel(logging.DEBUG if self.settings.debug else logging.INFO)
        handler = logging.FileHandler(logfile, mode='w')
        fmt = logging.Formatter('%(asctime)s (PID:%(process)s) - %(levelname)s - %(message)s')
        handler.setFormatter(fmt)
        self.logger.addHandler(handler)

        async def init_client_session():
            self.client_session = aiohttp.ClientSession()

        self.log_info('Creating aiohttp session')
        self.client_session = None
        self.loop.run_until_complete(init_client_session())

        self.log_info('Loading pokeapi')
        self.pokeapi = None
        self.load_extension('pikalaxbot.ext.pokeapi')

        # Load cogs
        self.log_info('Loading extensions')
        if 'jishaku' not in disabled_cogs:
            try:
                self.load_extension('jishaku')
            except commands.ExtensionNotFound:
                self.logger.error('Unable to load "jishaku", maybe install it first?')
            except commands.ExtensionFailed as e:
                e = e.original
                self.logger.warning('Failed to load extn "jishaku" due to an error')
                for line in traceback.format_exception(e.__class__, e, e.__traceback__):
                    self.logger.warning(line)
            else:
                self.log_info('Loaded jishaku')

        for cogfile in glob.glob(f'{__dir__}/cogs/*.py'):
            if os.path.isfile(cogfile) and '__init__' not in cogfile:
                cogname = os.path.splitext(os.path.basename(cogfile))[0]
                if cogname not in disabled_cogs:
                    extn = f'pikalaxbot.cogs.{cogname}'
                    try:
                        self.load_extension(extn)
                    except commands.ExtensionNotFound:
                        self.logger.error(f'Unable to find extn "{cogname}"')
                    except commands.ExtensionFailed as e:
                        self.logger.warning(f'Failed to load extn "{cogname}"')
                        for line in traceback.format_exception(e.__class__, e, e.__traceback__):
                            self.logger.warning(line)
                    else:
                        self.log_info(f'Loaded extn "{cogname}"')
                else:
                    self.log_info(f'Skipping disabled extn "{cogname}"')

        # self.load_extension('pikalaxbot.ext.twitch')

        async def init_sql():
            self.log_info('Start init db')
            async with self.sql as sql:
                await sql.db_init(self)
            self.log_info('Finish init db')

        self.log_info('Init db')
        self.loop.run_until_complete(init_sql())
        self.log_info('DB init complete')

        # Reboot handler
        self.reboot_after = True

        # Twitch bot
        self._alive_since = None

    @property
    def sql(self):
        return connect(self._sql, loop=self.loop)

    async def send_tb(self, tb, embed=None):
        channel = self.exc_channel
        client_session = self.client_session
        if channel is None:
            return
        if len(tb) < 1990:
            await channel.send(f'```{tb}```', embed=embed)
        else:
            try:
                url = await mystbin(tb, cs=client_session)
            except aiohttp.ClientResponseError:
                await channel.send('An error has occurred', file=discord.File(StringIO(tb)), embed=embed)
            else:
                await channel.send(f'An error has occurred: {url}', embed=embed)

    def run(self):
        self.log_info('Starting bot')
        token = self.settings.token
        super().run(token)

    async def logout(self):
        self.log_info('Logout request received')
        await self.close()

    @property
    def exc_channel(self):
        try:
            return self.get_channel(self.settings.exc_channel)
        except AttributeError:
            return None

    @property
    def command_error_emoji(self):
        return discord.utils.get(self.emojis, name=self.settings.error_emoji)
