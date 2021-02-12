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

import aiohttp
import platform
import datetime
import typing

import discord
from discord.ext import commands

from . import *

from .. import __version__


class NoPostsFound(commands.CommandError):
    def __init__(self, subreddit: str, message=None, *args):
        super().__init__(message=message, *args)
        self.subreddit = subreddit


class SubredditNotFound(commands.CommandError):
    def __init__(self, subreddit: str, message=None, *args):
        super().__init__(message=message, *args)
        self.subreddit = subreddit


class Reddit(BaseCog):
    """Commands for yoinking image posts off of Reddit."""

    def __init__(self, bot):
        super().__init__(bot)
        self.session = bot.client_session

    @discord.utils.cached_property
    def headers(self):
        return {'user-agent': f'{platform.platform()}:{self.bot.user.name}:{__version__} (by /u/pikalaxalt)'}

    async def get_reddit(self, endpoint: str) -> dict:
        async with self.session.get(f'https://reddit.com/{endpoint}', headers=self.headers, raise_for_status=True) as r:
            resp = await r.json()
        return resp

    async def fetch_subreddit_info(self, subreddit: str) -> dict[str, typing.Any]:
        resp = await self.get_reddit(f'r/{subreddit}/about.json')
        return resp['data']

    async def fetch_random_reddit_post(self, subreddit: str) -> dict[str, typing.Any]:
        resp = await self.get_reddit(f'r/{subreddit}/random.json')
        if isinstance(resp, dict):
            raise SubredditNotFound(subreddit)
        return resp[0]['data']['children'][0]['data']

    def cog_check(self, ctx: MyContext) -> bool:
        return ctx.guild.id not in self.bot.settings.banned_guilds

    async def get_subreddit_embed(self, ctx: MyContext, subreddit: str):
        min_creation = ctx.message.created_at - datetime.timedelta(hours=3)

        subinfo = await self.fetch_subreddit_info(subreddit)
        if subinfo['over18'] and not (ctx.guild and ctx.channel.is_nsfw()):
            raise commands.NSFWChannelRequired(ctx.channel)

        def check(post):
            return (post['approved_at_utc'] or datetime.datetime.fromtimestamp(post['created_utc']) <= min_creation) \
                and post['score'] >= 10 \
                and (not post['over_18'] or not (ctx.guild and ctx.channel.is_nsfw())) \
                and not post['spoiler']

        for attempt in range(10):
            child = await self.fetch_random_reddit_post(subreddit)
            if not check(child):
                continue
            if child.get('url_overridden_by_dest') and not child.get('is_video') and not child.get('media'):
                break
        else:
            raise NoPostsFound(subreddit)
        title: str = child['title']
        sub_prefixed: str = child['subreddit_name_prefixed']
        author: str = child['author']
        permalink: str = child['permalink']
        score: int = child['score']
        upvote_emoji: discord.Emoji = discord.utils.get(self.bot.emojis, name='upvote')
        embed = discord.Embed(
            title=f'/{sub_prefixed}',
            description=f'[{title}](https://reddit.com{permalink})\n'
                        f'Score: {score}{upvote_emoji}',
            url=f'https://reddit.com/{sub_prefixed}',
            colour=discord.Colour.dark_orange(),
            timestamp=datetime.datetime.fromtimestamp(child['created_utc'])
        )
        embed.set_image(url=child['url'])
        embed.set_author(name=f'/u/{author}', url=f'https://reddit.com/u/{author}')
        return embed

    @commands.command(name='reddit', aliases=['sub'])
    async def get_subreddit(self, ctx: MyContext, subreddit: str):
        """Randomly fetch an image post from the given subreddit."""
        async with ctx.typing():
            embed = await self.get_subreddit_embed(ctx, subreddit)
        await ctx.send(embed=embed)

    @commands.command()
    async def beans(self, ctx: MyContext):
        """Gimme my beans reeeeeeeeeeeeee"""
        await self.get_subreddit(ctx, 'beans')

    async def cog_command_error(self, ctx: MyContext, error: commands.CommandError):
        error = getattr(error, 'original', error)
        if isinstance(error, aiohttp.ClientResponseError):
            await ctx.send(f'An unhandled HTTP exception occurred: {error.status}: {error.message}')
        elif isinstance(error, SubredditNotFound):
            await ctx.send(f'Hmm... I can\'t seem to find r/{error.subreddit}')
        elif isinstance(error, NoPostsFound):
            await ctx.send(f'Hmm... I seem to be out of {error.subreddit} right now')
        elif isinstance(error, commands.NSFWChannelRequired):
            await ctx.send('That subreddit is too spicy for this channel!')
        elif isinstance(error, commands.CheckFailure):
            pass
        else:
            await ctx.send(f'An unhandled internal exception occurred: {error.__class__.__name__}: {error}')
            await self.bot.get_cog('ErrorHandling').send_tb(ctx, error)


def setup(bot: PikalaxBOT):
    bot.add_cog(Reddit(bot))
