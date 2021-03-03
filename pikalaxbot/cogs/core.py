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

import discord
from discord.ext import commands, menus, flags
import datetime
import asyncio

from . import *
from .utils.errors import *
from .utils.game import GameCogBase


class ConfirmationMenu(menus.Menu):
    def __init__(self, mode, **kwargs):
        super().__init__(**kwargs)
        self.mode = mode
        self.reaction = None

    async def send_initial_message(self, ctx: MyContext, channel):
        content = 'The bot will shutdown and apply updates. Okay to proceed?' \
            if self.mode \
            else 'The bot will shutdown and must be manually restarted. Okay to proceed?'
        return await ctx.reply(content)

    @menus.button('\N{CROSS MARK}')
    async def abort(self, payload: discord.RawReactionActionEvent):
        await self.message.edit(content='Reboot cancelled', delete_after=10)
        self.stop()

    @menus.button('\N{WHITE HEAVY CHECK MARK}')
    async def confirm(self, payload: discord.RawReactionActionEvent):
        self.bot.reboot_after = self.mode
        await self.message.edit(content='Rebooting to apply updates' if self.mode else 'Shutting down')

        async def do_logout():
            await asyncio.sleep(3)
            await self.bot.logout()

        asyncio.create_task(do_logout())

    async def finalize(self, timed_out):
        if timed_out:
            await self.message.edit(content='Request timed out', delete_after=10)


class Core(BaseCog):
    """The core functionality of the bot."""

    banlist: set[int] = set()
    game = 'p!help'
    config_attrs = 'banlist', 'game'
    LOCAL_TZ = datetime.datetime.now().astimezone().tzinfo

    async def bot_check(self, ctx: MyContext):
        if not self.bot.is_ready():
            raise NotReady('The bot is not ready to process commands')
        if not ctx.channel.permissions_for(ctx.me).send_messages:
            raise commands.BotMissingPermissions(['send_messages'])
        if isinstance(ctx.command, commands.Command) and await self.bot.is_owner(ctx.author):
            return True
        if ctx.author.id in self.banlist:
            raise BotIsIgnoringUser(f'I am origin {ctx.author}')
        return True

    @flags.add_flag('-y', '--yes', dest='yes', action='store_true')
    @flags.command(aliases=['reboot', 'restart', 'shutdown'])
    @commands.is_owner()
    @commands.max_concurrency(1)
    async def kill(self, ctx: MyContext, **_flags):
        """Shut down the bot (owner only, manual restart required)"""

        menu = ConfirmationMenu(ctx.invoked_with in {'reboot', 'restart'}, timeout=60.0, clear_reactions_after=True)
        if _flags.get('yes'):
            await ctx.send('Rebooting to apply updates' if menu.mode else 'Shutting down')
            await self.bot.logout()
        else:
            await menu.start(ctx, wait=True)

    @commands.command()
    @commands.is_owner()
    async def ignore(self, ctx: MyContext, person: discord.Member):
        """Ban a member from using the bot :datsheffy:"""

        if person == self.bot.user or await self.bot.is_owner(person):
            return await ctx.send('Hmmm... Nope, not gonna do that.')
        self.banlist.add(person.id)
        await ctx.send(f'{person.display_name} is now banned from interacting with me.')

    @commands.command()
    @commands.is_owner()
    async def unignore(self, ctx: MyContext, person: discord.Member):
        """Unban a member from using the bot"""

        self.banlist.discard(person.id)
        await ctx.send(f'{person.display_name} is no longer banned from interacting with me.')

    @commands.command(name='list-cogs', aliases=['cog-list', 'ls-cogs'])
    async def list_cogs(self, ctx: MyContext):
        """Print the names of all loaded Cogs"""

        await ctx.send('```\n' + '\n'.join(self.bot.cogs) + '\n```')

    @BaseCog.listener()
    async def on_raw_message_edit(self, payload: discord.RawMessageUpdateEvent):
        """Detect when the original version of a published announcement is delteted."""

        channel = self.bot.get_channel(payload.channel_id)
        if isinstance(channel, discord.TextChannel) \
                and channel.is_news() \
                and channel.permissions_for(channel.guild.me).manage_messages \
                and payload.data['content'] == '[Original Message Deleted]' \
                and 'webhook_id' in payload.data:
            await channel.get_partial_message(payload.message_id).delete()

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
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

    @staticmethod
    async def delete_response(ctx: MyContext, history: set[int]):
        # Try bulk delete first
        partials: list[discord.PartialMessage] = [ctx.channel.get_partial_message(msg_id) for msg_id in history]
        try:
            await ctx.channel.delete_messages(partials)
        except discord.HTTPException:
            # Bulk delete failed for some reason, so try deleting them one by one
            for msg in partials:
                try:
                    await msg.delete()
                except discord.HTTPException:
                    pass

    @BaseCog.listener('on_message_delete')
    @BaseCog.listener('on_message_edit')
    async def clear_context(self, message: discord.Message, after: discord.Message = None, /):
        try:
            ctx, history = self.bot._ctx_cache.pop((message.channel.id, message.id))  # type: MyContext, set[int]
        except KeyError:
            pass
        else:
            ctx.cancel()
            if isinstance(ctx.cog, GameCogBase):
                await ctx.cog.end_quietly(ctx, history)
            await Core.delete_response(ctx, history)
        if after:
            await self.bot.process_commands(after)


def setup(bot: PikalaxBOT):
    bot.add_cog(Core(bot))
