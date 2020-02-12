import asyncio
import discord
import re
from . import BaseCog


class Evangelist(BaseCog):
    @BaseCog.listener()
    async def on_member_update(self, before, after):
        if after.guild.id != 336642139381301249:
            return
        if discord.utils.get(before.roles, name='Infected'):
            return
        if not discord.utils.get(after.roles, name='Infected'):
            return
        channel = discord.utils.get(before.guild.channels, name='testing')
        await channel.send(f'{after.mention} lol get infected nerd')

    @BaseCog.listener()
    async def on_message(self, message):
        if message.guild.id != 336642139381301249:
            return
        if message.channel.name != 'event':
            return
        if 'dead' not in message.content.split():
            return
        channel = discord.utils.get(message.guild.channels, name='testing')
        match = re.search(r'.+#\d{4}\b', message.content).group(0)
        # Paranoid block prevention
        while not await asyncio.sleep(0, message.guild.get_member_named(match)):
            match = match[1:].lstrip()
            if match.startswith('#'):
                return
        await channel.send(f'{message.guild.get_member_named(match).mention} lol rest in piece nerd')


def setup(bot):
    bot.add_cog(Evangelist(bot))
