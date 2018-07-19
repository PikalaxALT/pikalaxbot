import asyncio
import aiohttp
import discord
from discord.ext import commands
from cogs import Cog


class OneHand(Cog):
    async def __local_check(self, ctx: commands.Context):
        return isinstance(ctx.channel, discord.TextChannel) and ctx.channel.is_nsfw()

    def __init__(self, bot):
        super().__init__(bot)
        self._cs = aiohttp.ClientSession(raise_for_status=True)

    @commands.command()
    async def e6(self, ctx: commands.Context, *params):
        try:
            num = min(max(int(params[-1]), 1), 5)
            params = params[:-1]
        except ValueError:
            num = 1
        tags = ' '.join(params)
        if not any(param.startswith('order:') for param in params):
            params += 'order:random',
        r = await self._cs.get('https://e621.net/post/index.json',
                               headers={'User-Agent': 'PikalaxBOT'},
                               params={'tags': ' '.join(params), 'limit': num})
        j = await r.json()
        for imagespec in j:
            score = imagespec['score']
            width = imagespec['width']
            height = imagespec['height']
            pic_id = imagespec['id']
            description = f'**Score:** {score} | ' \
                          f'**Resolution:** {width} x {height} | ' \
                          f'**Link:** [Click Here](https://e621.net/post/show/{pic_id})'
            color = discord.Color.from_rgb(1, 46, 87)
            embed = discord.Embed(color=color, description=description)
            embed.set_author(name=tags, icon_url=ctx.author.avatar_url)
            embed.set_image(url=imagespec['file_url'])
            embed.set_footer(text='e621', icon_url='http://i.imgur.com/RrHrSOi.png')
            await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(OneHand(bot))
