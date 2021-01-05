import asyncio
import discord
from discord.ext import menus


__all__ = 'NavMenuPages',


class NavMenuPages(menus.MenuPages):
    def __init__(self, source: menus.PageSource, **kwargs):
        super().__init__(source, **kwargs)
        self._in_info = False

    async def go_back_to_current_page(self):
        await asyncio.sleep(30.0)
        await self.show_current_page()

    @menus.button('\N{INPUT SYMBOL FOR NUMBERS}', position=menus.Last(1.5))
    async def pick_page(self, payload: discord.RawReactionActionEvent):
        """lets you type a page number to go to"""

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

    @menus.button('\N{INFORMATION SOURCE}', position=menus.Last(3))
    async def info(self, payload: discord.RawReactionActionEvent):
        """shows this message"""

        self._in_info = not self._in_info
        if self._in_info:
            embed = discord.Embed(title='Paginator help', description='Hello! Welcome to the help page.')
            value = '\n'.join(f'{emoji}: {button.action.__doc__}' for emoji, button in self.buttons.items())
            embed.add_field(name='What are these reactions for?', value=value)
            embed.set_footer(text=f'We were on page {self.current_page + 1} before this message.')
            await self.message.edit(embed=embed)
            task = self.bot.loop.create_task(self.go_back_to_current_page())

            def on_done():
                self._in_info = False

            task.add_done_callback(on_done)
        else:
            await self.show_current_page()
