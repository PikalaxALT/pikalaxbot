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

import re
import time
import discord
from discord.ext import commands
from . import *
import typing


class Fix(BaseCog):
    """Use these commands to yell at bot developers."""

    initial_bot_owners = {
        'pika': 'PikalaxALT',
        'groudon': 'chfoo',
        'yay': 'azum and tustin',
        'updater': 'tustin',
        'starmie': 'Danny',
        'danny': 'Danny',
        'meme': 'Jet'
    }
    initial_bot_names = {
        'yay': 'xfix\'s bot'
    }

    def __init__(self, bot):
        super().__init__(bot)
        self.bot_owners: dict[str, str] = {}
        self.bot_names: dict[str, str] = {}

    async def init_db(self, sql):
        await sql.execute('CREATE TABLE IF NOT EXISTS fix (name TEXT PRIMARY KEY, owner TEXT NOT NULL, altname TEXT)')
        values = [(key, value, self.initial_bot_names.get(key)) for key, value in self.initial_bot_owners.items()]
        await sql.executemany('INSERT INTO fix VALUES ($1, $2, $3) ON CONFLICT (name) DO NOTHING', values)
        for name, owner, altname in await sql.fetch('SELECT * FROM fix'):
            self.bot_owners[name] = owner
            if altname:
                self.bot_names[name] = altname

    @staticmethod
    def get_fix_alias(ctx: MyContext) -> typing.Optional[str]:
        if ctx.invoked_with is not None:
            match = re.match(r'fix(\w*)', ctx.invoked_with)
            return match and match.group(1)

    @commands.group(invoke_without_command=True)
    async def fix(self, ctx: MyContext):
        """`{ctx.prefix}fix<botname>` - Nag the bot's owner to fix their bot"""
        alias = self.get_fix_alias(ctx)
        owner = self.bot_owners.get(alias, 'already')
        botname = self.bot_names.get(alias, 'your bot')
        await ctx.send(f'"Fix {botname}, {owner}!" - PikalaxALT {time.gmtime().tm_year:d}')

    @BaseCog.listener()
    async def on_message(self, message: discord.Message):
        ctx: MyContext = await self.bot.get_context(message)
        if ctx.prefix is not None \
                and not ctx.valid \
                and Fix.get_fix_alias(ctx) \
                and await self.fix.can_run(ctx):
            await self.fix(ctx)

    @fix.command()
    async def add(self, ctx: MyContext, key: str.lower, owner: str, altname: str = None):
        """Add a bot to my database"""
        if key not in self.bot_owners:
            self.bot_owners[key] = owner
            if altname:
                self.bot_owners[key] = altname
            elif key in self.bot_names:
                del self.bot_names[key]
            async with self.bot.sql as sql:
                await sql.execute(
                    'INSERT INTO fix '
                    'VALUES ($1, $2, $3) '
                    'ON CONFLICT (name) '
                    'DO UPDATE '
                    'SET owner = $2, altname = $3',
                    key, owner, altname)
            await ctx.message.add_reaction('\N{WHITE HEAVY CHECK MARK}')
        else:
            await ctx.message.add_reaction('\N{CROSS MARK}')

    @fix.command(name='del')
    async def delete_key(self, ctx: MyContext, key: str.lower):
        """Remove a bot from my database"""
        if key in self.bot_owners:
            del self.bot_owners[key]
            if key in self.bot_names:
                del self.bot_names[key]
            async with self.bot.sql as sql:
                await sql.execute('DELETE FROM fix WHERE name = $1', key)
            await ctx.message.add_reaction('\N{WHITE HEAVY CHECK MARK}')
        else:
            await ctx.message.add_reaction('\N{CROSS MARK}')


def setup(bot: PikalaxBOT):
    bot.add_cog(Fix(bot))
