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
from discord.ext import commands, menus
import asyncpg
import asyncstdlib.functools as afunctools
import typing
import asyncio
import collections
from . import *
from ..pokeapi import PokeapiModels
if typing.TYPE_CHECKING:
    from .leaderboard import Leaderboard


def int_range(low: int, high: int):
    class ActualConverter(int):
        @classmethod
        async def convert(cls, context: MyContext, argument: str):
            try:
                argument = cls(argument)
            except ValueError:
                raise commands.BadArgument('Conversion to int failed for value "{}"'.format(argument))
            if not high >= argument >= low:
                raise commands.BadArgument('Integer value out of range')
            return argument
    return ActualConverter


class ShopConfirmationMenu(menus.Menu):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._response: typing.Optional[bool] = None

    async def send_initial_message(self, ctx: MyContext, channel: discord.TextChannel):
        pass

    @menus.button('\N{WHITE HEAVY CHECK MARK}')
    async def on_yes(self, payload: discord.RawReactionActionEvent):
        self._response = True
        self.stop()

    @menus.button('\N{CROSS MARK}')
    async def on_no(self, payload: discord.RawReactionActionEvent):
        self._response = False
        self.stop()

    async def finalize(self, timed_out):
        if timed_out:
            await self.message.delete()


class ShopInventoryPageSource(menus.ListPageSource):
    async def format_page(self, menu: menus.MenuPages, page: list['PokeapiModels.Item']):
        embed = discord.Embed(
            title='Items available for purchase',
            description=f'Use `{menu.ctx.prefix}mart buy` to make a purchase'
        )
        for item in page:
            embed.add_field(
                name=item.name,
                value=f'Cost: {item.cost}'
            )
        embed.set_footer(
            text=f'Page {menu.current_page + 1} of {self.get_max_pages()}'
        )
        return embed


class ItemBagPageSource(menus.ListPageSource):
    async def format_page(self, menu: menus.MenuPages, page: list[tuple['PokeapiModels.Item', int]]):
        embed = discord.Embed(
            title='Items in {0.ctx.author.display_name}\'s bag'.format(menu),
            description=f'Use `{menu.ctx.prefix}mart buy` to make a purchase'
        )
        for item, quantity in page:
            embed.add_field(
                name=item.name,
                value=f'Quantity: x{quantity}'
            )
        embed.set_footer(
            text=f'Page {menu.current_page + 1} of {self.get_max_pages()}'
        )
        return embed


def shared_max_concurrency(rate: int, per: commands.BucketType, *, wait=False):
    value = commands.MaxConcurrency(rate, per=per, wait=wait)

    def decorator(func: typing.Union[commands.Command, typing.Callable[..., typing.Coroutine]]):
        if isinstance(func, commands.Command):
            func._max_concurrency = value
        else:
            func.__commands_max_concurrency__ = value
        return func

    return decorator


wares_concurrency = shared_max_concurrency(1, per=commands.BucketType.channel, wait=False)


class Shop(BaseCog):
    """Welcome to the PokéMart!"""

    _shop_item_ids = (
        2, 3, 4, 6, 7, 8, 9, 10, 11, 13, 14, 15, 16,
        17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28,
        38, 39, 45, 46, 47, 48, 49, 51, 52,
        55, 56, 57, 58, 59, 60, 61, 62, 63, 64,
        76, 77, 78, 79, 80, 81, 82, 83, 84, 85,
    )

    def __init__(self, bot):
        super().__init__(bot)
        self._lock_bucket = collections.defaultdict(asyncio.Lock)

    async def cog_before_invoke(self, ctx: MyContext):
        await self._lock_bucket[ctx.author].acquire()
        await super().cog_before_invoke(ctx)

    async def cog_after_invoke(self, ctx: MyContext):
        self._lock_bucket[ctx.author].release()
        await super().cog_after_invoke(ctx)

    # Temporary dev lock
    def cog_check(self, ctx: MyContext):
        return commands.is_owner().predicate(ctx)

    @afunctools.cached_property
    async def shop_items(self):
        return [await self.bot.pokeapi.get_model('Item', id_) for id_ in self._shop_item_ids]

    async def init_db(self, sql: asyncpg.Connection):
        await sql.execute(
            'create table '
            'if not exists '
            'pkmn_inventory ('
            'member bigint not null, '
            'item_id int not null, '
            'quantity int not null default 0 check (quantity >= 0), '
            'unique (member, item_id)'
            ')'
        )

    @wares_concurrency
    @commands.group(invoke_without_command=True)
    async def mart(self, ctx: MyContext):
        """Commands for buying and selling items"""
        await self.wares(ctx)

    @wares_concurrency
    @mart.command()
    async def wares(self, ctx: MyContext):
        """Show the selection of items available"""
        shop_items = await self.shop_items
        page_source = ShopInventoryPageSource(shop_items, per_page=9)
        menu = menus.MenuPages(page_source, delete_message_after=True, clear_reactions_after=True)
        await menu.start(ctx, wait=True)

    @mart.command()
    async def buy(
        self,
        ctx: MyContext,
        item: PokeapiModels.Item,
        quantity: int_range(1, 999) = 1
    ):
        """Buy items from the shop. There is a limited selection available"""
        if item.id not in self._shop_item_ids:
            prefix, *_ = await self.bot.get_prefix(ctx.message)
            return await ctx.reply(
                f'{item}? I don\'t have that in stock.',
                embed=discord.Embed(
                    description=f'Use `{prefix}{self.wares.qualified_name}` to see what I have for sale.'
                ),
                delete_after=10
            )
        price = item.cost * quantity
        async with self.bot.sql as sql:  # type: asyncpg.Connection
            balance = await sql.fetchval(
                'select score '
                'from game '
                'where id = $1',
                ctx.author.id
            )
        balance = balance or 0
        embed = discord.Embed().set_image(
            url=await self.bot.pokeapi.get_item_icon_url(item)
        ).add_field(
            name='Balance',
            value='{:,}'.format(balance)
        )
        msg = await ctx.reply(
            f'Okay, {item}, and you wanted {quantity}? '
            f'That will cost you {price:,} leaderboard points. '
            f'Is that okay?',
            embed=embed
        )
        menu = ShopConfirmationMenu(
            message=msg,
            clear_reactions_after=True
        )
        await menu.start(ctx, wait=True)
        if menu._response is None:
            return await ctx.send('Request timed out.', delete_after=10)
        if not menu._response:
            return await ctx.send('Transaction cancelled.', delete_after=10)
        try:
            async with self.bot.sql as sql:  # type: asyncpg.Connection
                async with sql.transaction():
                    await sql.execute(
                        'update game '
                        'set score = score - $2 '
                        'where id = $1',
                        ctx.author.id,
                        price
                    )
                    await sql.execute(
                        'insert into pkmn_inventory '
                        'values ($1, $2, $3) '
                        'on conflict (member, item_id) '
                        'do update '
                        'set quantity = pkmn_inventory.quantity + $3',
                        ctx.author.id,
                        item.id,
                        quantity
                    )
        except asyncpg.CheckViolationError:
            lb_cog: 'Leaderboard' = self.bot.get_cog('Leaderboard')
            prefix, *_ = await self.bot.get_prefix(ctx.message)
            return await ctx.reply(
                f'You seem to be a little short on funds. '
                f'You can spend up to your score on the game leaderboards. '
                f'Use `{prefix}{lb_cog.show.qualified_name}` to check your balance.',
                delete_after=10
            )
        await ctx.reply(f'Okay, I sold {quantity} {item}(s) to {ctx.author.display_name} for {price:,} points.')

    @mart.command()
    async def sell(
        self,
        ctx: MyContext,
        item: PokeapiModels.Item,
        quantity: int_range(1, 999) = 1
    ):
        """Sell items from your inventory"""

        if item.cost == 0:
            return await ctx.reply(f'{item.name}? Oh no, I can\'t buy that.', delete_after=10)
        price = item.cost * quantity // 2
        async with self.bot.sql as sql:  # type: asyncpg.Connection
            bag_quantity = await sql.fetchval(
                'select quantity '
                'from pkmn_inventory '
                'where member = $1 '
                'and item_id = $2',
                ctx.author.id,
                item.id
            )
        bag_quantity = bag_quantity or 0
        if bag_quantity < quantity:
            return await ctx.reply('You don\'t have nearly that many of these to sell.', delete_after=10)
        msg = await ctx.reply(
            f'Okay, {item.name}, and you want to sell {quantity}? '
            f'I can give you {price:,} for those. Okay?'
        )
        menu = ShopConfirmationMenu(
            message=msg,
            clear_reactions_after=True
        )
        await menu.start(ctx, wait=True)
        if menu._response is None:
            return await ctx.send('Request timed out', delete_after=10)
        elif not menu._response:
            return await ctx.send('Transaction cancelled', delete_after=10)
        try:
            async with self.bot.sql as sql:  # type: asyncpg.Connection
                async with sql.transaction():
                    await sql.execute(
                        'insert into game '
                        'values ($1, $2) '
                        'on conflict (id) '
                        'do update '
                        'set score = game.score + $2',
                        ctx.author.id,
                        price
                    )
                    await sql.execute(
                        'update pkmn_inventory '
                        'set quantity = quantity - $3 '
                        'where member = $1 '
                        'and item_id = $2',
                        ctx.author.id,
                        item.id,
                        quantity
                    )
        except asyncpg.CheckViolationError:
            return await ctx.reply('You seem to have less than what you told me you had', delete_after=10)
        await ctx.reply(f'Great! Thanks for the {item.name}(s)!')

    @commands.group(invoke_without_command=True)
    async def inventory(self, ctx: MyContext):
        """Commands related to managing your pack"""

    @inventory.command('check')
    async def inventory_check(self, ctx: MyContext):
        """Show your inventory"""

        async with self.bot.sql as sql:  # type: asyncpg.Connection
            bag_items = [
                (await self.bot.pokeapi.get_model('Item', id_), quantity)
                for id_, quantity in await sql.fetch(
                    'select item_id, quantity '
                    'from pkmn_inventory '
                    'where member = $1 '
                    'and quantity > 0',
                    ctx.author.id
                )
            ]
        page_source = ItemBagPageSource(bag_items, per_page=9)
        menu = menus.MenuPages(page_source, delete_message_after=True, clear_reactions_after=True)
        await menu.start(ctx, wait=True)

    @inventory.command('toss')
    async def inventory_toss(
        self,
        ctx: MyContext,
        item: PokeapiModels.Item,
        quantity: int_range(1, 999) = 1
    ):
        """Toss items from your bag"""

        async with self.bot.sql as sql:  # type: asyncpg.Connection
            bag_quantity = await sql.fetchval(
                'select quantity '
                'from pkmn_inventory '
                'where member = $1 '
                'and item_id = $2',
                ctx.author.id,
                item.id
            )
        bag_quantity = bag_quantity or 0
        if bag_quantity < quantity:
            return await ctx.reply('You don\'t have nearly that many of these to toss.', delete_after=10)
        msg = await ctx.reply(
            f'Okay to toss {quantity} {item.name}(s)?'
        )
        menu = ShopConfirmationMenu(
            message=msg,
            clear_reactions_after=True
        )
        await menu.start(ctx, wait=True)
        if menu._response is None:
            return await ctx.send('Request timed out', delete_after=10)
        elif not menu._response:
            return await ctx.send('Declined to toss', delete_after=10)
        try:
            async with self.bot.sql as sql:  # type: asyncpg.Connection
                async with sql.transaction():
                    await sql.execute(
                        'update pkmn_inventory '
                        'set quantity = quantity - $3 '
                        'where member = $1 '
                        'and item_id = $2',
                        ctx.author.id,
                        item.id,
                        quantity
                    )
        except asyncpg.CheckViolationError:
            return await ctx.reply('You seem to have less than what you told me you had', delete_after=10)
        await ctx.reply(f'Threw away {quantity} {item.name}(s).')


def setup(bot: PikalaxBOT):
    bot.add_cog(Shop(bot))
