import asyncio
import discord
import datetime
from discord.ext import commands
from cogs import Cog
import time


class Poll(Cog):
    TIMEOUT = 60

    async def do_poll(self, ctx, prompt, emojis, options, content=None):
        description = '\n'.join(f'{emoji}: {option}' for emoji, option in zip(emojis, options))
        embed = discord.Embed(title=prompt, description=description)
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar_url)
        msg: discord.Message = await ctx.send(content, embed=embed)

        # This setup is to ensure that each user gets max one vote
        votes_d = {}

        def check1(rxn, athr):
            return rxn.message.id == msg.id and rxn.emoji in emojis and athr.id not in votes_d

        def check2(rxn, athr):
            return rxn.message.id == msg.id and rxn.emoji == votes_d.get(athr.id)

        end = time.time() + self.TIMEOUT
        while True:
            tasks = [
                self.bot.wait_for('reaction_add', check=check1),
                self.bot.wait_for('reaction_remove', check=check2)
            ]
            now = time.time()
            done, left = await asyncio.wait(tasks, timeout=end - now, return_when=asyncio.FIRST_COMPLETED)
            [task.cancel() for task in left]
            try:
                reaction, author = done.pop().result()
            except IndexError:  # asyncio.wait does not raise TimeoutError, so this is how we detect timeout.
                break
            vote = votes_d.get(author.id)
            if vote is None:  # This was a reaction_add event
                votes_d[author.id] = reaction.emoji
            elif vote == reaction.emoji:  # This was a reaction_remove event
                del votes_d[author.id]
            else:
                raise ValueError('Our checks passed when neither should have!')

        votes_l = list(votes_d.values())
        votes = [votes_l.count(emoji) for emoji in emojis]
        winner_count = max(votes)
        tie_emoji = []
        tie_opts = []
        for i in range(len(options)):
            if votes[i] == winner_count:
                tie_emoji.append(emojis[i])
                tie_opts.append(options[i])
        return winner_count, tie_emoji, tie_opts

    @commands.command(name='poll')
    async def poll_cmd(self, ctx: commands.Context, prompt, *options):
        if len(options) > 10:
            raise ValueError('Too many options!')
        if len(options) < 1:
            raise ValueError('Not enough options!')
        nopt = len(options)
        emojis = [f'{i + 1}\u20e3' if i < 10 else '\U0001f51f' for i in range(nopt)]
        content = f'Vote using emoji reactions.  You have {self.TIMEOUT:d} seconds from when the last option appears.  ' \
                  f'Max one vote per user.  To change your vote, clear your original selection first.'
        while len(emojis) > 1:
            count, emojis, options = await self.do_poll(ctx, prompt, emojis, options, content=content)
            content = f'SUDDEN DEATH between {len(emojis)} options'
        await ctx.send(f'Winner: {emojis[0]}: {options[0]}')

    async def __error(self, ctx, exc):
        await ctx.send(f'**{exc.__class__.__name__}:** {exc}')
        self.log_tb(ctx, exc)


def setup(bot):
    bot.add_cog(Poll(bot))
