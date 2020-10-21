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

import discord
from discord.ext import commands
from humanize import naturaltime, precisedelta
import resource
import typing
import inspect
import os
import datetime
from jishaku.meta import __version__ as jsk_ver

from . import BaseCog
from .utils.errors import *
from .utils.converters import CommandConverter


class Core(BaseCog):
    banlist = set()
    game = 'p!help'
    config_attrs = 'banlist', 'game'

    async def bot_check(self, ctx: commands.Context):
        if not self.bot.is_ready():
            raise NotReady('The bot is not ready to process commands')
        if not ctx.channel.permissions_for(ctx.me).send_messages:
            raise commands.BotMissingPermissions(['send_messages'])
        if isinstance(ctx.command, commands.Command) and await self.bot.is_owner(ctx.author):
            return True
        if ctx.author.id in self.banlist:
            raise BotIsIgnoringUser(f'I am ignoring {ctx.author}')
        return True

    @commands.command(aliases=['reboot'])
    @commands.is_owner()
    async def kill(self, ctx: commands.Context):
        """Shut down the bot (owner only, manual restart required)"""

        self.bot.reboot_after = ctx.invoked_with == 'reboot'
        await ctx.send('Rebooting to apply updates')
        await self.bot.logout()

    @commands.command()
    @commands.is_owner()
    async def ignore(self, ctx, person: discord.Member):
        """Ban a member from using the bot :datsheffy:"""

        self.banlist.add(person.id)
        await ctx.send(f'{person.display_name} is now banned from interacting with me.')

    @commands.command()
    @commands.is_owner()
    async def unignore(self, ctx, person: discord.Member):
        """Unban a member from using the bot"""

        self.banlist.discard(person.id)
        await ctx.send(f'{person.display_name} is no longer banned from interacting with me.')

    @commands.command()
    async def about(self, ctx):
        """Shows info about the bot in the current context"""

        tz = datetime.datetime.now() - datetime.datetime.utcnow()
        e = discord.Embed()
        shared = sum(g.get_member(ctx.author.id) is not None for g in self.bot.guilds)
        e.set_author(name=str(ctx.me))
        e.add_field(name='ID', value=ctx.me.id, inline=False)
        e.add_field(name='Guilds', value=f'{len(self.bot.guilds)} ({shared} shared)', inline=False)
        if ctx.guild:
            e.add_field(name='Joined', value=naturaltime(ctx.me.joined_at + tz), inline=False)
        e.add_field(name='Created', value=naturaltime(ctx.me.created_at + tz), inline=False)
        if ctx.guild:
            roles = [r.name.replace('@', '@\u200b') for r in ctx.me.roles]
            e.add_field(name='Roles', value=', '.join(roles) if len(roles) < 10 else f'{len(roles)} roles', inline=False)
        e.add_field(name='Source', value='https://github.com/PikalaxALT/pikalaxbot')
        e.add_field(name='Uptime', value=f'{datetime.datetime.utcnow() - self.bot._alive_since}')
        if ctx.guild and ctx.me.colour.value:
            e.colour = ctx.me.colour
        if ctx.me.avatar:
            e.set_thumbnail(url=ctx.me.avatar_url)
        await ctx.send(embed=e)

    @commands.command(aliases=['src'])
    async def source(self, ctx, *, command: typing.Optional[CommandConverter]):
        """Links the source of the command. If command source cannot be retrieved,
        links the root of the bot's source tree."""

        url = 'https://github.com/PikalaxALT/pikalaxbot'
        branch = 'master'
        if command is not None:
            if command.name == 'help':
                obj = type(self.bot.help_command)
                src = inspect.getsourcefile(obj)
                module = obj.__module__.replace('.', os.path.sep)
            else:
                obj = command.callback
                src = obj.__code__.co_filename
                module = obj.__module__.replace('.', os.path.sep)
            if module in src:
                lines, start = inspect.getsourcelines(obj)
                sourcefile = src[src.index(module):].replace('\\', '/')
                end = start + len(lines) - 1
                if command.cog and command.cog.__cog_name__ == 'Jishaku':
                    url = 'https://github.com/Gorialis/jishaku'
                    branch = jsk_ver
                elif sourcefile.startswith('discord/'):
                    url = 'https://github.com/Rapptz/discord.py'
                    branch = f'v{discord.__version__}'
                url = f'{url}/blob/{branch}/{sourcefile}#L{start}-L{end}'
        await ctx.send(f'<{url}>')

    @BaseCog.listener()
    async def on_ready(self):
        self.bot._alive_since = self.bot._alive_since or datetime.datetime.utcnow()

    @commands.command()
    async def uptime(self, ctx):
        """Print the amount of time since the bot's last reboot"""

        tz = datetime.datetime.now() - datetime.datetime.utcnow()
        date = naturaltime(self.bot._alive_since + tz)
        await ctx.send(f'Bot last rebooted {date}')

    @commands.command(name='list-cogs', aliases=['cog-list', 'ls-cogs'])
    async def list_cogs(self, ctx):
        """Print the names of all loaded Cogs"""

        await ctx.send('```\n' + '\n'.join(self.bot.cogs) + '\n```')

    @commands.command()
    async def memory(self, ctx):
        """Show the bot's current memory usage"""

        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        units = [
            (1 << 30, 'TiB'),
            (1 << 20, 'GiB'),
            (1 << 10, 'MiB')
        ]
        for size, unit in units:
            if rss >= size:
                rss /= size
                break
        else:
            unit = 'KiB'
        await ctx.send(f'Total resources used: {rss:.3f} {unit}')

    @commands.command()
    async def userinfo(self, ctx, *, target: typing.Union[discord.Member, discord.User] = None):
        def format_datetime(dt):
            strftime = dt.strftime('%Y-%m-%d %H:%M')
            human_time = precisedelta(dt, minimum_unit='minutes', format='%d')
            return f'{strftime} ({human_time} ago)'

        target = target or ctx.author
        is_member = isinstance(target, discord.Member)
        embed = discord.Embed()
        embed.set_author(name=str(target))
        embed.set_thumbnail(url=str(target.avatar_url))
        embed.add_field(name='ID', value=str(target.id), inline=False)
        embed.add_field(name='Servers', value=str(sum(1 for guild in self.bot.guilds if guild.get_member(target.id))), inline=False)
        embed.add_field(name='Joined', value=is_member and format_datetime(target.joined_at) or 'N/A', inline=False)
        embed.add_field(name='Created', value=format_datetime(target.created_at), inline=False)
        if is_member:
            embed.add_field(name='Roles', value=', '.join(str(role) for role in target.roles[1:]) or '\u200b')
        elif ctx.channel is None:
            embed.set_footer(text='This command was used in a DM.')
        else:
            embed.set_footer(text='This member is not in this server.')
        await ctx.send(embed=embed)

    @BaseCog.listener()
    async def on_raw_message_edit(self, payload: discord.RawMessageUpdateEvent):
        """Detect when the original version of a published announcement is delteted."""

        channel = self.bot.get_channel(payload.channel_id)
        if isinstance(channel, discord.TextChannel) \
                and channel.is_news() \
                and channel.permissions_for(channel.guild.me).manage_messages \
                and payload.data['content'] == '[Original Message Deleted]' \
                and 'webhook_id' in payload.data:
            await self.bot.http.delete_message(payload.channel_id, payload.message_id)


def setup(bot):
    bot.add_cog(Core(bot))
