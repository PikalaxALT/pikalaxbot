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

import aiohttp
import asyncio
import discord
from discord.ext import commands
import logging
import os
import glob
import traceback
from utils.config_io import Settings
from utils.sql import connect


class LoggingMixin:
    def __init__(self, *args, **kwargs):
        # Set up logger
        self.logger = logging.getLogger('discord')
        super().__init__(*args, **kwargs)

    def log_and_print(self, level, msg, *args, **kwargs):
        self.logger.log(level, msg, *args, **kwargs)
        if level >= self.logger.level:
            print(msg % args)

    def log_info(self, msg, *args, **kwargs):
        self.log_and_print(logging.INFO, msg, *args, **kwargs)

    def log_debug(self, msg, *args, **kwargs):
        self.log_and_print(logging.DEBUG, msg, *args, **kwargs)

    def log_warning(self, msg, *args, **kwargs):
        self.log_and_print(logging.WARNING, msg, *args, **kwargs)

    def log_error(self, msg, *args, **kwargs):
        self.log_and_print(logging.ERROR, msg, *args, **kwargs)

    def log_critical(self, msg, *args, **kwargs):
        self.log_and_print(logging.CRITICAL, msg, *args, **kwargs)

    def log_tb(self, ctx, exc):
        self.log_and_print(
            logging.ERROR,
            f'Ignoring exception in command {ctx.command}:',
            exc_info=(exc.__class__, exc, exc.__traceback__)
        )


async def _command_prefix(bot, message):
    if message.guild is None:
        return ''
    if message.guild.id not in bot.guild_prefixes:
        async with bot.sql as sql:
            bot.guild_prefixes[message.guild.id] = await sql.get_prefix(bot, message)
    return bot.guild_prefixes[message.guild.id]


class PikalaxBOT(LoggingMixin, commands.Bot):
    filter_excs = commands.CommandNotFound, commands.CheckFailure
    handle_excs = commands.UserInputError,

    def __init__(self, settings_file, logfile, *, loop=None):
        # Load settings
        loop = asyncio.get_event_loop() if loop is None else loop
        self.settings = Settings(settings_file, loop=loop)
        disabled_cogs = self.settings.disabled_cogs
        super().__init__(_command_prefix, case_insensitive=True, loop=loop)
        self.guild_prefixes = {}

        # Set up logger
        self.logger.setLevel(logging.DEBUG if self.settings.debug else logging.INFO)
        handler = logging.FileHandler(logfile, mode='w')
        fmt = logging.Formatter('%(asctime)s (PID:%(process)s) - %(levelname)s - %(message)s')
        handler.setFormatter(fmt)
        self.logger.addHandler(handler)

        # Load cogs
        dname = os.path.dirname(__file__) or '.'
        for cogfile in glob.glob(f'{dname}/../cogs/*.py'):
            if os.path.isfile(cogfile) and '__init__' not in cogfile:
                extn = f'cogs.{os.path.splitext(os.path.basename(cogfile))[0]}'
                if extn.split('.')[1] not in disabled_cogs:
                    try:
                        self.load_extension(extn)
                    except discord.ClientException:
                        self.logger.warning(f'Failed to load cog "{extn}"')
                    else:
                        self.logger.info(f'Loaded cog "{extn}"')
                else:
                    self.logger.info(f'Skipping disabled cog "{extn}"')

        async def init_sql():
            async with self.sql as sql:
                await sql.db_init(self)

        self.loop.create_task(init_sql())

        # Create client session
        self.user_cs = None
        self.ensure_client_session()

        # Reboot handler
        self.reboot_after = True

    @property
    def sql(self):
        return connect('data/db.sql', loop=self.loop)

    def run(self):
        self.logger.info('Starting bot')
        token = self.settings.token or input('Bot OAUTH2 token: ')
        super().run(token)

    def ensure_client_session(self):
        if self.user_cs is None or self.user_cs.closed:
            self.user_cs = aiohttp.ClientSession(raise_for_status=True, loop=self.loop)

    async def logout(self):
        await self.user_cs.close()
        async with self.sql as sql:
            await sql.backup_db()
        await self.close()

    @property
    def owner(self):
        return self.get_user(self.owner_id)

    @property
    def exc_channel(self):
        try:
            return self.get_channel(self.settings.exc_channel)
        except AttributeError:
            return None

    @property
    def command_error_emoji(self):
        return discord.utils.get(self.emojis, name=self.settings.error_emoji)

    async def hastebin(self, content: str) -> str:
        """Upload the content to hastebin and return the url.

        :param content: str: Raw content to upload
        :return: str: URL to the uploaded content
        :raises aiohttp.ClientException: on failure to upload
        """
        self.ensure_client_session()
        async with self.user_cs.post('https://hastebin.com/documents', data=content.encode('utf-8')) as res:
            post = await res.json()
        uri = post['key']
        return f'https://hastebin.com/{uri}'
