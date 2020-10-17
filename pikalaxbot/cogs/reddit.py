import random
import aiohttp
import typing
import platform
import datetime
import os

import discord
from discord.ext import commands

from . import BaseCog
from .utils.data import data

__dir__ = os.path.dirname(os.path.dirname(__file__)) or '.'
with open(os.path.join(os.path.dirname(__dir__), 'version.txt')) as fp:
    __version__ = fp.read().strip()


class Reddit(BaseCog):
    def __init__(self, bot):
        super().__init__(bot)
        self.session: typing.Optional[aiohttp.ClientSession] = None

        async def create_session():
            self.session = aiohttp.ClientSession(raise_for_status=True)

        bot.loop.create_task(create_session())

    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())

    async def get_subreddit_embed(self, ctx, subreddit):
        headers = {'user-agent': f'{platform.platform()}:{self.bot.user.name}:{__version__} (by /u/pikalaxalt)'}
        min_creation = ctx.message.created_at - datetime.timedelta(hours=3)

        def check(post):
            return (post['approved_at_utc'] or datetime.datetime.fromtimestamp(post['created_utc']) <= min_creation) \
                and post['score'] >= 10 \
                and (not post['over_18'] or ctx.channel.is_nsfw()) \
                and not post['spoiler']

        for attempt in range(10):
            async with self.session.get(f'https://reddit.com/r/{subreddit}/random.json', headers=headers) as r:
                resp = await r.json()
                if isinstance(resp, dict):
                    raise aiohttp.ClientResponseError(status=404, message=f'No subreddit named "{subreddit}"', history=(r,), request_info=r.request_info)
            child = resp[0]['data']['children'][0]['data']
            if not check(child):
                continue
            if child.get('url_overridden_by_dest') and not child.get('is_video') and not child.get('media'):
                break
        else:
            return await ctx.send(f'Hmm... I seem to be out of {subreddit} right now')
        author = child['author']
        permalink = child['permalink']
        score = child['score']
        upvote_emoji = discord.utils.get(self.bot.emojis, name='upvote')
        embed = discord.Embed(
            title=child['title'],
            description=f'Score: {score}{upvote_emoji}',
            url=f'https://reddit.com{permalink}',
            colour=discord.Colour.dark_orange(),
            timestamp=datetime.datetime.fromtimestamp(child['created_utc'])
        )
        embed.set_image(url=child['url'])
        embed.set_author(name=f'/u/{author}', url=f'https://reddit.com/u/{author}')
        return embed

    @commands.command(name='reddit', aliases=['sub'])
    async def get_subreddit(self, ctx, subreddit):
        """Randomly fetch an image post from the given subreddit."""
        async with ctx.typing():
            embed = await self.get_subreddit_embed(ctx, subreddit)
        await ctx.send(embed=embed)

    @commands.command()
    async def beans(self, ctx):
        """Gimme my beans reeeeeeeeeeeeee"""
        await self.get_subreddit(ctx, 'beans')

    async def cog_command_error(self, ctx, error):
        error = getattr(error, 'original', error)
        if isinstance(error, aiohttp.ClientResponseError):
            if error.status == 404:
                await ctx.send('I cannot find that subreddit!')
            else:
                await ctx.send(f'An unhandled HTTP exception occurred: {error.status}: {error.message}')
        elif isinstance(error, commands.CheckFailure):
            pass
        else:
            await ctx.send(f'An unhandled internal exception occurred: {error.__class__.__name__}: {error}')


def setup(bot):
    bot.add_cog(Reddit(bot))
