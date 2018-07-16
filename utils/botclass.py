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
from utils.config_io import Settings
from utils.sql import Sql


class LoggingMixin:
    def __init__(self, *args, **kwargs):
        # Set up logger
        self.logger = logging.getLogger('discord')
        super().__init__(*args, **kwargs)

    def log_and_print(self, level, msg, *args):
        self.logger.log(level, msg, *args)
        if level >= self.logger.level:
            print(msg % args)

    def log_info(self, msg, *args):
        self.log_and_print(logging.INFO, msg, *args)

    def log_debug(self, msg, *args):
        self.log_and_print(logging.DEBUG, msg, *args)

    def log_warning(self, msg, *args):
        self.log_and_print(logging.WARNING, msg, *args)

    def log_error(self, msg, *args):
        self.log_and_print(logging.ERROR, msg, *args)

    def log_critical(self, msg, *args):
        self.log_and_print(logging.CRITICAL, msg, *args)

    def log_tb(self, ctx, exc):
        tb = traceback.format_exception(type(exc), exc, exc.__traceback__)
        self.log_and_print(logging.ERROR, f'Ignoring exception in command {ctx.command}:')
        self.log_and_print(logging.ERROR, ''.join(tb))
        return tb


def _command_prefix(bot, message):
    if isinstance(message.channel, discord.DMChannel):
        return ''
    return bot.settings.prefix


class PikalaxBOT(LoggingMixin, commands.AutoShardedBot):
    def __init__(self, settings_file, logfile, *, loop=None):
        # Load settings
        loop = asyncio.get_event_loop() if loop is None else loop
        self.settings = Settings(settings_file)
        help_name = self.settings.help_name
        disabled_cogs = self.settings.disabled_cogs
        super().__init__(_command_prefix, case_insensitive=True, help_attrs={'name': help_name}, loop=loop)

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

        # Set up sql database
        self.sql = Sql()
        with self.sql:
            self.sql.db_init()

    def run(self):
        self.logger.info('Starting bot')
        token = self.settings.token
        super().run(token)

    async def close(self):
        await super().close()
        with self.sql:
            self.sql.backup_db()

    @staticmethod
    def find_emoji_in_guild(guild, *names, default=None):
        if guild is None:
            return default
        return discord.utils.find(lambda e: e.name in names, guild.emojis) or default

    def command_error_emoji(self, guild):
        return self.find_emoji_in_guild(guild, 'tppBurrito', 'VeggieBurrito', default='❤')

    def cmd_error_check(self, ctx, exc):
        if isinstance(exc, commands.CommandNotFound) or isinstance(exc, commands.CheckFailure):
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
            attr = f'_{cog.__class__.__name__}__error'
            if hasattr(cog, attr):
                self.log_and_print(logging.DEBUG, f'{cog.__class__.__name__} has __error')
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

        emoji = self.command_error_emoji(ctx.guild)
        if isinstance(exc, commands.NotOwner) and ctx.command.name != 'pikahelp':
            await report('Permission denied')
        elif isinstance(exc, commands.MissingPermissions):
            await report(f'You are missing permissions: {", ".join(exc.missing_perms)}')
        elif isinstance(exc, commands.BotMissingPermissions):
            await report(f'I am missing permissions: {", ".join(exc.missing_perms)}')
        elif exc is NotImplemented:
            await report('The command or one of its dependencies is not fully implemented')
        elif isinstance(exc, commands.UserInputError):
            await report(f'**{type(exc).__name__}**: {exc}')
        else:
            self.log_tb(ctx, exc)

    async def _before_invoke(self, ctx):
        ctx.cog.fetch()
        if self.settings.debug:
            owner = self.get_user(self.owner_id)
            await owner.send(f'before_invoke: {ctx.cog.__class__.__name__}.{ctx.command}')

    async def _after_invoke(self, ctx):
        ctx.cog.commit()
        if self.settings.debug:
            owner = self.get_user(self.owner_id)
            await owner.send(f'after_invoke: {ctx.cog.__class__.__name__}.{ctx.command}')
