import discord
from discord.ext import commands
from . import *
from .utils.converters import CommandConverter
from .. import __version__, __dirname__
from ..types import GuildChannel
from humanize import precisedelta, naturaltime
import datetime
import os
import glob
import inspect
import time
import typing
import collections
import operator
try:
    import resource
except ImportError:
    resource = None
from jishaku.meta import __version__ as jsk_ver

from sqlalchemy import Column, TEXT, BIGINT, INTEGER, UniqueConstraint, select
from sqlalchemy.ext.asyncio import AsyncSession


class Commandstats(BaseTable):
    command = Column(TEXT, primary_key=True)
    guild = Column(BIGINT, primary_key=True)
    uses = Column(INTEGER, default=0)

    __table_args__ = (UniqueConstraint(command, guild),)


class Info(BaseCog):
    """Commands giving info about the bot, guild, etc."""
    LOCAL_TZ = datetime.datetime.now().astimezone().tzinfo
    CHANNEL_EMOJIS = {
        discord.ChannelType.text: '#️⃣',
        discord.ChannelType.voice: '🔊',
        discord.ChannelType.news: '📢',
        discord.ChannelType.store: '🏪',
    }

    @commands.command()
    async def userinfo(self, ctx: MyContext, *, target: typing.Union[discord.Member, discord.User] = None):
        """Show information about the given user"""

        def format_datetime(dt):
            strftime = dt.strftime('%Y-%m-%d %H:%M')
            human_time = precisedelta(dt, minimum_unit='minutes', format='%d')
            return f'{strftime} ({human_time} ago)'

        target = target or ctx.author
        is_member = isinstance(target, discord.Member)
        embed = discord.Embed(
            colour=target.colour
        ).set_author(
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

    @commands.guild_only()
    @commands.command(aliases=['guildinfo'])
    async def serverinfo(self, ctx: MyContext):
        """Shows information about the current server"""

        guild: discord.Guild = ctx.guild
        emojis = ''.join([str(e) for e in guild.emojis if e.is_usable()][:10])
        status_icons = {
            stat: discord.utils.get(
                ctx.bot.emojis,
                name=f'status_{stat}'
            )
            for stat in discord.Status
            if stat is not discord.Status.invisible
        }
        member_statuses = collections.Counter(m.status for m in guild.members)
        nbots = sum(1 for m in guild.members if m.bot)
        status_string = ' '.join(f'{icon} {member_statuses[stat]}' for stat, icon in status_icons.items())
        embed = discord.Embed(
            title=str(guild),
            description=f'**ID:** {guild.id}\n'
                        f'**Owner:** {guild.owner}',
            colour=0xf47fff
        ).set_thumbnail(
            url=str(guild.icon_url)
        ).add_field(
            name='Boosts',
            value=f'Level {guild.premium_tier}\n'
                  f'{guild.premium_subscription_count} boosts',
            inline=False
        ).add_field(
            name='Emojis',
            value=f'{emojis}...',
            inline=False
        ).add_field(
            name='Channels',
            value=f'{len(guild.text_channels)} text channels\n'
                  f'{len(guild.voice_channels)} voice channels\n'
                  f'{len(guild.categories)} categories',
            inline=False
        ).add_field(
            name='Members',
            value=f'{status_string}\n'
                  f'Total: {guild.member_count} ({nbots} bots)'
        )
        await ctx.send(embed=embed)


    @staticmethod
    async def send_perms(
            ctx: MyContext,
            member: discord.Member,
            where: typing.Union[GuildChannel, discord.Guild],
            perms: discord.Permissions
    ):
        voice_perms = frozenset((
            'priority_speaker',
            'stream',
            'connect',
            'speak',
            'mute_members',
            'deafen_members',
            'move_members',
            'use_voice_activation'
        ))
        paginator = commands.Paginator('', '', 1024)
        emojis = ('\N{CROSS MARK}', '\N{WHITE HEAVY CHECK MARK}')
        i = 0
        show_voice_perms = isinstance(where, (discord.VoiceChannel, discord.Guild))
        page_limit = 11 if show_voice_perms else 8
        for name, value in sorted(perms):
            if show_voice_perms or name not in voice_perms:
                paginator.add_line(f'{emojis[value]} {name.title().replace("_", " ").replace("Tts", "TTS")}')
                i += 1
                if i % page_limit == 0:
                    paginator.close_page()
        embed = discord.Embed(
            title=f'Permissions for {member} in {where}',
            colour=0xf47fff
        )
        [embed.add_field(name='\u200b', value=page) for page in paginator.pages]
        await ctx.send(embed=embed)

    @commands.group(aliases=['perms'], invoke_without_command=True)
    async def permissions(
            self,
            ctx: MyContext,
            channel: typing.Optional[GuildChannel],
            *,
            member: discord.Member = None
    ):
        """Print the member's permissions in a channel"""
        member = member or ctx.author
        channel = channel or ctx.channel
        await Info.send_perms(ctx, member, channel, member.permissions_in(channel))

    @permissions.command(name='guild')
    async def guild_permissions(self, ctx: MyContext, *, member: discord.Member = None):
        """Print the member's permissions in the guild"""
        member = member or ctx.author
        await Info.send_perms(ctx, member, ctx.guild, member.guild_permissions)

    @commands.command()
    async def about(self, ctx: MyContext):
        """Shows info about the bot in the current context"""

        await self.bot.is_owner(discord.Object(id=0))  # for owner_id
        prefix, *_ = await self.bot.get_prefix(ctx.message)
        e = discord.Embed(
            title=f'PikalaxBOT v{__version__}',
            description=f'Hiya, I\'m a bot! **{self.bot.get_user(self.bot.owner_id)}** made me.\n\n'
                        f'My prefix in this guild is `{prefix}`.'
        )
        shared = sum(g.get_member(ctx.author.id) is not None for g in self.bot.guilds)
        e.set_author(name=str(ctx.me))
        e.add_field(
            name='Package Versions',
            value=f'Discord.py v{discord.__version__}\n'
                  f'Jishaku v{jsk_ver}',
            inline=False
        )
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
            value='[Click](https://github.com/PikalaxALT/pikalaxbot)'
        ).add_field(
            name='Uptime',
            value=f'{datetime.datetime.utcnow() - self.bot._alive_since}'
        )
        e.add_field(
            name='Support server',
            value='[Click](https://discord.gg/TbjzpzR9Rg)'
        )
        if ctx.guild and ctx.me.colour.value:
            e.colour = ctx.me.colour
        if ctx.me.avatar:
            e.set_thumbnail(url=ctx.me.avatar_url)
        await ctx.send(embed=e)

    @commands.command(aliases=['src'])
    async def source(self, ctx: MyContext, *, command: typing.Optional[CommandConverter]):
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

    @commands.command()
    async def credits(self, ctx: MyContext):
        """Credit where credit is due"""

        embed = discord.Embed(
            title='Credits',
            description='I was mostly written by PikalaxALT#5823, '
                        'but some extensions contain code '
                        'written by other beautiful people.',
            colour=0xF47FFF
        ).add_field(
            name='Q20Game',
            value='Tustin2121#6219'
        ).add_field(
            name='Eval',
            value='Danny#0007'
        ).add_field(
            name='Jishaku',
            value='Devon Gorialis'
        ).add_field(
            name='ext.PokeAPI',
            value='jreese (aiosqlite), Naramsim (database itself)'
        )
        await ctx.send(embed=embed)

    if resource:
        @commands.command()
        async def memory(self, ctx: MyContext):
            """Show the bot's current memory usage"""

            rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            units = [
                (1 << 30, 'TiB'),
                (1 << 20, 'GiB'),
                (1 << 10, 'MiB'),
                (1 << 0,  'KiB'),
            ]
            size, unit = discord.utils.find(lambda c: rss >= size[0], units)
            await ctx.send(f'Total resources used: {rss / size:.3f} {unit}')

    @BaseCog.listener()
    async def on_command_completion(self, ctx: MyContext):
        async with self.sql_session as sess:  # type: AsyncSession
            obj = await sess.scalar(
                select(
                    Commandstats
                ).where(
                    Commandstats.command == str(ctx.command),
                    Commandstats.guild == ctx.guild.id
                )
            )
            if obj is None:
                obj = Commandstats(
                    command=str(ctx.command),
                    guild=ctx.guild.id,
                    uses=1
                )
                sess.add(obj)
            else:
                obj.uses += 1

    async def get_runnable_commands(self, ctx: MyContext):
        cmds = []
        async with self.sql_session as sess:
            for obj in (await sess.execute(
                select(
                    Commandstats
                ).where(
                    Commandstats.guild == ctx.guild.id
                ).order_by(
                    Commandstats.uses.desc()
                )
            )).scalars():
                cmd: commands.Command = self.bot.get_command(obj.command)
                if cmd is None:
                    sess.delete(obj)
                    continue
                try:
                    valid = await cmd.can_run(ctx)
                    if valid:
                        cmds.append(f'{obj.command} ({obj.uses} uses)')
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
        ctr: collections.Counter[str] = collections.Counter()
        for ctr['file'], f in enumerate(glob.glob(f'{__dirname__}/**/*.py', recursive=True)):
            with open(f, encoding='utf-8') as fp:
                for ctr['line'], line in enumerate(fp, ctr['line']):
                    line = line.lstrip()
                    ctr['class'] += line.startswith('class')
                    ctr['function'] += line.startswith('def')
                    ctr['coroutine'] += line.startswith('async def')
                    ctr['comment'] += '#' in line
        n_total_cmds = len(self.bot.commands)
        places = '\U0001f947', '\U0001f948', '\U0001f949'
        prefix, *_ = await self.bot.get_prefix(ctx.message)  # type: str
        embed = discord.Embed(
            title=f'{self.bot.user.name} Stats',
            description=f'My prefix for this server is `{prefix}`',
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
            value='\n'.join(f'{key.title()}: {value}' for key, value in ctr.items()) + f'\n'
                  f'Commands: {n_total_cmds}'
        )
        await ctx.send(embed=embed)

    @BaseCog.listener()
    async def on_ready(self):
        self.bot._alive_since = self.bot._alive_since or datetime.datetime.utcnow()

    @commands.command()
    async def uptime(self, ctx: MyContext):
        """Print the amount of time since the bot's last reboot"""

        date = naturaltime(self.bot._alive_since + self.LOCAL_TZ.utcoffset(None))
        await ctx.send(f'Bot last rebooted {date}')

    @staticmethod
    def get_channel_repr(channel: GuildChannel):
        if channel.type is discord.ChannelType.text:
            if channel == channel.guild.rules_channel:
                emoji = '🗒️'
            elif channel.is_nsfw():
                emoji = '🔞'
            else:
                emoji = '#️⃣'
        else:
            emoji = Info.CHANNEL_EMOJIS[channel.type]
        return '{} {.name}'.format(emoji, channel)

    @commands.group(invoke_without_command=True)
    async def channels(self, ctx: MyContext):
        """Shows the channel list"""
        embed = discord.Embed(
            title=f'Channels I can read in {ctx.guild}',
            colour=0xF47FFF
        )

        perms = operator.attrgetter('read_messages', 'read_message_history')

        def predicate(chan: discord.abc.GuildChannel):
            return any(perms(chan.permissions_for(ctx.guild.me)))

        for category, channels in ctx.guild.by_category():  \
                # type: typing.Optional[discord.CategoryChannel], list[discord.TextChannel]
            channels = [channel for channel in channels if predicate(channel)]
            if not channels:
                continue
            embed.add_field(
                name=str(category or '\u200b'),
                value='\n'.join(map(self.get_channel_repr, channels)),
                inline=False
            )
        await ctx.send(embed=embed)

    @commands.command(aliases=['pfp'])
    async def avatar(self, ctx: MyContext, *, user: typing.Union[discord.Member, discord.User] = None):
        """Show the user's avatar"""
        user = user or ctx.author
        await ctx.reply(embed=discord.Embed(
            title=f'{user}\'s avatar',
            colour=0xf47fff
        ).set_image(
            url=str(user.avatar_url_as(static_format='png'))
        ))
