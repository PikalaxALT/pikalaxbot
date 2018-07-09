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
from discord.ext import commands
from utils.sql import Sql
from utils.default_cog import Cog


class lower(commands.clean_content):
    async def convert(self, ctx, argument):
        arg = await super().convert(ctx, argument)
        return arg.lower()


class ModTools(Cog):
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
        game = game or f'{ctx.prefix}pikahelp'
        activity = discord.Game(game)
        await self.bot.change_presence(activity=activity)
        async with self.bot.settings as settings:
            settings.user.game = game
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
            with Sql() as sql:
                sql.call_script(script)
        except sqlite3.Error:
            tb = traceback.format_exc(limit=3)
            embed = discord.Embed(color=0xff0000)
            embed.add_field(name='Traceback', value=f'```{tb}```')
            await ctx.send('The script failed with an error (check your syntax?)', embed=embed)
        else:
            await ctx.send('Script successfully executed')

    @admin.command(name='oauth')
    async def send_oauth(self, ctx: commands.Context):
        """Sends the bot's OAUTH token."""
        with self.bot.settings as settings:
            token = settings.credentials.token
        await self.bot.get_user(self.bot.owner_id).send(token)
        await ctx.message.add_reaction('☑')

    @admin.group(name='command', )
    async def admin_cmd(self, ctx: commands.Context):
        """Manage bot commands"""

    @admin_cmd.command(name='disable')
    async def disable_command(self, ctx: commands.Context, *, cmd):
        """Disable a command"""
        with self.bot.settings as settings:
            if cmd in settings.meta.disabled_commands:
                await ctx.send(f'{cmd} is already disabled')
            else:
                settings.meta.disabled_commands.add(cmd)
                await ctx.message.add_reaction('☑')

    @admin_cmd.command(name='enable')
    async def enable_command(self, ctx: commands.Context, *, cmd):
        """Enable a command"""
        with self.bot.settings as settings:
            if cmd in settings.meta.disabled_commands:
                settings.meta.disabled_commands.discard(cmd)
                await ctx.message.add_reaction('☑')
            else:
                await ctx.send(f'{cmd} is already enabled')

    @admin.group()
    async def cog(self, ctx):
        """Manage bot cogs"""

    @cog.command(name='enable')
    async def enable_cog(self, ctx, cog: lower):
        """Enable cog"""
        with self.bot.settings as settings:
            if cog not in settings.meta.disabled_cogs:
                return await ctx.send(f'Cog "{cog}" already enabled or does not exist')
            try:
                self.bot.load_extension(f'cogs.{cog}')
            except discord.ClientException:
                await ctx.send(f'Failed to load cog "{cog}"')
            else:
                await ctx.send(f'Loaded cog "{cog}"')
                settings.meta.disabled_cogs.discard(cog)

    @cog.command(name='disable')
    async def disable_cog(self, ctx, cog: lower):
        """Disable cog"""
        with self.bot.settings as settings:
            if cog in settings.user.disabled_cogs:
                return await ctx.send(f'Cog "{cog}" already disabled')
            try:
                self.bot.unload_extension(f'cogs.{cog}')
            except discord.ClientException:
                await ctx.send(f'Failed to unload cog "{cog}"')
            else:
                await ctx.send(f'Unloaded cog "{cog}"')
                settings.user.disabled_cogs.add(cog)


def setup(bot):
    bot.add_cog(ModTools(bot))
