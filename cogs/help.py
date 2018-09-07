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

# Credits to Danny for making this featureful paginated help.

from discord.ext import commands

from cogs import BaseCog
from utils.paginator import HelpPaginator


def setup(bot):
    class Help(BaseCog):
        @commands.command(**bot.help_attrs)
        async def _help(self, ctx: commands.Context, *, command=None):
            """Shows help about a command or the bot"""

            if command is None:
                p = await HelpPaginator.from_bot(ctx)
            else:
                entity = self.bot.get_cog(command) or self.bot.get_command(command)

                if entity is None:
                    clean = command.replace('@', '@\u200b')
                    return await ctx.send(f'Command or category "{clean}" not found.')
                elif isinstance(entity, commands.Command):
                    p = await HelpPaginator.from_command(ctx, entity)
                else:
                    p = await HelpPaginator.from_cog(ctx, entity)

            await p.paginate()

        @_help.error
        async def help_error(self, ctx, exc):
            self.log_tb(ctx, exc)
            if hasattr(exc, 'orig'):
                exc = exc.orig
            await ctx.send(exc)

    help_name = bot.help_attrs['name']
    bot.remove_command(help_name)
    bot.add_cog(Help(bot))


def teardown(bot):
    bot.command(**bot.help_attrs)(commands.bot._default_help_command)
