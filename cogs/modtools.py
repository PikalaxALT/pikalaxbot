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
import tempfile
import traceback
import sqlite3
import logging
from discord.ext import commands
from cogs import ClientSessionCog


class lower(commands.clean_content):
    async def convert(self, ctx, argument):
        arg = await super().convert(ctx, argument)
        return arg.lower()


class ModTools(ClientSessionCog):
    prefix = 'p!'
    game = 'p!help'
    disabled_commands = set()
    disabled_cogs = set()
    debug = False
    config_attrs = 'prefix', 'game', 'disabled_commands', 'disabled_cogs', 'debug'

    def __unload(self):
        task = self.bot.loop.create_task(self.cs.close())
        asyncio.wait([task], timeout=60)

    async def __local_check(self, ctx: commands.Context):
        return await self.bot.is_owner(ctx.author)

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
        with tempfile.TemporaryFile() as t:
            await ctx.message.attachments[0].save(t)
            await self.bot.user.edit(avatar=t.read())
        await ctx.send('OwO')

    @admin.group()
    async def leaderboard(self, ctx):
        """Commands for manipulating the leaderboard"""

    @admin.command(name='sql')
    async def call_sql(self, ctx, *, script):
        """Run arbitrary sql command"""
        try:
            with self.bot.sql as sql:
                sql.call_script(script)
        except sqlite3.Error:
            tb = traceback.format_exc(limit=3)
            embed = discord.Embed(color=discord.Color.red())
            embed.add_field(name='Traceback', value=f'```{tb}```')
            await ctx.send('The script failed with an error (check your syntax?)', embed=embed)
        else:
            await ctx.send('Script successfully executed')

    @admin.command(name='oauth')
    async def send_oauth(self, ctx: commands.Context):
        """Sends the bot's OAUTH token."""
        await self.bot.owner.send(self.bot.http.token)
        await ctx.message.add_reaction('☑')

    @admin.group(name='command', )
    async def admin_cmd(self, ctx: commands.Context):
        """Manage bot commands"""

    @admin_cmd.command(name='disable')
    async def disable_command(self, ctx: commands.Context, *, cmd):
        """Disable a command"""
        if cmd in self.disabled_commands:
            await ctx.send(f'{cmd} is already disabled')
        else:
            self.disabled_commands.add(cmd)
            await ctx.message.add_reaction('☑')

    @admin_cmd.command(name='enable')
    async def enable_command(self, ctx: commands.Context, *, cmd):
        """Enable a command"""
        if cmd in self.disabled_commands:
            self.disabled_commands.discard(cmd)
            await ctx.message.add_reaction('☑')
        else:
            await ctx.send(f'{cmd} is already enabled')

    @admin.group()
    async def cog(self, ctx):
        """Manage bot cogs"""

    @cog.command(name='enable')
    async def enable_cog(self, ctx, *cogs: lower):
        """Enable cogs"""
        await self.git_pull(ctx)
        for cog in cogs:
            if cog not in self.disabled_cogs:
                await ctx.send(f'Cog "{cog}" already enabled or does not exist')
                continue
            try:
                self.bot.load_extension(f'cogs.{cog}')
            except discord.ClientException:
                await ctx.send(f'Failed to load cog "{cog}"')
            else:
                await ctx.send(f'Loaded cog "{cog}"')
                self.disabled_cogs.discard(cog)

    @cog.command(name='disable')
    async def disable_cog(self, ctx, *cogs: lower):
        """Disable cogs"""
        for cog in cogs:
            if cog == self.__class__.__name__.lower():
                await ctx.send(f'Cannot unload the {cog} cog!!')
                continue
            if cog in self.disabled_cogs:
                await ctx.send(f'Cog "{cog}" already disabled')
                continue
            try:
                self.bot.unload_extension(f'cogs.{cog}')
            except discord.ClientException:
                await ctx.send(f'Failed to unload cog "{cog}"')
            else:
                await ctx.send(f'Unloaded cog "{cog}"')
                self.disabled_cogs.add(cog)

    async def git_pull(self, ctx):
        async with ctx.typing():
            fut = await asyncio.create_subprocess_shell('git pull', loop=self.bot.loop)
            await fut.wait()
        return fut.returncode == 0

    @cog.command(name='reload')
    async def reload_cog(self, ctx: commands.Context, *cogs: lower):
        """Reload cogs"""
        await self.git_pull(ctx)
        for cog in cogs:
            extn = f'cogs.{cog}'
            if extn in self.bot.extensions:
                self.bot.unload_extension(f'cogs.{cog}')
                try:
                    self.bot.load_extension(f'cogs.{cog}')
                except discord.ClientException as e:
                    if cog == self.__class__.__name__.lower():
                        return await ctx.send(f'Could not reload {cog}. {cog.title()} will be unavailable.')
                    self.disabled_cogs.add(cog)
                    await ctx.send(f'Could not reload {cog}, so it shall be disabled ({e})')
                else:
                    await ctx.send(f'Reloaded cog {cog}')

    @cog.command(name='load')
    async def load_cog(self, ctx: commands.Context, *cogs: lower):
        """Load cogs that aren't already loaded"""
        await self.git_pull(ctx)
        for cog in cogs:
            if cog in self.disabled_cogs:
                await ctx.send(f'Cog "{cog}" is disabled!')
                continue
            try:
                self.bot.load_extension(f'cogs.{cog}')
            except discord.ClientException as e:
                await ctx.send(f'Could not load {cog}: {e}')
            else:
                await ctx.send(f'Loaded cog {cog}')

    @admin.command(name='debug')
    async def toggle_debug(self, ctx):
        self.debug = not self.debug
        await ctx.send(f'Set debug mode to {"on" if self.debug else "off"}')

    @admin.command(name='log', aliases=['logs'])
    async def send_log(self, ctx):
        handler = discord.utils.find(lambda h: isinstance(h, logging.FileHandler), self.bot.logger.handlers)
        if handler is None:
            await ctx.send('No log file handler is registered')
        else:
            await ctx.author.send(file=discord.File(handler.baseFilename))
            await ctx.message.add_reaction('☑')

    @admin.command(name='prefix')
    async def change_prefix(self, ctx, prefix):
        self.prefix = prefix
        await ctx.message.add_reaction('☑')
    
    @disable_cog.before_invoke
    @disable_command.before_invoke
    @reload_cog.before_invoke
    @enable_cog.before_invoke
    @enable_command.before_invoke
    @load_cog.before_invoke
    @change_prefix.before_invoke
    @change_game.before_invoke
    async def change_settings_before_invoke(self, ctx):
        self.fetch()
    
    @disable_cog.after_invoke
    @disable_command.after_invoke
    @reload_cog.after_invoke
    @enable_cog.after_invoke
    @enable_command.after_invoke
    @load_cog.after_invoke
    @change_prefix.after_invoke
    @change_game.after_invoke
    async def change_settings_after_invoke(self, ctx):
        self.commit()


def setup(bot):
    bot.add_cog(ModTools(bot))
