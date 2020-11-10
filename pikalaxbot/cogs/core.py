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
import time
import glob
import collections
from jishaku.meta import __version__ as jsk_ver

from . import BaseCog
from .. import __dirname__
from .utils.errors import *
from .utils.converters import CommandConverter


class Core(BaseCog):
    """The core functionality of the bot."""

    banlist = set()
    game = 'p!help'
    config_attrs = 'banlist', 'game'
    LOCAL_TZ = datetime.datetime.now().astimezone().tzinfo

    async def init_db(self, sql):
        await sql.execute('create table if not exists commandstats (command text unique not null primary key, uses integer default 0)')

    @BaseCog.listener()
    async def on_command_completion(self, ctx):
        async with self.bot.sql as sql:
            await sql.execute('insert or ignore into commandstats(command) values (?)', (ctx.command.qualified_name,))
            await sql.execute('update commandstats set uses = uses + 1 where command = ?', (ctx.command.qualified_name,))

    async def get_runnable_commands(self, ctx):
        cmds = []
        async with self.bot.sql as sql:
            async with sql.execute('select * from commandstats order by uses desc') as cur:
                async for name, uses in cur:
                    cmd: commands.Command = self.bot.get_command(name)
                    try:
                        valid = await cmd.can_run(ctx)
                        if valid:
                            cmds.append(f'{name} ({uses} uses)')
                    except commands.CommandError:
                        continue
        return cmds

    @commands.command()
    async def stats(self, ctx):
        """Shows usage stats about the bot"""

        a = time.perf_counter()
        await ctx.trigger_typing()
        b = time.perf_counter()
        api_ping = b - a
        cmds = await self.get_runnable_commands(ctx)
        # Get source lines
        ctr = collections.Counter()
        for ctr['file'], f in enumerate(glob.glob(f'{__dirname__}/**/*.py', recursive=True)):
            with open(f) as fp:
                for ctr['line'], line in enumerate(fp, ctr['line']):
                    line = line.lstrip()
                    ctr['class'] += line.startswith('class')
                    ctr['function'] += line.startswith('def')
                    ctr['coroutine'] += line.startswith('async def')
                    ctr['comment'] += '#' in line
        places = '\U0001f947', '\U0001f948', '\U0001f949'
        embed = discord.Embed(
            title=f'{self.bot.user.name} Stats',
            description=f'My prefix for this server is `{ctx.prefix}`',
            colour=0xf47fff
        ).add_field(
            name='General Info',
            value=f'{len(self.bot.guilds)} servers\n'
                  f'{len(self.bot.users)} users\n'
                  f'Websocket Ping: {self.bot.latency * 1000:.02f}ms\n'
                  f'API Ping: {api_ping * 1000:.02f}ms'
        ).add_field(
            name='Last rebooted',
            value=naturaltime(self.bot._alive_since + self.LOCAL_TZ.utcoffset(None))
        ).add_field(
            name='Command Stats',
            value='\n'.join(f'{place} {cmd}' for place, cmd in zip(places, cmds)) or 'Insufficient data'
        ).add_field(
            name='Code stats',
            value='\n'.join(f'{key.title()}: {value}' for key, value in ctr.items())
        )
        await ctx.send(embed=embed)

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

    @commands.command(aliases=['reboot', 'restart', 'shutdown'])
    @commands.is_owner()
    async def kill(self, ctx: commands.Context):
        """Shut down the bot (owner only, manual restart required)"""

        mode = ctx.invoked_with in ('reboot', 'restart')
        self.bot.reboot_after = mode
        await ctx.send('Rebooting to apply updates' if mode else 'Shutting down')
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

        e = discord.Embed()
        shared = sum(g.get_member(ctx.author.id) is not None for g in self.bot.guilds)
        e.set_author(name=str(ctx.me))
        e.add_field(name='ID', value=ctx.me.id, inline=False)
        e.add_field(name='Guilds', value=f'{len(self.bot.guilds)} ({shared} shared)', inline=False)
        if ctx.guild:
            e.add_field(
                name='Joined',
                value=naturaltime(ctx.me.joined_at + self.LOCAL_TZ.utcoffset(None)),
                inline=False
            ).add_field(
                name='Created',
                value=naturaltime(ctx.me.created_at + self.LOCAL_TZ.utcoffset(None)),
                inline=False
            )
        if ctx.guild:
            roles = [r.name.replace('@', '@\u200b') for r in ctx.me.roles]
            e.add_field(
                name='Roles',
                value=', '.join(roles) if len(roles) < 10 else f'{len(roles)} roles',
                inline=False
            )
        e.add_field(
            name='Source',
            value='https://github.com/PikalaxALT/pikalaxbot'
        ).add_field(
            name='Uptime',
            value=f'{datetime.datetime.utcnow() - self.bot._alive_since}'
        )
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

        date = naturaltime(self.bot._alive_since + self.LOCAL_TZ.utcoffset(None))
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
        embed = discord.Embed().set_author(
            name=str(target)
        ).set_thumbnail(
            url=str(target.avatar_url)
        ).add_field(
            name='ID',
            value=str(target.id),
            inline=False
        ).add_field(
            name='Servers',
            value=str(sum(1 for guild in self.bot.guilds if guild.get_member(target.id))),
            inline=False
        ).add_field(
            name='Joined',
            value=is_member and format_datetime(target.joined_at) or 'N/A',
            inline=False
        ).add_field(
            name='Created',
            value=format_datetime(target.created_at),
            inline=False
        )
        if is_member:
            embed.add_field(
                name='Roles',
                value=', '.join(str(role) for role in target.roles[1:]) or 'This member has no roles in this server.'
            )
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

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if not await self.bot.is_owner(before):
            return
        before_roles = set(before.roles)
        after_roles = set(after.roles)
        new_roles = after_roles - before_roles
        rem_roles = before_roles - after_roles
        embed = discord.Embed(title=f'Your member object in {before.guild} was updated')
        if new_roles:
            embed.add_field(name='Roles added', value=', '.join(r.name for r in new_roles))
        if rem_roles:
            embed.add_field(name='Roles removed', value=', '.join(r.name for r in rem_roles))
        # if before.nick != after.nick:
        #     embed.add_field(name='Nickname changed', value=after.nick or 'reset to username')
        if not embed.fields:
            return
        await self.bot.get_user(self.bot.owner_id).send(embed=embed)


def setup(bot):
    bot.add_cog(Core(bot))
