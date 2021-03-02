import discord
from discord.ext import commands
import typing
from . import *


GuildChannel = typing.Union[
    discord.TextChannel,
    discord.VoiceChannel,
    discord.CategoryChannel,
]


class Channels(BaseCog):
    """Commands related to managing guild channels"""

    EMOJIS = {
        discord.ChannelType.text: '#️⃣',
        discord.ChannelType.voice: '🔈',
        discord.ChannelType.news: '�',
        discord.ChannelType.store: '🏪',
    }

    def get_channel_repr(self, channel: GuildChannel):
        return '{} {.name}'.format(self.EMOJIS[channel.type], channel)

    @commands.group(invoke_without_command=True)
    async def channels(self, ctx: MyContext):
        """Shows the channel list"""
        embed = discord.Embed()
        for category, channels in ctx.guild.by_category():  \
                # type: typing.Optional[discord.CategoryChannel], list[discord.TextChannel]
            embed.add_field(
                name=str(category or '\u200b'),
                value='\n'.join(map(self.get_channel_repr, channels)),
                inline=False
            )
        await ctx.send(embed=embed)


def setup(bot: PikalaxBOT):
    bot.add_cog(Channels(bot))
