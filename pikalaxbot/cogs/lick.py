import random
import discord
from discord.ext import commands
from . import *
import re


class cycleseq(list):
    def __getitem__(self, item: int):
        return super().__getitem__(item % len(self))


class Lick(BaseCog):
    """Commands that lick you."""

    notes_s = cycleseq(('C', 'C♯', 'D', 'D♯', 'E', 'F', 'F♯', 'G', 'G♯', 'A', 'A♯', 'B'))
    notes_f = cycleseq(('C', 'D♭', 'D', 'E♭', 'E', 'F', 'G♭', 'G', 'A♭', 'A', 'B♭', 'B'))
    lick = 0, 2, 3, 5, 2, -2, 0

    @commands.command(name='lick')
    async def lick_c(self, ctx: MyContext):
        """
        https://m.youtube.com/watch?v=krDxhnaKD7Q
        """
        start = random.randrange(12)
        use_s = all(self.notes_s[tongue + start][0] != self.notes_s[self.lick[i + 1] + start][0] for i, tongue in enumerate(self.lick[:-1]))
        notes = self.notes_s if use_s else self.notes_f
        await ctx.send(' '.join(notes[start + offset] for offset in self.lick))
    
    @commands.command(name='licc')
    async def licc_c(self, ctx: MyContext, *, recipient: discord.Member = None):
        """
        liccs u
        """
        emotes = [emote for emote in ctx.bot.emojis if re.search(r'lic[ck]', emote.name, re.I) is not None]
        emote = random.choice(emotes)
        if recipient:
            await ctx.send(f'{ctx.author.display_name} gave {recipient.mention} a huge licc {emote}')
        else:
            await ctx.send(f'{emote}')


def setup(bot: PikalaxBOT):
    bot.add_cog(Lick(bot))
