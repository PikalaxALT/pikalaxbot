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
from .utils.config_io import Settings
from .utils.sql import connect
from .utils.logging_mixin import LoggingMixin

from .ext.twitch import *
from .version import version as __version__


__all__ = ('PikalaxBOT',)


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

    def __init__(self, settings_file, logfile, sqlfile, *, loop=None):
        # Load settings
        loop = asyncio.get_event_loop() if loop is None else loop
        self.settings = Settings(settings_file, loop=loop)
        disabled_cogs = self.settings.disabled_cogs
        super().__init__(_command_prefix, case_insensitive=True, loop=loop)
        self.guild_prefixes = {}
        self._sql = sqlfile

        # Set up logger
        self.logger.setLevel(logging.DEBUG if self.settings.debug else logging.INFO)
        handler = logging.FileHandler(logfile, mode='w')
        fmt = logging.Formatter('%(asctime)s (PID:%(process)s) - %(levelname)s - %(message)s')
        handler.setFormatter(fmt)
        self.logger.addHandler(handler)

        # Load cogs
        dname = os.path.dirname(__file__) or '.'
        for cogfile in glob.glob(f'{dname}/cogs/*.py'):
            if os.path.isfile(cogfile) and '__init__' not in cogfile:
                cogname = os.path.splitext(os.path.basename(cogfile))[0]
                if cogname not in disabled_cogs:
                    extn = f'pikalaxbot.cogs.{cogname}'
                    try:
                        self.load_extension(extn)
                    except commands.ExtensionNotFound:
                        self.logger.error(f'Unable to find extn "{cogname}"')
                    except discord.ClientException:
                        self.logger.warning(f'Failed to load extn "{cogname}"')
                    else:
                        self.logger.info(f'Loaded extn "{cogname}"')
                else:
                    self.logger.info(f'Skipping disabled extn "{cogname}"')

        async def init_sql():
            async with self.sql as sql:
                await sql.db_init(self)

        self.loop.create_task(init_sql())

        # Reboot handler
        self.reboot_after = True

        # Twitch bot
        self._twitch_bot = create_twitch_bot(self)

    async def tmi_dispatch(self, event, *args, **kwargs):
        if self._twitch_bot is not None:
            await self._twitch_bot._dispatch(event, *args, **kwargs)

    @property
    def sql(self):
        return connect(self._sql, loop=self.loop)

    def run(self):
        self.logger.info('Starting bot')
        token = self.settings.token
        super().run(token)

    async def logout(self):
        self.logger.info('Logout request received')
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
