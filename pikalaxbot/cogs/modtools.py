# PikalaxBOT - A Discord bot in discord.py
# Copyright (C) 2018-2021  PikalaxALT
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
import traceback
import logging
import typing
import aioitertools
import sys
import time
import operator
from discord.ext import commands, menus
from . import *
from .utils.converters import CommandConverter
from .utils.errors import CogOperationError
from .utils.menus import NavMenuPages
from ..utils.prefix import set_guild_prefix, Prefixes

from sqlalchemy import text
from sqlalchemy.exc import StatementError, ResourceClosedError


class SqlResponseMenu(NavMenuPages):
    _cumsums: list[int]
    sql_cmd: str
    _exec_time: float


class SqlResponseEmbed(menus.ListPageSource):
    def format_page(self, menu: SqlResponseMenu, page):
        first = 1 if menu.current_page == 0 else menu._cumsums[menu.current_page - 1] + 1
        last = menu._cumsums[menu.current_page]
        return discord.Embed(
            title=menu.sql_cmd,
            description=page,
            colour=0xf47fff
        ).set_footer(
            text=f'Rows {first}-{last} of {menu._cumsums[-1]}\n'
                 f'Page {menu.current_page + 1}/{self.get_max_pages()}\n'
                 f'Query completed in {menu._exec_time * 1000:.3f}ms'
        )


class clean_lower(str):
    @classmethod
    async def convert(cls, ctx, argument):
        arg = await commands.clean_content().convert(ctx, argument)
        return arg.lower()


def filter_history(channel: discord.TextChannel, **kwargs) -> typing.Coroutine[typing.Any, None, list[discord.Message]]:
    check = kwargs.pop('check', lambda m: True)
    limit = kwargs.pop('limit', sys.maxsize)
    return aioitertools.list(aioitertools.map(
        operator.itemgetter(1),
        aioitertools.zip(range(limit), channel.history(limit=None, **kwargs).filter(check))
    ))


class Modtools(BaseCog):
    """Commands for the bot owner to use"""

    prefix = 'p!'
    game = 'p!help'
    disabled_commands: set[str] = set()
    disabled_cogs: set[str] = set()
    debug = False
    config_attrs = 'prefix', 'game', 'disabled_commands', 'disabled_cogs', 'debug'

    def __init__(self, bot):
        super().__init__(bot)
        for name in list(self.disabled_commands):
            cmd = self.bot.get_command(name)
            if cmd:
                cmd.enabled = False
            else:
                self.disabled_commands.discard(name)

    async def init_db(self, sql):
        await Prefixes.create(sql)

    def cog_unload(self):
        for name in list(self.disabled_commands):
            cmd: typing.Optional[commands.Command] = self.bot.get_command(name)
            if cmd:
                cmd.enabled = True
            else:
                self.disabled_commands.discard(name)

    async def cog_check(self, ctx: MyContext):
        if not await self.bot.is_owner(ctx.author):
            raise commands.NotOwner('You do not own this bot')
        return True

    @commands.group(case_insensitive=True)
    async def admin(self, ctx: MyContext):
        """Commands for the admin console"""

    @admin.group(case_insensitive=True)
    async def ui(self, ctx: MyContext):
        """Commands to manage the bot's appearance"""

    @ui.command(name='nick')
    @commands.bot_has_permissions(change_nickname=True)
    async def change_nick(self, ctx: MyContext, *, nickname: commands.clean_content = None):
        """Change or reset the bot's nickname"""

        await ctx.me.edit(nick=nickname)
        await ctx.send('OwO')

    @ui.command(name='game')
    async def change_game(self, ctx: MyContext, *, game: str = None):
        """Change or reset the bot's presence"""

        game = game or f'{ctx.prefix}help'
        activity = discord.Game(game)
        await self.bot.change_presence(activity=activity)
        self.game = game
        await ctx.send(f'I\'m now playing {game}')

    @ui.command(name='avatar')
    @commands.check(lambda ctx: len(ctx.message.attachments) == 1)
    async def change_avatar(self, ctx: MyContext):
        """Change avatar"""
        await self.bot.user.edit(avatar=await ctx.message.attachments[0].read())
        await ctx.send('OwO')

    @admin.group()
    async def leaderboard(self, ctx: MyContext):
        """Commands for manipulating the leaderboard"""

    @admin.command(name='sql')
    async def call_sql(self, ctx: MyContext, *, script: str):
        """Run arbitrary sql command"""

        pag = commands.Paginator(max_size=2048)
        header: typing.Optional[str] = None
        counts = []
        async with ctx.typing(), self.bot.sql as sql:
            sql_start = time.perf_counter()
            try:
                async for i, row in aioitertools.enumerate(await sql.stream(text(script)), 1):
                    if header is None:
                        header = '|'.join(row.keys())
                        pag.add_line(header)
                        pag.add_line('-' * len(header))
                    to_add = '|'.join(map(str, row))
                    if len(header) * 2 + len(to_add) > 2040:
                        raise ValueError('At least one page of results is too long to fit. '
                                         'Try returning fewer columns?')
                    if pag._count + len(to_add) + 1 > 2045 or len(pag._current_page) >= 21:
                        counts.append(i - 1)
                        pag.close_page()
                        pag.add_line(header)
                        pag.add_line('-' * len(header))
                    pag.add_line(to_add)
            except ResourceClosedError:
                pass
            sql_end = time.perf_counter()

        if pag and pag.pages:
            counts.append(i)
            menu = SqlResponseMenu(
                SqlResponseEmbed(pag.pages, per_page=1),
                delete_message_after=True,
                clear_reactions_after=True
            )
            menu.sql_cmd = script
            menu._cumsums = counts
            menu._exec_time = sql_end - sql_start
            await menu.start(ctx)
        else:
            await ctx.send(f'Operation completed, no rows returned.\n'
                           f'Query completed in {(sql_end - sql_start) * 1000:.3f}ms', delete_after=10)
        await ctx.message.add_reaction('\N{white heavy check mark}')

    @commands.command(name='sql')
    async def top_call_sql(self, ctx: MyContext, *, script: str):
        """Run arbitrary sql command"""

        await self.call_sql(ctx, script=script)

    @call_sql.error
    @top_call_sql.error
    async def sql_error(self, ctx: MyContext, exc: commands.CommandError):
        exc = getattr(exc, 'original', exc)
        tb = ''.join(traceback.format_exception(exc.__class__, exc, exc.__traceback__, limit=3))
        embed = discord.Embed(color=discord.Color.red())
        embed.add_field(name='Traceback', value=f'```{tb}```')
        if isinstance(exc, StatementError):
            msg = 'The script failed with an error (check your syntax?)'
        else:
            msg = 'An unexpected error has occurred, my husbando is on the case'
        await ctx.message.add_reaction('\N{CROSS MARK}')
        await ctx.send(msg, embed=embed)
        self.log_tb(ctx, exc)

    @admin.command(name='oauth')
    async def send_oauth(self, ctx: MyContext):
        """Sends the bot's OAUTH token."""

        await self.bot.get_user(self.bot.owner_id).send(self.bot.settings.token)
        await ctx.message.add_reaction('✅')

    @admin.group(name='command', )
    async def admin_cmd(self, ctx: MyContext):
        """Manage bot commands"""

    @admin_cmd.command(name='disable')
    async def disable_command(self, ctx: MyContext, *, cmd: CommandConverter):
        """Disable a command"""

        if cmd.name in self.disabled_commands:
            await ctx.send(f'{cmd} is already disabled')
        else:
            self.disabled_commands.add(cmd.name)
            cmd.enabled = False
            await ctx.message.add_reaction('✅')

    @admin_cmd.command(name='enable')
    async def enable_command(self, ctx: MyContext, *, cmd: CommandConverter):
        """Enable a command"""

        if cmd.name in self.disabled_commands:
            self.disabled_commands.discard(cmd.name)
            cmd.enabled = True
            await ctx.message.add_reaction('✅')
        else:
            await ctx.send(f'{cmd} is already enabled')

    @admin_cmd.error
    async def admin_cmd_error(self, ctx: MyContext, exc: Exception):
        if isinstance(exc, commands.ConversionError):
            await ctx.send(f'Command "{exc.original.args[0]}" not found')

    @admin.group()
    async def cog(self, ctx: MyContext):
        """Manage bot cogs"""

    @staticmethod
    async def git_pull(ctx: MyContext):
        async with ctx.typing():
            fut = await asyncio.create_subprocess_shell('git pull')
            await fut.wait()
        return fut.returncode == 0
    
    async def cog_operation(self, ctx: MyContext, mode: typing.Literal['load', 'unload', 'reload'], cog: str):
        def default_method(_):
            raise commands.ExtensionError

        method = getattr(self.bot, f'{mode}_extension', default_method)
        if cog == 'jishaku':
            extension = cog
        else:
            extension = f'pikalaxbot.cogs.{cog}'
        real_cog = cog.title().replace('_', '')
        try:
            method(extension)
        except commands.ExtensionError:
            await ctx.send(f'Failed to {mode} cog "{real_cog}"')
            raise

    @cog.command(name='disable')
    async def disable_cog(self, ctx: MyContext, *cogs: clean_lower):
        """Disable cogs"""

        failures = {}
        for cog in cogs:
            if cog == self.__class__.__name__.lower():
                await ctx.send(f'Cannot unload the {cog} cog!!')
                continue
            if cog in self.disabled_cogs:
                await ctx.send(f'BaseCog "{cog}" already disabled')
                continue
            try:
                await self.cog_operation(ctx, 'unload', cog)
            except Exception as e:
                failures[cog] = e
            self.disabled_cogs.add(cog)
        if failures:
            raise CogOperationError('unload', **failures)

    @cog.command(name='enable')
    async def enable_cog(self, ctx: MyContext, *cogs: clean_lower):
        """Enable cogs"""

        await Modtools.git_pull(ctx)
        failures = {}
        for cog in cogs:
            if cog not in self.disabled_cogs:
                await ctx.send(f'BaseCog "{cog}" already enabled or does not exist')
                continue
            try:
                await self.cog_operation(ctx, 'load', cog)
            except Exception as e:
                failures[cog] = e
            else:
                self.disabled_cogs.discard(cog)
        if failures:
            raise CogOperationError('load', **failures)

    @cog.command(name='reload')
    async def reload_cog(self, ctx: MyContext, *cogs: clean_lower):
        """Reload cogs"""

        await Modtools.git_pull(ctx)
        failures = {}

        cooldown = commands.CooldownMapping.from_cooldown(1, 1, commands.BucketType.default)

        if not cogs:
            cogs = tuple(
                extn.replace('pikalaxbot.cogs.', '')
                for extn in self.bot.extensions
            )

        msg = await ctx.send(f'Reloading {len(cogs)} extension(s)...')

        succeeded = []
        fresh = True
        for cog in cogs:
            if cog == 'jishaku':
                extn = cog
            else:
                extn = f'pikalaxbot.cogs.{cog}'
            if extn in self.bot.extensions:
                try:
                    await self.cog_operation(ctx, 'reload', cog)
                except Exception as e:
                    failures[cog] = e
                else:
                    succeeded.append(cog.title())
                    if fresh := not cooldown.update_rate_limit(msg):
                        await msg.edit(content='Reloaded ' + ', '.join(succeeded))
            else:
                await ctx.send(f'Cog {cog} not loaded, use {self.load_cog.qualified_name} instead')
        if not fresh:
            await msg.edit(content='Reloaded ' + ', '.join(succeeded))
        if failures:
            raise CogOperationError('reload', **failures)

    @cog.command(name='load')
    async def load_cog(self, ctx: MyContext, *cogs: clean_lower):
        """Load cogs that aren't already loaded"""

        await Modtools.git_pull(ctx)
        failures = {}
        for cog in cogs:
            if cog in self.disabled_cogs:
                await ctx.send(f'BaseCog "{cog}" is disabled!')
                continue
            try:
                await self.cog_operation(ctx, 'load', cog)
            except Exception as e:
                failures[cog] = e
        if failures:
            raise CogOperationError('load', **failures)

    @admin.command(name='debug')
    async def toggle_debug(self, ctx: MyContext):
        """Toggle debug mode"""

        self.debug = not self.debug
        await ctx.send(f'Set debug mode to {"on" if self.debug else "off"}')

    @admin.command(name='log', aliases=['logs'])
    async def send_log(self, ctx: MyContext):
        """DM the logfile to the bot's owner"""

        handler: typing.Optional[logging.FileHandler] = discord.utils.find(
            lambda h: isinstance(h, logging.FileHandler),
            self.bot.logger.handlers
        )
        if handler is None:
            await ctx.send('No log file handler is registered')
        else:
            await ctx.author.send(file=discord.File(handler.baseFilename))
            await ctx.message.add_reaction('✅')

    @admin.command(name='prefix')
    async def change_prefix(self, ctx: MyContext, prefix='p!'):
        """Update the bot's command prefix"""

        await set_guild_prefix(ctx, prefix)
        await ctx.message.add_reaction('✅')

    @admin.command()
    async def purge(self, ctx: MyContext, channel: typing.Optional[discord.TextChannel], limit=10):
        """Purge <limit> of the bot's messages in the current (or given) channel"""

        channel = channel or ctx.channel
        async with ctx.typing():
            to_delete = await filter_history(channel, limit=limit, check=lambda m: m.author == self.bot.user)
            try:
                await ctx.channel.delete_messages(to_delete)
            except discord.HTTPException:
                for msg in to_delete:
                    try:
                        await msg.delete()
                    except discord.HTTPException:
                        pass
        await ctx.message.add_reaction('✅')

    async def cog_command_error(self, ctx: MyContext, error: commands.CommandError):
        if hasattr(ctx.command, 'on_error'):
            return
        if isinstance(error, commands.CommandInvokeError):
            error = error.original
        await ctx.message.add_reaction('❌')
        if isinstance(error, CogOperationError):
            for cog, original in error.cog_errors.items():
                if not original:
                    continue
                orig = getattr(original, 'original', original) or original
                await self.bot.get_cog('ErrorHandling').send_tb(ctx, orig, origin=f'{error.mode}ing {cog}')
        else:
            await ctx.send(f'**{error.__class__.__name__}**: {error}', delete_after=10)
            self.log_tb(ctx, error)

    @commands.command(name='cl')
    async def fast_cog_load(self, ctx: MyContext, *cogs: clean_lower):
        """Load the extension"""

        await self.load_cog(ctx, *cogs)

    @commands.command(name='cr')
    async def fast_cog_reload(self, ctx: MyContext, *cogs: clean_lower):
        """Reoad the extension"""

        await self.reload_cog(ctx, *cogs)


def setup(bot: PikalaxBOT):
    bot.add_cog(Modtools(bot))
