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

# Credits to Danny for making this featureful paginated help.
# 17 Oct 2020: Refactored to use ext.menus

import discord
from discord.ext import commands, menus
import asyncio

from . import BaseCog
import typing
import traceback


class BotHelpPageSource(menus.GroupByPageSource):
    async def format_page(self, menu: menus.MenuPages, entry: menus._GroupByEntry):
        bot = menu.bot
        cog = bot.get_cog(entry.key)
        embed = discord.Embed(
            title=entry.key,
            description=(cog and cog.description) or discord.Embed.Empty,
            colour=discord.Colour.blurple()
        )
        for command in entry.items:
            embed.add_field(name=command.qualified_name, value=command.help or 'No help given', inline=False)
        max_pages = self.get_max_pages()
        if max_pages and max_pages > 1:
            embed.set_footer(text=f'Page {menu.current_page + 1}/{self.get_max_pages()}')
        return embed


class GroupOrCogHelpPageSource(menus.ListPageSource):
    async def format_page(self, menu, page):
        # Silence IDE warnings
        raise NotImplementedError

    def format_embed(self, menu, entry, *, title=discord.Embed.Empty, description=discord.Embed.Empty):
        embed = discord.Embed(
            title=title,
            description=description,
            colour=discord.Colour.blurple()
        )
        for command in entry:
            embed.add_field(name=command.qualified_name, value=command.help or 'No help given', inline=False)
        max_pages = self.get_max_pages()
        if max_pages and max_pages > 1:
            embed.set_author(name=f'Page {menu.current_page + 1}/{self.get_max_pages()} ({len(self.entries)} commands)')
        return embed


class CogHelpPageSource(GroupOrCogHelpPageSource):
    def __init__(self, cog, entries, *, per_page):
        super().__init__(entries, per_page=per_page)
        self._cog = cog

    async def format_page(self, menu: menus.MenuPages, entry: typing.List[commands.Command]):
        cog = self._cog
        return self.format_embed(menu, entry, title=f'{cog.qualified_name} Help', description=cog.description or discord.Embed.Empty)


class GroupHelpPageSource(GroupOrCogHelpPageSource):
    title = discord.Embed.Empty
    description = discord.Embed.Empty

    async def format_page(self, menu: menus.MenuPages, page):
        return self.format_embed(menu, page, title=self.title, description=self.description)


class HelpMenu(menus.MenuPages):
    def __init__(self, source, **kwargs):
        super().__init__(source, **kwargs)
        self._in_info = False

    async def go_back_to_current_page(self):
        await asyncio.sleep(30.0)
        await self.show_current_page()

    @menus.button('\N{INPUT SYMBOL FOR NUMBERS}', position=menus.Last(0))
    async def pick_page(self, payload):
        my_msg = await self.ctx.send('What page do you want to go to?')
        try:
            msg = await self.bot.wait_for('message', check=lambda m: m.author == self.ctx.author and m.channel == self.ctx.channel, timeout=30.0)
        except asyncio.TimeoutError:
            await self.ctx.send('Took too long.')
            return
        finally:
            await my_msg.delete()
        if msg.content.isdigit():
            page = int(msg.content)
            await self.show_checked_page(page - 1)

    @menus.button('\N{INFORMATION SOURCE}', position=menus.Last(2))
    async def info(self, payload):
        self._in_info = not self._in_info
        if self._in_info:
            embed = discord.Embed(title='Paginator help', description='Hello! Welcome to the help page.')
            value = '⏮: go to the first page\n' \
                    '◀: go to the previous page\n' \
                    '▶: go to the next page\n' \
                    '⏭: go to the last page\n' \
                    '🔢: lets you type a page number to go to\n' \
                    '⏹: stops the pagination session.\n' \
                    'ℹ: shows this message\n' \
                    '❔: shows how to use the bot'
            embed.add_field(name='What are these reactions for?', value=value)
            embed.set_footer(text=f'We were on page {self.current_page + 1} before this message.')
            await self.message.edit(embed=embed)
            task = self.bot.loop.create_task(self.go_back_to_current_page())

            def on_done():
                self._in_info = False

            task.add_done_callback(on_done)
        else:
            await self.show_current_page()

    @menus.button('\N{WHITE QUESTION MARK ORNAMENT}', position=menus.Last(3))
    async def using_the_bot(self, payload):
        embed = discord.Embed(title='Using the bot', description='Hello! Welcome to the help page')
        embed.add_field(name='How do I use the bot?', value='Reading the bot signature is pretty simple.', inline=False)
        embed.add_field(name='<argument>', value='This means the argument is required.', inline=False)
        embed.add_field(name='[argument]', value='This means the argument is optional.', inline=False)
        embed.add_field(name='[A|B]', value='This means that it can be either A or B.', inline=False)
        embed.add_field(name='[argument...]', value='This means you can have multiple arguments.', inline=False)
        embed.add_field(name='Now that you know the basics, it should be noted that...', value='You do not type in the brackets!', inline=False)
        embed.set_footer(text=f'We were on page {self.current_page + 1} before this message.')
        await self.message.edit(embed=embed)
        self.bot.loop.create_task(self.go_back_to_current_page())


class PaginatedHelpCommand(commands.HelpCommand):
    def __init__(self, **options):
        command_attrs = options.pop('command_attrs', {})
        command_attrs.update(
            cooldown=commands.Cooldown(1, 3.0, commands.BucketType.user),
            max_concurrency=commands.MaxConcurrency(1, per=commands.BucketType.channel, wait=False),
            help='Shows help about the bot, a command, or a category'
        )
        super().__init__(command_attrs=command_attrs, **options)

    async def on_help_command_error(self, ctx, error):
        ctx.bot.log_tb(ctx, error)
        if isinstance(error, commands.CommandInvokeError):
            await ctx.send(str(error.original))

    def get_command_signature(self, command):
        parent = command.full_parent_name
        if len(command.aliases) > 0:
            aliases = '|'.join(command.aliases)
            fmt = f'[{command.name}|{aliases}]'
            if parent:
                fmt = f'{parent} {fmt}'
            alias = fmt
        else:
            alias = command.name if not parent else f'{parent} {command.name}'
        return f'{alias} {command.signature}'

    async def send_bot_help(self, mapping):
        def key(c):
            return c.cog_name or '\u200bNo Category'

        bot = self.context.bot
        entries = await self.filter_commands(bot.commands, sort=True, key=key)
        page_source = BotHelpPageSource(entries, key=key, per_page=9)
        paginator = HelpMenu(page_source, delete_message_after=True)
        await paginator.start(ctx=self.context, wait=True)

    async def send_cog_help(self, cog):
        entries = await self.filter_commands(cog.get_commands(), sort=True)
        page_source = CogHelpPageSource(cog, entries, per_page=6)
        paginator = HelpMenu(page_source, delete_message_after=True)
        await paginator.start(ctx=self.context, wait=True)

    def common_command_formatting(self, page_or_embed, command):
        page_or_embed.title = self.get_command_signature(command)
        if command.description:
            page_or_embed.description = f'{command.description}\n\n{command.help}'
        else:
            page_or_embed.description = command.help or 'No help found...'

    async def send_command_help(self, command):
        # No pagination necessary for a single command.
        embed = discord.Embed(colour=discord.Colour.blurple())
        self.common_command_formatting(embed, command)
        await self.context.send(embed=embed)

    async def send_group_help(self, group):
        subcommands = group.commands
        if len(subcommands) == 0:
            return await self.send_command_help(group)

        entries = await self.filter_commands(subcommands, sort=True)
        page_source = GroupHelpPageSource(entries, per_page=9)
        self.common_command_formatting(page_source, group)

        paginator = HelpMenu(page_source, delete_message_after=True)
        await paginator.start(ctx=self.context, wait=True)


class Help(BaseCog):
    def __init__(self, bot):
        super().__init__(bot)
        self._original_help_command = bot.help_command
        bot.help_command = PaginatedHelpCommand(command_attrs={'name': bot.settings.help_name})
        bot.help_command.cog = self

    async def cog_command_error(self, ctx, error):
        if isinstance(error, (commands.CommandOnCooldown, commands.MaxConcurrencyReached)):
            return
        tb = '\n'.join(traceback.format_exception(error.__class__, error, error.__traceback__))
        await self.bot.send_tb(f'Ignoring exception in help command\n{tb}')

    def cog_unload(self):
        self.bot.help_command = self._original_help_command


def setup(bot):
    bot.add_cog(Help(bot))
