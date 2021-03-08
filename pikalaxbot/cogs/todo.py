import discord
from discord.ext import commands, menus
from . import *
from .utils.menus import NavMenuPages
import typing

from sqlalchemy import Column, INTEGER, BIGINT, TEXT, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


class TodoListPageSource(menus.ListPageSource):
    async def format_page(self, menu: NavMenuPages, page: str):
        return discord.Embed(
            title=f'{menu.author}\'s to-do list',
            description=page,
            colour=0xf47fff
        ).set_footer(
            text=f'Page {menu.current_page + 1} of {self.get_max_pages()}'
        )


class TodoPerson(BaseTable):
    user_id = Column(BIGINT, primary_key=True)

    items = relationship('TodoItem', lazy=False, cascade='all, delete-orphan', backref='owner')


class TodoItem(BaseTable):
    id = Column(INTEGER, primary_key=True)
    user_id = Column(BIGINT, ForeignKey(TodoPerson.user_id))
    entry = Column(TEXT)

    __table_args__ = (UniqueConstraint(user_id, entry),)


class Todo(BaseCog):
    """Commands related to to-do lists"""

    @commands.group('todo', invoke_without_command=True)
    async def todo_grp(self, ctx: MyContext):
        """To-do list command group"""
        await self.todo_list(ctx)

    @todo_grp.command('list')
    async def todo_list(self, ctx: MyContext):
        """Show your to-do list"""
        async with self.sql_session as sess:
            tdl: TodoPerson = await sess.get(TodoPerson, ctx.author.id)
        if tdl and tdl.items:
            pag = commands.Paginator()
            for i, item in enumerate(tdl.items, 1):  # type: int, TodoItem
                pag.add_line(f'{i}: {item.entry}')
            menu = NavMenuPages(TodoListPageSource(pag.pages, per_page=1))
            menu.author = ctx.author
            await menu.start(ctx)
        else:
            await ctx.send('You have no to-do items.')

    @todo_grp.command('add')
    async def todo_add(self, ctx: MyContext, *, entry: str):
        """Add an item to your to-do list"""
        try:
            async with self.sql_session as sess:
                tdl: TodoPerson = await sess.get(TodoPerson, ctx.author.id)
                if tdl is None:
                    tdl = TodoPerson(user_id=ctx.author.id)
                    sess.add(tdl)
                    await sess.flush()
                    await sess.refresh(tdl)
                tdl.items.append(TodoItem(entry=entry))
        except IntegrityError:
            await ctx.send('That item is already on your to-do list!')
        else:
            await ctx.message.add_reaction('\N{white heavy check mark}')

    @todo_grp.command('delete', aliases=['rm', 'del', 'remove'])
    async def todo_remove(self, ctx: MyContext, *, item: typing.Union[int, str]):
        """Remove a to-do list item"""
        async with self.sql_session as sess:  # type: AsyncSession
            # Can't do this in a converter because the backref won't cooperate
            person = await sess.get(TodoPerson, ctx.author.id)
            if person is None:
                raise commands.BadArgument('No to-do items')
            try:
                idx = int(item)
                if idx < 1 or idx > len(person.items):
                    raise commands.BadArgument('Not a valid to-do index')
                return person.items[idx - 1]
            except ValueError:
                obj = discord.utils.get(person.items, entry=item)
                if obj is None:
                    raise commands.BadArgument('That item is not on your to-do list')
            sess.delete(item)
            await sess.refresh(person)
        await ctx.message.add_reaction('\N{white heavy check mark}')

    async def cog_command_error(self, ctx: MyContext, error: commands.CommandError):
        if isinstance(error, commands.BadArgument):
            await ctx.reply(error)
        else:
            await self.send_tb(ctx, error)
