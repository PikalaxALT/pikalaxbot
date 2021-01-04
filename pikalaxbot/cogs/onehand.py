# PikalaxBOT - A Discord bot in discord.py
# Copyright (C) 2018  PikalaxALT
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
import operator

import discord
from discord.ext import commands

from . import *
from .utils.errors import CommandBannedInGuild


class Onehand(BaseCog):
    """Lewd commands owo"""

    banned_guilds: set[int] = set()
    global_blacklist = {'cub', 'shota', 'loli', 'young'}
    my_blacklist: set[str] = set()
    e6_api_key = ''
    config_attrs = 'banned_guilds', 'my_blacklist', 'e6_api_key'

    async def cog_check(self, ctx: MyContext):
        if ctx.command == self.oklewd:
            return True
        if ctx.guild is None:
            return True
        if ctx.guild.id in self.banned_guilds:
            raise CommandBannedInGuild('Lewd commands are banned in this guild.')
        return True

    async def get_bad_dragon(self, ctx: MyContext, name: str, *params: str):
        try:
            num = min(max(int(params[-1]), 1), 5)
            params = params[:-1]
        except (ValueError, IndexError):
            num = 1
        blacklist = self.global_blacklist.union(self.my_blacklist)
        params = set(params)
        params.difference_update(blacklist)
        if not params:
            await ctx.send('Empty query (no non-blacklisted tags)')
            return
        tags = ' '.join(params)
        if not any(param.startswith('order:') for param in params):
            params.add('order:random')
        async with self.bot.client_session.get(
                f'https://{name}.net/posts.json',
                headers={'User-Agent': self.bot.user.name},
                params={'tags': ' '.join(params), 'limit': 100, 'login': 'pikalaxalt', 'api_key': self.e6_api_key}
        ) as r:
            resp = (await r.json())['posts']
            j = [post for i, post in zip(range(num), (await r.json())['posts']) if not any(blacklist & set(value) for value in post['tags'].values())]
        upvote_emoji = discord.utils.get(self.bot.emojis, name='upvote')
        downvote_emoji = discord.utils.get(self.bot.emojis, name='downvote')
        num_sent = 0
        for imagespec in resp:
            if not any(blacklist & set(value) for value in imagespec['tags'].values()):
                filespec = discord.utils.find(operator.itemgetter('url'), (imagespec['file'], imagespec['sample'], imagespec['preview']))
                if not filespec:
                    print(imagespec['id'])
                    continue
                score = imagespec['score']['total']
                upvotes = imagespec['score']['up']
                downvotes = imagespec['score']['down']
                width = filespec['width']
                height = filespec['height']
                pic_id = imagespec['id']
                file_ext = imagespec['file']['ext']
                if file_ext in {'webm', 'swf'}:
                    description = f'**Score:** {score} ({upvotes}{upvote_emoji}/{downvotes}{downvote_emoji}) | ' \
                                  f'**Link:** [Click Here](https://{name}.net/posts/{pic_id}?q={tags.replace(" ", "+")})\n' \
                                  f'*This file ({file_ext}) cannot be previewed or embedded.*'
                else:
                    description = f'**Score:** {score} ({upvotes}{upvote_emoji}/{downvotes}{downvote_emoji}) | ' \
                                  f'**Resolution:** {width} x {height} | ' \
                                  f'[Link](https://{name}.net/posts/{pic_id}?q={tags.replace(" ", "+")})'
                color = discord.Color.from_rgb(1, 46, 87)
                embed = discord.Embed(color=color, description=description)
                embed.set_author(name=tags, icon_url=ctx.author.avatar_url)
                embed.set_image(url=filespec['url'])
                embed.set_footer(text=f'{name} - {num_sent + 1}/{len(j)}', icon_url='http://i.imgur.com/RrHrSOi.png')
                await ctx.send(embed=embed)
                num_sent += 1
                if num_sent >= num:
                    break
        if not num_sent:
            await ctx.send(f':warning: | No results for: `{tags}`')

    @commands.command(aliases=['e621'])
    @commands.is_nsfw()
    @commands.bot_has_permissions(embed_links=True)
    @commands.cooldown(1, 5, commands.BucketType.channel)
    async def e6(self, ctx: MyContext, *params: str):
        """Search for up to 5 images on e621 with the given tags.  The number of images to return must come last."""

        await self.get_bad_dragon(ctx, 'e621', *params)

    @commands.command(aliases=['e926'])
    @commands.is_nsfw()
    @commands.bot_has_permissions(embed_links=True)
    @commands.cooldown(1, 5, commands.BucketType.channel)
    async def e9(self, ctx: MyContext, *params: str):
        """Search for up to 5 images on e926 with the given tags.  The number of images to return must come last."""

        await self.get_bad_dragon(ctx, 'e926', *params)

    @e6.error
    @e9.error
    async def e9_error(self, ctx: MyContext, exc: commands.CommandError):
        dest = 'e621' if ctx.command == self.e6 else 'e926'
        if isinstance(exc, aiohttp.ClientError):
            await ctx.send(f'Could not reach {dest}: {exc}',
                           delete_after=10)
        else:
            await ctx.send(f'Unhandled exception in {dest}: **{exc.__class__.__name__}**: {exc}')

    @commands.command()
    @commands.is_owner()
    async def nolewd(self, ctx: MyContext, *, guild: discord.Guild = None):
        """Blacklist commands that have the potential to return questionable content in this guild."""

        guild = guild or ctx.guild
        if guild.id in self.banned_guilds:
            await ctx.send(f'Guild "{guild}" is already marked safe', delete_after=10)
        else:
            self.banned_guilds.add(guild.id)
            await ctx.message.add_reaction('✅')

    @commands.command()
    @commands.is_owner()
    async def oklewd(self, ctx: MyContext, *, guild: discord.Guild = None):
        """Whitelist commands that have the potential to return questionable content in this guild."""

        guild = guild or ctx.guild
        if guild.id not in self.banned_guilds:
            await ctx.send(f'Guild "{guild}" is not marked safe', delete_after=10)
        else:
            self.banned_guilds.remove(guild.id)
            await ctx.message.add_reaction('✅')

    @commands.group()
    async def blacklist(self, ctx: MyContext):
        """Manage the e621/e926 tags blacklist"""

        pass

    @blacklist.command(name='add')
    async def blacklist_add(self, ctx: MyContext, *tags: str):
        """Add the tags to the blacklist"""

        self.my_blacklist.update(tags)
        await ctx.message.add_reaction('✅')

    @blacklist.command(name='remove')
    async def blacklist_remove(self, ctx: MyContext, *tags: str):
        """Remove the tags from the blacklist"""

        self.my_blacklist.difference_update(tags)
        await ctx.message.add_reaction('✅')

    @blacklist.command(name='clear')
    async def blacklist_clear(self, ctx: MyContext):
        """Delete the blacklisted tags"""

        self.my_blacklist.clear()
        await ctx.message.add_reaction('✅')

    @blacklist.command(name='show')
    async def blacklist_show(self, ctx: MyContext):
        """Show the blacklisted tags"""

        glb = ', '.join(self.global_blacklist)
        loc = ', '.join(self.my_blacklist)
        await ctx.send(f'The following tags are blacklisted globally: `{glb}`\n'
                       f'The following additional tags are also blacklisted:\n'
                       f'`{loc}`')

    @commands.command()
    @commands.bot_has_permissions(attach_files=True)
    async def inspire(self, ctx: MyContext):
        """Generate an inspirational poster using inspirobot.me"""

        async with self.bot.client_session.get('http://inspirobot.me/api', params={'generate': 'true'}) as r:
            url = await r.text()
        await ctx.send(url)

    @inspire.error
    async def inspire_error(self, ctx: MyContext, exc: commands.CommandError):
        if isinstance(exc, aiohttp.ClientError):
            await ctx.send(f'Could not reach inspirobot.me: {exc}',
                           delete_after=10)

    async def cog_command_error(self, ctx: MyContext, exc: commands.CommandError):
        if isinstance(exc, commands.BotMissingPermissions):
            await ctx.send(f'{exc}')
        elif isinstance(exc, (commands.NSFWChannelRequired, CommandBannedInGuild)):
            await ctx.send('This command is age-restricted and cannot be used in this channel.',
                           delete_after=10)
        elif isinstance(exc, commands.MissingRequiredArgument):
            await ctx.send(f'{exc}')
        else:
            self.log_tb(ctx, exc)


def setup(bot):
    bot.add_cog(Onehand(bot))
