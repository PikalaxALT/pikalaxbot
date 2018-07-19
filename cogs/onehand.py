import asyncio
import aiohttp
import discord
import io
import os
from discord.ext import commands
from cogs import Cog


class OneHand(Cog):
    async def __local_check(self, ctx: commands.Context):
        return isinstance(ctx.channel, discord.TextChannel) and ctx.channel.is_nsfw()

    def __init__(self, bot):
        super().__init__(bot)
        self._cs = aiohttp.ClientSession(raise_for_status=True)

    def __del__(self):
        task = self.bot.loop.create_task(self._cs.close())
        asyncio.wait([task])

    @commands.command()
    @commands.bot_has_permissions(embed_links=True)
    async def e6(self, ctx: commands.Context, *params):
        """Search for up to 5 images on e621 with the given tags.  The number of images to return must come last."""
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

    @e6.error
    async def e6_error(self, ctx: commands.Context, exc: Exception):
        if isinstance(exc, aiohttp.ClientError):
            await ctx.send(f'Could not reach e621: {exc}')

    @commands.command()
    @commands.bot_has_permissions(attach_files=True)
    async def inspire(self, ctx: commands.Context):
        """Generate an inspirational poster using inspirobot.me"""
        r = await self._cs.get('http://inspirobot.me/api', params={'generate': 'true'})
        url = await r.text()
        r = await self._cs.get(url)
        stream = io.BytesIO(await r.read())
        await ctx.send(file=discord.file.File(stream, os.path.basename(url)))

    @inspire.error
    async def inspire_error(self, ctx, exc):
        if isinstance(exc, aiohttp.ClientError):
            await ctx.send(f'Could not reach inspirobot.me: {exc}')

    async def __error(self, ctx:commands.Context, exc: Exception):
        if isinstance(exc, commands.BotMissingPermissions):
            await ctx.send(exc)
        elif isinstance(exc, commands.CheckFailure):
            await ctx.send('This command is age-restricted and cannot be used in this channel.')


def setup(bot):
    bot.add_cog(OneHand(bot))
