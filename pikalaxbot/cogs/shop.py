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
import json
from . import *
from ..pokeapi import PokeapiModel
from .utils.game import Game
if typing.TYPE_CHECKING:
    from .leaderboard import Leaderboard

from sqlalchemy import Column, BIGINT, INTEGER, UniqueConstraint, CheckConstraint, select, update
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.dialects.postgresql.asyncpg import AsyncAdapt_asyncpg_dbapi


class PkmnInventory(BaseTable):
    member = Column(BIGINT, primary_key=True)
    item_id = Column(INTEGER, primary_key=True)
    quantity = Column(INTEGER, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint(member, item_id),
        CheckConstraint(quantity >= 0)
    )

    @classmethod
    async def give(
            cls,
            conn: AsyncConnection,
            person: discord.Member,
            item: 'PokeapiModel.classes.Item',
            quantity: int
    ):
        statement = insert(cls).values(
            member=person.id,
            item_id=item.id,
            quantity=quantity
        )
        upsert = statement.on_conflict_do_update(
            index_elements=['member', 'item_id'],
            set_={'quantity': statement.excluded.quantity + quantity}
        )
        await conn.execute(upsert)

    @classmethod
    async def take(
            cls,
            conn: AsyncConnection,
            person: discord.Member,
            item: 'PokeapiModel.classes.Item',
            quantity: int
    ):
        statement = update(cls).where(
            cls.member == person.id,
            cls.item_id == item.id
        ).values(
            quantity=cls.quantity - quantity
        )
        await conn.execute(statement)

    @classmethod
    async def check(cls, conn: AsyncConnection, person: discord.Member, item: 'PokeapiModel.classes.Item', quantity):
        statement = select(cls.quantity).where(
            cls.member == person.id,
            cls.item_id == item.id
        )
        bag_quantity = await conn.scalar(statement)
        return bag_quantity and bag_quantity >= quantity

    @classmethod
    async def retrieve(cls, conn: AsyncConnection, person: discord.Member):
        statement = select([cls.item_id, cls.quantity]).where(cls.member == person.id, cls.quantity != 0)
        result = await conn.execute(statement)
        return result.all()

    @classmethod
    async def retrieve_streamed(cls, conn: AsyncConnection, person: discord.Member):
        statement = select([cls.item_id, cls.quantity]).where(cls.member == person.id, cls.quantity != 0)
        result = await conn.stream(statement)
        async for item in result:
            yield item


def int_range(low: int, high: int):
    def actual_converter(argument: str):
        try:
            argument = int(argument)
        except ValueError:
            raise commands.BadArgument('Conversion to int failed for value "{}"'.format(argument))
        if not high >= argument >= low:
            raise commands.BadArgument('Integer value out of range')
        return argument
    return actual_converter


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
    async def format_page(self, menu: menus.MenuPages, page: list['PokeapiModel.classes.Item']):
        embed = discord.Embed(
            title='Items available for purchase',
            description=f'Use `{menu.ctx.prefix}mart buy` to make a purchase'
        )
        for item in page:
            embed.add_field(
                name=item,
                value=f'Cost: {item.cost}'
            )
        embed.set_footer(
            text=f'Page {menu.current_page + 1} of {self.get_max_pages()}'
        )
        return embed


class ItemBagPageSource(menus.ListPageSource):
    async def format_page(self, menu: menus.MenuPages, page: list[tuple['PokeapiModel.classes.Item', int]]):
        embed = discord.Embed(
            title='Items in {0.ctx.author.display_name}\'s bag'.format(menu),
            description=f'Use `{menu.ctx.prefix}mart buy` to make a purchase'
        )
        for item, quantity in page:
            embed.add_field(
                name=item,
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


wares_concurrency = shared_max_concurrency(1, per=commands.BucketType.channel)
buy_sell_toss_concurrency = shared_max_concurrency(1, per=commands.BucketType.user)


class Shop(BaseCog):
    """Welcome to the PokéMart!"""

    _shop_item_ids = (
        2, 3, 4, 6, 7, 8, 9, 10, 11, 13, 14, 15, 16,
        17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28,
        38, 39, 45, 46, 47, 48, 49, 51, 52,
        55, 56, 57, 58, 59, 60, 61, 62, 63, 64,
        76, 77, 78, 79, 80, 81, 82, 83, 84, 85,
    )

    @afunctools.cached_property
    async def shop_items(self):
        return [await PokeapiModel.classes.Item.get(self.bot.pokeapi, id_) for id_ in self._shop_item_ids]

    async def init_db(self, sql):
        await PkmnInventory.create(sql)

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

    @buy_sell_toss_concurrency
    @mart.command()
    async def buy(
        self,
        ctx: MyContext,
        quantity: typing.Optional[int_range(1, 999)] = 1,
        *,
        item: 'PokeapiModel.classes.Item'
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
        async with self.bot.sql as sql:
            balance = await Game.check_score(sql, ctx.author)
        balance = balance and balance.score or 0
        item_path = json.loads((await item.item_spriteses)[0].sprites)['default']
        icon_url = self.bot.pokeapi.sprite_url(item_path)
        embed = discord.Embed().set_image(
            url=icon_url
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
            async with self.bot.sql as sql:
                await Game.decrement_score(sql, ctx.author, by=price)
                await PkmnInventory.give(sql, ctx.author, item, quantity)
        except AsyncAdapt_asyncpg_dbapi.IntegrityError as e:
            if isinstance(e.orig, asyncpg.CheckViolationError):
                lb_cog: 'Leaderboard' = self.bot.get_cog('Leaderboard')
                prefix, *_ = await self.bot.get_prefix(ctx.message)
                return await ctx.reply(
                    f'You seem to be a little short on funds. '
                    f'You can spend up to your score on the game leaderboards. '
                    f'Use `{prefix}{lb_cog.show.qualified_name}` to check your balance.',
                    delete_after=10
                )
            raise e.orig
        await ctx.reply(f'Okay, I sold {quantity} {item}(s) to {ctx.author.display_name} for {price:,} points.')

    @buy_sell_toss_concurrency
    @mart.command()
    async def sell(
        self,
        ctx: MyContext,
        quantity: typing.Optional[int_range(1, 999)] = 1,
        *,
        item: 'PokeapiModel.classes.Item'
    ):
        """Sell items from your inventory"""

        if item.cost == 0:
            return await ctx.reply(f'{item}? Oh no, I can\'t buy that.', delete_after=10)
        async with self.bot.sql as sql:
            if not await PkmnInventory.check(sql, ctx.author, item, quantity):
                return await ctx.reply('You don\'t have nearly that many of these to sell.', delete_after=10)
        price = item.cost * quantity // 2
        msg = await ctx.reply(
            f'Okay, {item}, and you want to sell {quantity}? '
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
            async with self.bot.sql as sql:
                await PkmnInventory.take(sql, ctx.author, item, quantity)
                await Game.increment_score(sql, ctx.author, by=price)
        except AsyncAdapt_asyncpg_dbapi.IntegrityError as e:
            if isinstance(e.orig, asyncpg.CheckViolationError):
                return await ctx.reply('You seem to have less than what you told me you had', delete_after=10)
            raise e.orig from None
        await ctx.reply(f'Great! Thanks for the {item}(s)!')

    @commands.group(invoke_without_command=True)
    async def inventory(self, ctx: MyContext):
        """Commands related to managing your pack"""

    @inventory.command('check')
    async def inventory_check(self, ctx: MyContext):
        """Show your inventory"""

        async with self.bot.sql as sql:
            bag_item_ids, bag_quantites = zip(*await PkmnInventory.retrieve(sql, ctx.author))
        bag_items = [await PokeapiModel.classes.Item.get(self.bot.pokeapi, id_) for id_ in bag_item_ids]
        page_source = ItemBagPageSource(list(zip(bag_items, bag_quantites)), per_page=9)
        menu = menus.MenuPages(page_source, delete_message_after=True, clear_reactions_after=True)
        await menu.start(ctx, wait=True)

    @buy_sell_toss_concurrency
    @inventory.command('toss')
    async def inventory_toss(
        self,
        ctx: MyContext,
        quantity: typing.Optional[int_range(1, 999)] = 1,
        *,
        item: 'PokeapiModel.classes.Item'
    ):
        """Toss items from your bag"""

        async with self.bot.sql as sql:
            if not await PkmnInventory.check(sql, ctx.author, item, quantity):
                return await ctx.reply('You don\'t have nearly that many of these to toss.', delete_after=10)
        msg = await ctx.reply(
            f'Okay to toss {quantity} {item}(s)?'
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
            async with self.bot.sql as sql:
                await PkmnInventory.take(sql, ctx.author, item, quantity)
        except AsyncAdapt_asyncpg_dbapi.IntegrityError as e:
            if isinstance(e.orig, asyncpg.CheckViolationError):
                return await ctx.reply('You seem to have less than what you told me you had', delete_after=10)
            raise e.orig from None
        await ctx.reply(f'Threw away {quantity} {item}(s).')


def setup(bot: PikalaxBOT):
    bot.add_cog(Shop(bot))


def teardown(bot: PikalaxBOT):
    PkmnInventory.unlink()
