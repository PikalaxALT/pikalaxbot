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


def _command_prefix(bot, message):
    if message.guild is None:
        return ''
    return bot.settings.prefix


class PikalaxBOT(LoggingMixin, commands.Bot):
    def __init__(self, settings_file, logfile, *, loop=None):
        # Load settings
        loop = asyncio.get_event_loop() if loop is None else loop
        self.settings = Settings(settings_file, loop=loop)
        help_name = self.settings.help_name
        _help = commands.HelpCommand(command_attrs={'name': help_name})
        disabled_cogs = self.settings.disabled_cogs
        super().__init__(_command_prefix, case_insensitive=True, help_command=_help, loop=loop)

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
                await sql.db_init()

        self.loop.create_task(init_sql())

        # Create client session
        self.user_cs = None
        self.ensure_client_session()

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
        await self.close()
        async with self.sql as sql:
            await sql.backup_db()

    @property
    def owner(self):
        return self.get_user(self.owner_id)

    @property
    def command_error_emoji(self):
        return discord.utils.get(self.emojis, name=self.settings.error_emoji)

    def cmd_error_check(self, ctx, exc):
        if isinstance(exc, commands.CommandNotFound):
            return False

        # Inherit checks from super
        if self.extra_events.get('on_command_error', None):
            self.log_and_print(logging.DEBUG, 'on_command_error in extra_events')
            return False

        if hasattr(ctx.command, 'on_error'):
            self.log_and_print(logging.DEBUG, f'{ctx.command} has on_error')
            return False

        cog = ctx.cog
        if cog:
            attr = f'cog_command_error'
            if hasattr(cog, attr):
                self.log_and_print(logging.DEBUG, f'{cog.__class__.__name__} has cog_command_error')
                return False

        return True

    async def on_command_error(self, ctx: commands.Context, exc):
        async def report(msg):
            debug = self.settings.debug
            await ctx.send(f'{ctx.author.mention}: {msg} {emoji}', delete_after=None if debug else 10)
            if debug:
                self.log_tb(ctx, exc)

        if not self.cmd_error_check(ctx, exc):
            return

        emoji = self.command_error_emoji
        if isinstance(exc, commands.NotOwner) and ctx.command.name != 'pikahelp':
            await report('You are not in the sudoers file. This incident will be reported')
        elif isinstance(exc, commands.MissingPermissions):
            await report(f'You are missing permissions: {", ".join(exc.missing_perms)}')
        elif isinstance(exc, commands.BotMissingPermissions):
            await report(f'I am missing permissions: {", ".join(exc.missing_perms)}')
        elif exc is NotImplemented:
            await report('The command or one of its dependencies is not fully implemented')
        elif isinstance(exc, commands.UserInputError):
            await report(f'**{type(exc).__name__}**: {exc}')
        elif isinstance(exc, commands.CheckFailure):
            return
        else:
            self.log_tb(ctx, exc)
