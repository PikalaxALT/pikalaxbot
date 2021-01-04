import discord
from discord.ext import commands, menus
from . import *
from .utils.menus import NavMenuPages
import unicodedata
import typing


class CharInfoMenu(menus.ListPageSource):
    def format_page(self, menu: NavMenuPages, page: tuple[str, str, str]):
        c, digit, name = page
        c_ord = ord(c)
        py_repr = f'{digit}'
        if name != 'Name not found':
            py_repr += f'\n\\N{{{name}}}'
        return discord.Embed(
            title=f'Info for character: {c}',
            colour=discord.Colour.greyple()
        ).add_field(
            name='Codepoint',
            value=f'{c_ord:x}'
        ).add_field(
            name='Python repr',
            value=py_repr
        ).add_field(
            name='More info',
            value=f'[Click here](http://www.fileformat.info/info/unicode/char/{c_ord:x})'
        ).set_footer(
            text=f'Character {menu.current_page + 1} of {self.get_max_pages()}'
        )


class CharInfo(BaseCog):
    """Commands for getting information about unicode characters."""

    @commands.max_concurrency(1)
    @commands.command()
    async def charinfo(self, ctx: MyContext, *, characters: str):
        """Shows you information about a number of characters."""

        units = [
            (0xFFFF0000, 8, 'U'),
            (0xFF00, 4, 'u'),
            (0xFF, 2, 'x'),
        ]

        def as_hex_str(c: str, default: typing.Optional[str] = None) -> str:
            c_ord = ord(c)
            try:
                return '\\{2}{{:0{1}x}}'.format(*discord.utils.find(lambda x: c_ord & x[0], units)).format(c_ord)
            except ValueError:
                if default is not None:
                    return default
                raise ValueError('unable to parse unicode codepoint')

        entries: list[tuple[str, str, str]] = [(
            c,
            as_hex_str(c, 'Internal error'),
            unicodedata.name(c, 'Name not found')
        ) for c in characters]
        page_source = CharInfoMenu(entries, per_page=1)
        menu = NavMenuPages(page_source, delete_message_after=True)
        await menu.start(ctx, wait=True)


def setup(bot: 'PikalaxBOT'):
    bot.add_cog(CharInfo(bot))
