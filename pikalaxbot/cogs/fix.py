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

import re
import time
from discord.ext import commands
from . import BaseCog


class Fix(BaseCog):
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
        self.bot_owners = {}
        self.bot_names = {}

    async def init_db(self, sql):
        await sql.execute('CREATE TABLE IF NOT EXISTS fix (name TEXT PRIMARY KEY, owner TEXT NOT NULL, altname TEXT)')
        for key, value in self.initial_bot_owners.items():
            altname = self.initial_bot_names.get(key)
            await sql.execute('INSERT OR IGNORE INTO fix VALUES (?, ?, ?)', (key, value, altname))
        async with sql.execute('SELECT * FROM fix') as cur:
            async for name, owner, altname in cur:
                self.bot_owners[name] = owner
                if altname:
                    self.bot_names[name] = altname

    @staticmethod
    def get_fix_alias(ctx):
        if ctx.invoked_with is not None:
            match = re.match(r'fix(\w*)', ctx.invoked_with)
            return match and match.group(1)

    @commands.command()
    async def fix(self, ctx: commands.Context):
        """!fix<botname> - Nag the bot's owner to fix their bot"""
        alias = self.get_fix_alias(ctx)
        owner = self.bot_owners.get(alias, 'already')
        botname = self.bot_names.get(alias, 'your bot')
        await ctx.send(f'"Fix {botname}, {owner}!" - PikalaxALT {time.gmtime().tm_year:d}')

    @BaseCog.listener()
    async def on_message(self, message):
        ctx = await self.bot.get_context(message)
        if ctx.prefix and not ctx.valid and Fix.get_fix_alias(ctx) \
                and await self.fix.can_run(ctx):
            await self.fix(ctx)


def setup(bot):
    bot.add_cog(Fix(bot))
