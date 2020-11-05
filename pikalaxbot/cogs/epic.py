import discord
from discord.ext import commands
from . import BaseCog


class Epic(BaseCog):
    """Commands unique to the Epic guild. Hi Cyan o/"""

    def cog_check(self, ctx):
        return ctx.guild.id == 471312957687463956

    @commands.command()
    async def ripchat(self, ctx):
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
