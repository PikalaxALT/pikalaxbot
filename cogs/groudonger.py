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

import discord
from cogs import BaseCog
from utils.botclass import PikalaxBOT


class Groudonger(BaseCog):
    async def on_reaction_add(self, reaction, user):
        msg: discord.Message = reaction.message
        channel: discord.TextChannel = msg.channel
        guild: discord.Guild = msg.guild

        groudonger: discord.Member = guild.get_member(303257160421212160)
        emoji: discord.Emoji = discord.utils.get(guild.emojis, id=507398431115837441)

        if user == groudonger and reaction.emoji == emoji:
            await channel.send('!wow')
            await self.bot.wait_for('message', check=lambda m: m.author == groudonger and m.channel == channel)
            await channel.send(f'{groudonger.mention} pls')


def setup(bot: PikalaxBOT):
    bot.add_cog(Groudonger(bot))
