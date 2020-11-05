import asyncio
import discord
from discord.ext import menus


__all__ = 'NavMenuPages',


class NavMenuPages(menus.MenuPages):
    def __init__(self, source, **kwargs):
        super().__init__(source, **kwargs)
        self._in_info = False

    async def go_back_to_current_page(self):
        await asyncio.sleep(30.0)
        await self.show_current_page()

    @menus.button('\N{INPUT SYMBOL FOR NUMBERS}', position=menus.Last(1))
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
