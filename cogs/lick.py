import random
import discord
from discord.ext import commands
from cogs import BaseCog


class Lick(BaseCog):
    notes_s = 'C', 'C♯', 'D', 'D♯', 'E', 'F', 'F♯', 'G', 'G♯', 'A', 'A♯', 'B'
    notes_f = 'C', 'D♭', 'D', 'E♭', 'E', 'F', 'G♭', 'G', 'A♭', 'A', 'B♭', 'B'
    lick = 0, 2, 3, 5, 2, -2, 0

    @commands.command()
    async def lick(self, ctx: commands.Context):
        start = random.randint(0, 11)
        use_s = True
        for i, tongue in enumerate(Lick.lick[:-1]):
            if Lick.notes_s[(tongue + start) % 12][0] == Lick.notes_s[(Lick.lick[i + 1] + start) % 12][0]:
                use_s = False
                break
        await ctx.send(' '.join((Lick.notes_s if use_s else Lick.notes_f)[(start + offset) % 12] for offset in Lick.lick))


def setup(bot):
    bot.add_cog(Lick(bot))
