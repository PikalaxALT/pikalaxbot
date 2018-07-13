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


class PikalaxBOT(commands.Bot):
    __attr_mapping__ = {
        'token': '_token',
        'prefix': 'command_prefix',
        'owner': 'owner_id'
    }
    __type_mapping__ = {
        'banlist': set,
        'disabled_commands': set,
        'markov_channel': set
    }

    def __init__(self, args, *, loop=None):
        # Set up logger
        self.logger = logging.getLogger('discord')
        self.logger.setLevel(logging.DEBUG if args.debug else logging.INFO)
        handler = logging.FileHandler(args.logfile, mode='w')
        fmt = logging.Formatter('%(asctime)s (PID:%(process)s) - %(levelname)s - %(message)s')
        handler.setFormatter(fmt)
        self.logger.addHandler(handler)

        # Load settings
        loop = asyncio.get_event_loop() if loop is None else loop
        self._settings_file = args.settings
        with self.settings:
            help_name = self.settings.user.help_name
            command_prefix = self.settings.meta.prefix
            disabled_cogs = self.settings.user.disabled_cogs
        super().__init__(command_prefix, case_insensitive=True, help_attrs={'name': help_name}, loop=loop)

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

    @property
    def settings(self):
        return Settings(self._settings_file)

    def run(self):
        self.logger.info('Starting bot')
        with self.settings:
            token = self.settings.credentials.token
        super().run(token)

    async def close(self):
        await self.wall('Shutting down...')
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

    def log_and_print(self, level, msg):
        self.logger.log(level, msg)
        print(msg)

    def log_tb(self, ctx, exc):
        tb = traceback.format_exception(type(exc), exc, exc.__traceback__)
        self.log_and_print(logging.ERROR, f'Ignoring exception in command {ctx.command}:')
        self.log_and_print(logging.ERROR, ''.join(tb))
        return tb

    def cmd_error_check(self, ctx, exc):
        if isinstance(exc, commands.CommandNotFound) or isinstance(exc, commands.CheckFailure):
            return False

        # Inherit checks from super
        if self.extra_events.get('on_command_error', None):
            return False

        if hasattr(ctx.command, 'on_error'):
            return False

        cog = ctx.cog
        if cog:
            attr = '_{0.__class__.__name__}__error'.format(cog)
            if hasattr(cog, attr):
                return False

        return True

    async def on_command_error(self, ctx: commands.Context, exc):
        async def report(msg):
            with self.settings:
                debug = self.settings.user.debug
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

    async def wall(self, *args, **kwargs):
        for channel in self.get_all_channels():
            if isinstance(channel, discord.TextChannel) and  channel.permissions_for(channel.guild.me).send_messages:
                await channel.send(*args, *kwargs)

    async def on_ready(self):
        await self.wall('_is active and ready for abuse!_')
