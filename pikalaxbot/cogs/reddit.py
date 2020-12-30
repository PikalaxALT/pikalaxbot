import aiohttp
import platform
import datetime
import traceback

import discord
from discord.ext import commands, menus

from . import BaseCog

from .. import __version__


class NoPostsFound(commands.CommandError):
    def __init__(self, subreddit, message=None, *args):
        super().__init__(message=message, *args)
        self.subreddit = subreddit


class SubredditNotFound(commands.CommandError):
    def __init__(self, subreddit, message=None, *args):
        super().__init__(message=message, *args)
        self.subreddit = subreddit


class RedditErrorPageSource(menus.ListPageSource):
    def __init__(self, ctx, error):
        paginator = commands.Paginator()
        paginator.add_line(f'command {ctx.command}')
        for line in traceback.format_exception(error.__class__, error, error.__traceback__):
            paginator.add_line(line.rstrip('\n'))
        super().__init__(paginator.pages, per_page=1)
        self.embed = discord.Embed(title='Command error details')
        self.embed.add_field(name='Author', value=ctx.author.mention, inline=False)
        if ctx.guild:
            self.embed.add_field(name='Channel', value=ctx.channel.mention, inline=False)
        self.embed.add_field(name='Invoked with', value='`' + ctx.message.content + '`', inline=False)
        self.embed.add_field(name='Invoking message', value=ctx.message.jump_url if ctx.guild else "is a dm",
                             inline=False)

    def format_page(self, menu, page):
        return {'content': page, 'embed': self.embed}


class Reddit(BaseCog):
    """Commands for yoinking image posts off of Reddit."""

    def __init__(self, bot):
        super().__init__(bot)
        self.session: aiohttp.ClientSession = bot.client_session

    @property
    def headers(self):
        return {'user-agent': f'{platform.platform()}:{self.bot.user.name}:{__version__} (by /u/pikalaxalt)'}

    async def get_reddit(self, endpoint):
        async with self.session.get(f'https://reddit.com/{endpoint}', headers=self.headers, raise_for_status=True) as r:
            resp = await r.json()
        return resp

    async def fetch_subreddit_info(self, subreddit):
        resp = await self.get_reddit(f'r/{subreddit}/about.json')
        return resp['data']

    async def fetch_random_reddit_post(self, subreddit):
        resp = await self.get_reddit(f'r/{subreddit}/random.json')
        if isinstance(resp, dict):
            raise SubredditNotFound(subreddit)
        return resp[0]['data']['children'][0]['data']

    def cog_check(self, ctx):
        return ctx.guild.id not in self.bot.settings.banned_guilds

    async def get_subreddit_embed(self, ctx, subreddit):
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
        title = child['title']
        sub_prefixed = child['subreddit_name_prefixed']
        author = child['author']
        permalink = child['permalink']
        score = child['score']
        upvote_emoji = discord.utils.get(self.bot.emojis, name='upvote')
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
            source = RedditErrorPageSource(ctx, error)
            menu = menus.MenuPages(source)
            await menu.start(ctx, channel=self.bot.exc_channel)


def setup(bot):
    bot.add_cog(Reddit(bot))
