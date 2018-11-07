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

        cog = self.bot.get_cog('Markov')

        if user.bot and msg.author == guild.me:
            chain = cog.gen_msg(len_max=250, n_attempts=10)
            await channel.send(f'!mail {chain}')
            await self.bot.wait_for('message', check=lambda m: m.author == user and m.channel == channel)
            await channel.send(f'{user.mention} pls')


def setup(bot: PikalaxBOT):
    bot.add_cog(Groudonger(bot))
