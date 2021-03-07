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

from discord.ext import commands
from . import *
from ..constants import *


class Epic(BaseCog):
    """Commands unique to the Epic guild. Hi Cyan o/"""

    def cog_check(self, ctx: MyContext):
        return ctx.guild.id == EPIC_GUILD_ID

    @commands.command()
    async def ripchat(self, ctx: MyContext):
        """Pays respects to the death of the chat."""

        await ctx.send(
            'And lo, the chat did die on this day. '
            'And lo, all discussion ceased. '
            'The chat had gone to meet its makers in the sky. '
            'It remained stiff. '
            'It ripped, and went forth into the ether forevermore. '
            'And never again shall it rise, until someone steps forth and speaketh unto the chat once again. '
            'In the name of the Helix, the Dome, and the Amber of Olde, Amen. '
            'Please pay your final respects now.'
        )
