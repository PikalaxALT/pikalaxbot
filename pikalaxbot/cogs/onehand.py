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
import io
import os

import discord
from discord.ext import commands

from . import BaseCog
from .utils.errors import CommandBannedInGuild


class Onehand(BaseCog):
    banned_guilds = set()
    global_blacklist = {'cub', 'shota', 'loli', 'young'}
    my_blacklist = set()
    config_attrs = 'banned_guilds', 'my_blacklist'

    async def cog_check(self, ctx: commands.Context):
        if ctx.command == self.oklewd:
            return True
        if ctx.guild is None:
            return True
        if ctx.guild.id in self.banned_guilds:
            raise CommandBannedInGuild('Lewd commands are banned in this guild.')
        return True

    async def get_bad_dragon(self, ctx: commands.Context, name, *params):
        try:
            num = min(max(int(params[-1]), 1), 5)
            params = params[:-1]
        except ValueError:
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
        async with aiohttp.ClientSession(raise_for_status=True) as cs:
            async with cs.get(
                    f'https://{name}.net/posts.json',
                    headers={'User-Agent': self.bot.user.name},
                    params={'tags': ' '.join(params), 'limit': 100}
            ) as r:
                resp = (await r.json())['posts']
                j = [post for i, post in zip(range(num), (await r.json())['posts']) if not any(blacklist & set(value) for value in post['tags'].values())]
        upvote_emoji = discord.utils.get(self.bot.emojis, name='upvote')
        downvote_emoji = discord.utils.get(self.bot.emojis, name='downvote')
        num_sent = 0
        for imagespec in resp:
            if not any(blacklist & set(value) for value in imagespec['tags'].values()):
                filespec = discord.utils.find(lambda x: x['url'], (imagespec['file'], imagespec['sample'], imagespec['preview']))
                if not filespec:
                    continue
                score = imagespec['score']['total']
                upvotes = imagespec['score']['up']
                downvotes = imagespec['score']['down']
                width = filespec['width']
                height = filespec['height']
                pic_id = imagespec['id']
                file_ext = imagespec['file']['ext']
                if file_ext in ('webm', 'swf'):
                    description = f'**Score:** {score} ({upvotes}{upvote_emoji}/{downvotes}{downvote_emoji}) | ' \
                                  f'**Link:** [Click Here](https://{name}.net/post/show/{pic_id})\n' \
                                  f'*This file ({file_ext}) cannot be previewed or embedded.*'
                else:
                    description = f'**Score:** {score} ({upvotes}{upvote_emoji}/{downvotes}{downvote_emoji}) | ' \
                                  f'**Resolution:** {width} x {height} | ' \
                                  f'[Link](https://{name}.net/post/show/{pic_id})'
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
    async def e6(self, ctx: commands.Context, *params):
        """Search for up to 5 images on e621 with the given tags.  The number of images to return must come last."""
        await self.get_bad_dragon(ctx, 'e621', *params)

    @e6.error
    async def e6_error(self, ctx: commands.Context, exc: Exception):
        if isinstance(exc, aiohttp.ClientError):
            await ctx.send(f'Could not reach e621: {exc}',
                           delete_after=10)
        else:
            await ctx.send(f'**{exc.__class__.__name__}**: {exc}')

    @commands.command(aliases=['e926'])
    @commands.bot_has_permissions(embed_links=True)
    @commands.cooldown(1, 5, commands.BucketType.channel)
    async def e9(self, ctx: commands.Context, *params):
        """Search for up to 5 images on e926 with the given tags.  The number of images to return must come last."""
        await self.get_bad_dragon(ctx, 'e926', *params)

    @e9.error
    async def e9_error(self, ctx: commands.Context, exc: Exception):
        if isinstance(exc, aiohttp.ClientError):
            await ctx.send(f'Could not reach e926: {exc}',
                           delete_after=10)

    @commands.command()
    @commands.is_owner()
    async def nolewd(self, ctx, *, guild: discord.Guild = None):
        if guild is None:
            guild = ctx.guild
        if guild.id in self.banned_guilds:
            await ctx.send(f'Guild "{guild}" is already marked safe', delete_after=10)
        else:
            self.banned_guilds.add(guild.id)
            await ctx.message.add_reaction('✅')

    @commands.command()
    @commands.is_owner()
    async def oklewd(self, ctx, *, guild: discord.Guild = None):
        if guild is None:
            guild = ctx.guild
        if guild.id not in self.banned_guilds:
            await ctx.send(f'Guild "{guild}" is not marked safe', delete_after=10)
        else:
            self.banned_guilds.remove(guild.id)
            await ctx.message.add_reaction('✅')

    @commands.group()
    async def blacklist(self, ctx):
        pass

    @blacklist.command(name='add')
    async def blacklist_add(self, ctx, *tags):
        self.my_blacklist.update(tags)
        await ctx.message.add_reaction('✅')

    @blacklist.command(name='remove')
    async def blacklist_remove(self, ctx, *tags):
        self.my_blacklist.difference_update(tags)
        await ctx.message.add_reaction('✅')

    @blacklist.command(name='clear')
    async def blacklist_clear(self, ctx):
        self.my_blacklist = set()
        await ctx.message.add_reaction('✅')

    @blacklist.command(name='show')
    async def blacklist_show(self, ctx):
        glb = ', '.join(self.global_blacklist)
        loc = ', '.join(self.my_blacklist)
        await ctx.send(f'The following tags are blacklisted globally: `{glb}`\n'
                       f'The following additional tags are also blacklisted:\n'
                       f'`{loc}`')

    @commands.command()
    @commands.bot_has_permissions(attach_files=True)
    async def inspire(self, ctx: commands.Context):
        """Generate an inspirational poster using inspirobot.me"""
        async with aiohttp.ClientSession(raise_for_status=True) as cs:
            async with cs.get('http://inspirobot.me/api', params={'generate': 'true'}) as r:
                url = await r.text()
            async with cs.get(url) as r:
                stream = io.BytesIO(await r.read())
        await ctx.send(file=discord.file.File(stream, os.path.basename(url)))

    @inspire.error
    async def inspire_error(self, ctx, exc):
        if isinstance(exc, aiohttp.ClientError):
            await ctx.send(f'Could not reach inspirobot.me: {exc}',
                           delete_after=10)

    async def cog_command_error(self, ctx: commands.Context, exc: Exception):
        if isinstance(exc, commands.BotMissingPermissions):
            await ctx.send(f'{exc}')
        elif isinstance(exc, (commands.NSFWChannelRequired, CommandBannedInGuild)):
            await ctx.send('This command is age-restricted and cannot be used in this channel.',
                           delete_after=10)
        else:
            self.log_tb(ctx, exc)


def setup(bot):
    bot.add_cog(Onehand(bot))
