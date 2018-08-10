import asyncio
import discord
import datetime
from discord.ext import commands
from cogs import Cog


class Poll(Cog):
    TIMEOUT = 60.0

    async def do_poll(self, ctx, prompt, emojis, options, content=None):
        description = '\n'.join(f'{emoji}: {option}' for emoji, option in zip(emojis, options))
        embed = discord.Embed(title=prompt, description=description)
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar_url)
        msg: discord.Message = await ctx.send(content, embed=embed)
        for emoji in emojis:
            await msg.add_reaction(emoji)
        await asyncio.sleep(self.TIMEOUT)
        for emoji in emojis:
            await msg.remove_reaction(emoji, self.bot.user)
        msg = await ctx.channel.get_message(msg.id)
        votes = [rxn.count for rxn in msg.reactions if rxn.emoji in emojis]
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
        content = f'Vote using emoji reactions.  You have {self.TIMEOUT:d} seconds from when the last option appears.'
        while len(emojis) > 1:
            count, emojis, options = await self.do_poll(ctx, prompt, emojis, options, content=content)
            content = f'SUDDEN DEATH between {len(emojis)} options'
        await ctx.send(f'Winner: {emojis[0]}: {options[0]}')


def setup(bot):
    bot.add_cog(Poll(bot))
