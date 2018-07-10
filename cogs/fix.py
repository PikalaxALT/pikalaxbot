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
from utils.default_cog import Cog


class Fix(Cog):
    bot_owners = {
        'pika': 'PikalaxALT',
        'groudon': 'chfoo',
        'yay': 'azum and tustin',
        'updater': 'tustin',
        'starmie': 'Danny',
        'meme': 'Jet'
    }
    bot_names = {
        'yay': 'xfix\'s bot'
    }

    @staticmethod
    def get_fix_alias(ctx):
        if ctx.invoked_with is not None:
            match = re.match(r'fix(\w*)', ctx.invoked_with)
            if match is not None:
                return match.group(1)

    @commands.command()
    async def fix(self, ctx: commands.Context):
        alias = self.get_fix_alias(ctx)
        owner = self.bot_owners.get(alias, 'already')
        botname = self.bot_names.get(alias, 'your bot')
        await ctx.send(f'"Fix {botname}, {owner}!" - PikalaxALT {time.gmtime().tm_year:d}')

    async def on_message(self, message):
        ctx = await self.bot.get_context(message)
        if ctx.command is None and self.get_fix_alias(ctx) is not None:
            ctx.command = self.fix
            return await self.bot.invoke(ctx)


def setup(bot):
    bot.add_cog(Fix(bot))
