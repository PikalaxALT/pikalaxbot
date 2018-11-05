import discord
from discord.ext import commands
from cogs import BaseCog
from utils.botclass import PikalaxBOT


class Groudonger(BaseCog):
    async def on_reaction_add(self, reaction, user):
        msg: discord.Message = reaction.message
        channel:discord.TextChannel = msg.channel
        guild: discord.Guild = msg.guild

        groudonger: discord.Member = guild.get_member(303257160421212160)
        emoji: discord.Emoji = discord.utils.get(guild.emojis, id=507398431115837441)

        if user == groudonger and reaction.emoji == emoji:
            await channel.send('!wow')
            await self.bot.wait_for('message', check=lambda m: m.author == groudonger and m.channel == channel)
            await channel.send(f'{groudonger.mention} pls')


def setup(bot: PikalaxBOT):
    bot.add_cog(Groudonger(bot))
