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
import traceback
import sqlite3
import logging
import typing
from discord.ext import commands, menus
from . import BaseCog
from .utils.converters import CommandConverter
from .utils.errors import CogOperationError
from .utils.menus import NavMenuPages


class SqlResponseEmbed(menus.ListPageSource):
    async def format_page(self, menu, page):
        return discord.Embed(
            title=menu.sql_cmd,
            description=page,
            colour=0xf47fff
        )


class lower(str):
    @classmethod
    async def convert(cls, ctx, argument):
        arg = await commands.clean_content().convert(ctx, argument)
        return arg.lower()


async def filter_history(channel, **kwargs):
    check = kwargs.pop('check', lambda m: True)
    limit = kwargs.pop('limit', None)
    count = 0
    async for message in channel.history(limit=None, **kwargs):
        if check(message):
            yield message
            count += 1
            if count == limit:
                break


class Modtools(BaseCog):
    """Commands for the bot owner to use"""

    prefix = 'p!'
    game = 'p!help'
    disabled_commands = set()
    disabled_cogs = set()
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
        await sql.execute("create table if not exists prefixes (guild integer not null primary key, prefix text not null)")

    def cog_unload(self):
        for name in list(self.disabled_commands):
            cmd = self.bot.get_command(name)
            if cmd:
                cmd.enabled = True
            else:
                self.disabled_commands.discard(name)

    async def cog_check(self, ctx: commands.Context):
        if not await self.bot.is_owner(ctx.author):
            raise commands.NotOwner('You do not own this bot')
        return True

    @commands.group(case_insensitive=True)
    async def admin(self, ctx):
        """Commands for the admin console"""

    @admin.group(case_insensitive=True)
    async def ui(self, ctx):
        """Commands to manage the bot's appearance"""

    @ui.command(name='nick')
    @commands.bot_has_permissions(change_nickname=True)
    async def change_nick(self, ctx: commands.Context, *, nickname: commands.clean_content = None):
        """Change or reset the bot's nickname"""

        await ctx.me.edit(nick=nickname)
        await ctx.send('OwO')

    @ui.command(name='game')
    async def change_game(self, ctx: commands.Context, *, game: str = None):
        """Change or reset the bot's presence"""

        game = game or f'{ctx.prefix}help'
        activity = discord.Game(game)
        await self.bot.change_presence(activity=activity)
        self.game = game
        await ctx.send(f'I\'m now playing {game}')

    @ui.command(name='avatar')
    @commands.check(lambda ctx: len(ctx.message.attachments) == 1)
    async def change_avatar(self, ctx: commands.Context):
        """Change avatar"""
        await self.bot.user.edit(avatar=await ctx.message.attachments[0].read())
        await ctx.send('OwO')

    @admin.group()
    async def leaderboard(self, ctx):
        """Commands for manipulating the leaderboard"""

    @admin.command(name='sql')
    async def call_sql(self, ctx, *, script):
        """Run arbitrary sql command"""

        pag = commands.Paginator(max_size=2048)
        async with ctx.typing():
            async with self.bot.sql as sql:
                async with sql.execute(script) as cursor:
                    async for row in cursor:
                        pag.add_line('|'.join(map(str, row)))
        if pag.pages:
            menu = NavMenuPages(SqlResponseEmbed(pag.pages, per_page=1), delete_message_after=True, clear_reactions_after=True)
            menu.sql_cmd = script
            await menu.start(ctx)
        await ctx.message.add_reaction('\N{white heavy check mark}')

    @commands.command(name='sql')
    async def top_call_sql(self, ctx, *, script):
        """Run arbitrary sql command"""

        await self.call_sql(ctx, script=script)

    @call_sql.error
    @top_call_sql.error
    async def sql_error(self, ctx, exc):
        exc = getattr(exc, 'original', exc)
        tb = ''.join(traceback.format_exception(exc.__class__, exc, exc.__traceback__, limit=3))
        embed = discord.Embed(color=discord.Color.red())
        embed.add_field(name='Traceback', value=f'```{tb}```')
        if isinstance(exc, sqlite3.Error):
            msg = 'The script failed with an error (check your syntax?)'
        else:
            msg = 'An unexpected error has occurred, my husbando is on the case'
        await ctx.message.add_reaction('\N{CROSS MARK}')
        await ctx.send(msg, embed=embed)
        self.log_tb(ctx, exc)

    @admin.command(name='oauth')
    async def send_oauth(self, ctx: commands.Context):
        """Sends the bot's OAUTH token."""

        await self.bot.get_user(self.bot.owner_id).send(self.bot.http.token)
        await ctx.message.add_reaction('✅')

    @admin.group(name='command', )
    async def admin_cmd(self, ctx: commands.Context):
        """Manage bot commands"""

    @admin_cmd.command(name='disable')
    async def disable_command(self, ctx: commands.Context, *, cmd: CommandConverter):
        """Disable a command"""

        if cmd.name in self.disabled_commands:
            await ctx.send(f'{cmd} is already disabled')
        else:
            self.disabled_commands.add(cmd.name)
            cmd.enabled = False
            await ctx.message.add_reaction('✅')

    @admin_cmd.command(name='enable')
    async def enable_command(self, ctx: commands.Context, *, cmd: CommandConverter):
        """Enable a command"""

        if cmd.name in self.disabled_commands:
            self.disabled_commands.discard(cmd.name)
            cmd.enabled = True
            await ctx.message.add_reaction('✅')
        else:
            await ctx.send(f'{cmd} is already enabled')

    @admin_cmd.error
    async def admin_cmd_error(self, ctx: commands.Context, exc: Exception):
        if isinstance(exc, commands.ConversionError):
            await ctx.send(f'Command "{exc.original.args[0]}" not found')

    @admin.group()
    async def cog(self, ctx):
        """Manage bot cogs"""

    async def git_pull(self, ctx):
        async with ctx.typing():
            fut = await asyncio.create_subprocess_shell('git pull', loop=self.bot.loop)
            await fut.wait()
        return fut.returncode == 0
    
    async def cog_operation(self, ctx, mode, cog):
        def default_method(_):
            raise commands.ExtensionError

        method = getattr(self.bot, f'{mode}_extension', default_method)
        if cog == 'jishaku':
            extension = cog
        elif cog.startswith('ext.'):
            extension = f'pikalaxbot.{cog}'
        else:
            extension = f'pikalaxbot.cogs.{cog}'
        real_cog = cog.title().replace('_', '')
        try:
            if cog == 'ext.pokeapi':
                await self.bot.loop.run_in_executor(None, method, extension)
            else:
                method(extension)
        except commands.ExtensionError:
            await ctx.send(f'Failed to {mode} cog "{real_cog}"')
            raise

    @BaseCog.listener()
    async def on_cog_db_init(self, cog):
        tasks = [
            self.bot.loop.create_task(self.bot.wait_for('cog_db_init_error', check=lambda c, e: c == cog)),
            self.bot.loop.create_task(self.bot.wait_for('cog_db_init_complete', check=lambda c: c == cog))
        ]
        done, pending = await asyncio.wait(tasks, return_when=asyncio.ALL_COMPLETED)
        [task.cancel() for task in pending]
        result = done.pop().result()
        if isinstance(result, tuple):
            _, error = result
            await self.bot.wait_until_ready()
            tb = ''.join(traceback.format_exception(error.__class__, error, error.__traceback__))
            msg = f'Ignoring exception in db init for cog {cog}:\n{tb}'
            await self.bot.send_tb(msg)

    @cog.command(name='disable')
    async def disable_cog(self, ctx, *cogs: lower):
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
    async def enable_cog(self, ctx, *cogs: lower):
        """Enable cogs"""

        await self.git_pull(ctx)
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
    async def reload_cog(self, ctx: commands.Context, *cogs: lower):
        """Reload cogs"""

        await self.git_pull(ctx)
        failures = {}

        cooldown = commands.CooldownMapping.from_cooldown(1, 1, commands.BucketType.default)

        if not cogs:
            cogs = [extn.replace('pikalaxbot.cogs.', '').replace('pikalaxbot.ext.', 'ext.') for extn in self.bot.extensions]

        msg = await ctx.send(f'Reloading {len(cogs)} extension(s)...')

        succeeded = []
        fresh = True
        for cog in cogs:
            if cog == 'jishaku':
                extn = cog
            elif cog.startswith('ext.'):
                extn = f'pikalaxbot.{cog}'
            else:
                extn = f'pikalaxbot.cogs.{cog}'
            if extn in self.bot.extensions:
                try:
                    await self.cog_operation(ctx, 'reload', cog)
                except Exception as e:
                    failures[cog] = e
                else:
                    succeeded.append(cog.title())
                    if not cooldown.update_rate_limit(msg):
                        await msg.edit(content='Reloaded ' + ', '.join(succeeded))
                        fresh = True
                    else:
                        fresh = False
            else:
                await ctx.send(f'Cog {cog} not loaded, use {self.load_cog.qualified_name} instead')
        if not fresh:
            await msg.edit(content='Reloaded ' + ', '.join(succeeded))
        if failures:
            raise CogOperationError('reload', **failures)

    @cog.command(name='load')
    async def load_cog(self, ctx: commands.Context, *cogs: lower):
        """Load cogs that aren't already loaded"""

        await self.git_pull(ctx)
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
    async def toggle_debug(self, ctx):
        """Toggle debug mode"""

        self.debug = not self.debug
        await ctx.send(f'Set debug mode to {"on" if self.debug else "off"}')

    @admin.command(name='log', aliases=['logs'])
    async def send_log(self, ctx):
        """DM the logfile to the bot's owner"""

        handler = discord.utils.find(lambda h: isinstance(h, logging.FileHandler), self.bot.logger.handlers)
        if handler is None:
            await ctx.send('No log file handler is registered')
        else:
            await ctx.author.send(file=discord.File(handler.baseFilename))
            await ctx.message.add_reaction('✅')

    @admin.command(name='prefix')
    async def change_prefix(self, ctx, prefix='p!'):
        """Update the bot's command prefix"""

        async with self.bot.sql as sql:
            await sql.execute("replace into prefixes (guild, prefix) values (?, ?)", (ctx.guild.id, prefix))
        self.bot.guild_prefixes[ctx.guild.id] = prefix
        await ctx.message.add_reaction('✅')

    @admin.command()
    @commands.bot_has_permissions(manage_messages=True)
    async def purge(self, ctx: commands.Context, channel: typing.Optional[discord.TextChannel], limit=10):
        """Purge <limit> of the bot's messages in the current (or given) channel"""

        channel = channel or ctx.channel
        async with ctx.typing():
            to_delete = [m async for m in filter_history(channel, limit=limit, check=lambda m: m.author == self.bot.user)]
            await ctx.channel.delete_messages(to_delete)
        await ctx.message.add_reaction('✅')

    async def cog_command_error(self, ctx, error):
        if hasattr(ctx.command, 'on_error'):
            return
        await ctx.message.add_reaction('❌')
        await ctx.send(f'**{error.__class__.__name__}**: {error}', delete_after=10)
        self.log_tb(ctx, error)

    @commands.command(name='cl')
    async def fast_cog_load(self, ctx, *cogs: lower):
        """Load the extension"""

        await self.load_cog(ctx, *cogs)

    @commands.command(name='cr')
    async def fast_cog_reload(self, ctx, *cogs: lower):
        """Reoad the extension"""

        await self.reload_cog(ctx, *cogs)


def setup(bot):
    bot.add_cog(Modtools(bot))
