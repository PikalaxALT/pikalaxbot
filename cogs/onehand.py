import asyncio
import aiohttp
import discord
import io
import os
from discord.ext import commands
from cogs import Cog


TPPServer = discord.Object(148079346685313034)


class OneHand(Cog):
    async def __local_check(self, ctx: commands.Context):
        return ctx.guild.id != TPPServer.id

    async def get_bad_dragon(self, ctx: commands.Context, name, *params):
        try:
            num = min(max(int(params[-1]), 1), 5)
            params = params[:-1]
        except ValueError:
            num = 1
        tags = ' '.join(params)
        if not any(param.startswith('order:') for param in params):
            params += 'order:random',
        r = await self.cs.get(
            f'https://{name}.net/post/index.json',
            headers={'User-Agent': self.bot.user.name},
            params={'tags': ' '.join(params), 'limit': num}
        )
        j = await r.json()
        if j:
            for imagespec in j:
                score = imagespec['score']
                width = imagespec['width']
                height = imagespec['height']
                pic_id = imagespec['id']
                file_ext = imagespec['file_ext']
                if file_ext in ('webm', 'swf'):
                    description = f'**Score:** {score} | ' \
                                  f'**Link:** [Click Here](https://{name}.net/post/show/{pic_id})\n' \
                                  f'*This file ({file_ext}) cannot be previewed or embedded.*'
                else:
                    description = f'**Score:** {score} | ' \
                                  f'**Resolution:** {width} x {height} | ' \
                                  f'**Link:** [Click Here](https://{name}.net/post/show/{pic_id})'
                color = discord.Color.from_rgb(1, 46, 87)
                embed = discord.Embed(color=color, description=description)
                embed.set_author(name=tags, icon_url=ctx.author.avatar_url)
                embed.set_image(url=imagespec['file_url'])
                embed.set_footer(text=name, icon_url='http://i.imgur.com/RrHrSOi.png')
                await ctx.send(embed=embed)
        else:
            await ctx.send(f':warning: | No results for: `{tags}`')

    @commands.command()
    @commands.is_nsfw()
    @commands.bot_has_permissions(embed_links=True)
    async def e6(self, ctx: commands.Context, *params):
        """Search for up to 5 images on e621 with the given tags.  The number of images to return must come last."""
        await self.get_bad_dragon(ctx, 'e621', *params)

    @e6.error
    async def e6_error(self, ctx: commands.Context, exc: Exception):
        if isinstance(exc, aiohttp.ClientError):
            await ctx.send(f'Could not reach e621: {exc}',
                           delete_after=10)

    @commands.command()
    @commands.bot_has_permissions(embed_links=True)
    async def e9(self, ctx: commands.Context, *params):
        """Search for up to 5 images on e926 with the given tags.  The number of images to return must come last."""
        await self.get_bad_dragon(ctx, 'e926', *params)

    @e9.error
    async def e9_error(self, ctx: commands.Context, exc: Exception):
        if isinstance(exc, aiohttp.ClientError):
            await ctx.send(f'Could not reach e926: {exc}',
                           delete_after=10)

    @commands.command()
    @commands.bot_has_permissions(attach_files=True)
    async def inspire(self, ctx: commands.Context):
        """Generate an inspirational poster using inspirobot.me"""
        r = await self.cs.get('http://inspirobot.me/api', params={'generate': 'true'})
        url = await r.text()
        r = await self.cs.get(url)
        stream = io.BytesIO(await r.read())
        await ctx.send(file=discord.file.File(stream, os.path.basename(url)))

    @inspire.error
    async def inspire_error(self, ctx, exc):
        if isinstance(exc, aiohttp.ClientError):
            await ctx.send(f'Could not reach inspirobot.me: {exc}',
                           delete_after=10)

    async def __error(self, ctx:commands.Context, exc: Exception):
        if isinstance(exc, commands.BotMissingPermissions):
            await ctx.send(exc)
        elif isinstance(exc, commands.CheckFailure):
            await ctx.send('This command is age-restricted and cannot be used in this channel.',
                           delete_after=10)
        else:
            self.log_tb(ctx, exc)


def setup(bot):
    bot.add_cog(OneHand(bot))
