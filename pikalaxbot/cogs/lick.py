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

import random
import discord
from discord.ext import commands
from . import *
import typing
import re
import math


class cycleseq(tuple):
    """
    Implements a cycler that can be indexed. Objects of this type are immutable.

    Indexing with an integer returns the value at that index as though the underlying
    tuple were extended to accommodate that index as necessary.

    Indexing with a finite slice will return a tuple with the selected elements.

    Indexing with an endless slice will return an instance of cycleseq for which
    the underlying tuple is as small as possible.
    """
    def __getitem__(self, item: typing.Union[int, slice]):
        if isinstance(item, slice):
            start = item.start or 0
            stop = item.stop
            step = item.step or 1
            if stop is None:
                if start == 0 and step == 1:
                    return self
                lcm = math.lcm(len(self), step)
                ret = tuple(self[i] for i in range(start, start + lcm, abs(step)))
                if step < 0:
                    ret = reversed(ret)
                return cycleseq(ret)
            return tuple(self[i] for i in range(start, stop, step))
        return super().__getitem__(item % len(self))

    def __repr__(self):
        return '{0.__class__.__name__}{1}'.format(self, super().__repr__())


class Lick(BaseCog):
    """Commands that lick you."""

    notes_s: cycleseq[str] = cycleseq(('C', 'C♯', 'D', 'D♯', 'E', 'F', 'F♯', 'G', 'G♯', 'A', 'A♯', 'B'))
    notes_f: cycleseq[str] = cycleseq(('C', 'D♭', 'D', 'E♭', 'E', 'F', 'G♭', 'G', 'A♭', 'A', 'B♭', 'B'))
    lick = 0, 2, 3, 5, 2, -2, 0

    @commands.command(name='lick')
    async def lick_c(self, ctx: MyContext):
        """
        https://m.youtube.com/watch?v=krDxhnaKD7Q
        """
        start = random.randrange(12)
        use_s = all(
            self.notes_s[tongue + start][0] != self.notes_s[self.lick[i + 1] + start][0]
            for i, tongue in enumerate(self.lick[:-1])
        )
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
