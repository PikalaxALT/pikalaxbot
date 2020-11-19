import discord
from discord.ext import commands
from . import BaseCog


EPIC_GUILD_ID = 471312957687463956


class Epic(BaseCog):
    """Commands unique to the Epic guild. Hi Cyan o/"""

    def cog_check(self, ctx):
        return ctx.guild.id == EPIC_GUILD_ID

    @commands.command()
    async def ripchat(self, ctx):
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


def setup(bot):
    bot.add_cog(Epic(bot))
