import discord
from discord.ext import commands, menus
from . import BaseCog
import datetime
import aiosqlite


class PaginatorPageSource(menus.ListPageSource):
    def __init__(self, paginator: commands.Paginator):
        super().__init__(paginator.pages, per_page=1)

    async def format_page(self, menu, page):
        return page


class CustomCommands(BaseCog):
    async def is_elevated(self, user):
        return user.guild_permissions.manage_messages or await self.bot.is_owner(user)

    async def init_db(self, sql):
        await sql.execute('create table if not exists custom_commands (guild_id integer, owner_id integer, invoke_with text, template text, uses integer default 0, created_at real)')
        await sql.execute('create unique index if not exists custom_commands_idx on custom_commands (guild_id, invoke_with)')

    async def custom_command_callback(self, ctx, *fields):
        try:
            await ctx.send(ctx._cc_template.format(*fields))
        except IndexError:
            await ctx.send('Missing one or more required arguments')
        else:
            async with self.bot.sql as sql:
                await sql.execute('update custom_commands set uses = uses + 1 where guild_id = ? and invoke_with = ?', (ctx.guild.id, ctx.invoked_with))

    @BaseCog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return
        ctx = await self.bot.get_context(message)
        if ctx.valid or not (ctx.prefix and ctx.invoked_with):
            return
        try:
            async with self.bot.sql as sql:
                async with sql.execute('select template from custom_commands where guild_id = ? and invoke_with = ?', (ctx.guild.id, ctx.invoked_with)) as cur:
                    template, = await cur.fetchone()
        except TypeError:
            return
        ctx.command = commands.command(name=ctx.invoked_with)(self.custom_command_callback)
        ctx._cc_template = template
        await self.bot.invoke(ctx)

    @commands.guild_only()
    @commands.group()
    async def cmd(self, ctx):
        """Commands for creating custom commands

        Command templates are evaluated using str.format.
        Use {} for placeholders for additional args on
        invoke."""

    @cmd.command(aliases=['create', 'mk', 'new'])
    async def add(self, ctx, invoke_with, *, template):
        """Create a new custom command"""

        if self.bot.get_command(invoke_with):
            return await ctx.send(f'A global command named "{invoke_with}" already exists')
        try:
            async with self.bot.sql as sql:
                await sql.execute_insert('insert into custom_commands values (?, ?, ?, ?, 0, ?)', (ctx.guild.id, ctx.author.id, invoke_with, template, ctx.message.created_at.timestamp()))
        except aiosqlite.OperationalError:
            return await ctx.send(f'A custom command named "{invoke_with}" already exists')
        await ctx.send(f'A custom command named "{invoke_with}" was successfully created')

    @cmd.command(aliases=['rm', 'del', 'delete'])
    async def remove(self, ctx, invoke_with):
        """Remove an existing custom command"""

        async with self.bot.sql as sql:
            try:
                await sql.execute('delete from custom_commands where guild_id = ? and invoke_with = ? and owner_id = ?', (ctx.guild.id, invoke_with, ctx.author.id))
            except aiosqlite.OperationalError:
                if not await self.is_elevated(ctx.author):
                    return await ctx.send('You do not own this command or it does not exist')
                try:
                    await sql.execute('delete from custom_commands where guild_id = ? and invoke_with = ?', (ctx.guild.id, invoke_with))
                except aiosqlite.OperationalError:
                    return await ctx.send('Command not found')
        await ctx.send(f'Custom command "{invoke_with}" deleted')

    @cmd.command()
    async def edit(self, ctx, invoke_with, *, new_template):
        """Update an existing custom command"""

        async with self.bot.sql as sql:
            try:
                await sql.execute('update custom_commands set template = ? where guild_id = ? and invoke_with = ? and owner_id = ?', (new_template, ctx.guild.id, invoke_with, ctx.author.id))
            except aiosqlite.OperationalError:
                if not await self.is_elevated(ctx.author):
                    return await ctx.send('You do not own this command or it does not exist')
                try:
                    await sql.execute('update custom_commands set template = ? where guild_id = ? and invoke_with = ?', (new_template, ctx.guild.id, invoke_with))
                except aiosqlite.OperationalError:
                    return await ctx.send('Command not found')
        await ctx.send(f'Custom command "{invoke_with}" updated')

    @cmd.group(name='list', invoke_without_command=True)
    async def list_cmds(self, ctx, *, owner: discord.Member = None):
        """List all your commands, or commands owned by the specified member."""

        owner = owner or ctx.author
        pag = commands.Paginator(prefix=f'**{owner.display_name}\'s commands:**\n```')
        async with self.bot.sql as sql:
            async with sql.execute('select invoke_with from custom_commands where guild_id = ? and owner_id = ?', (ctx.guild.id, owner.id)) as cur:
                async for record, in cur:
                    pag.add_line(record)
        if not pag.pages:
            return await ctx.send(f'{owner.display_name} owns no custom commands in this guild')
        page_source = PaginatorPageSource(pag)
        menu = menus.MenuPages(page_source, delete_message_after=True)
        await menu.start(ctx, wait=True)

    @list_cmds.command('all')
    async def list_all_cmds(self, ctx):
        """List all commands in the server."""

        pag = commands.Paginator(prefix=f'**{ctx.guild}\'s commands:**\n```')
        async with self.bot.sql as sql:
            async with sql.execute('select invoke_with from custom_commands where guild_id = ?', (ctx.guild.id,)) as cur:
                async for record, in cur:
                    pag.add_line(record)
        if not pag.pages:
            return await ctx.send('No custom commands in this guild')
        page_source = PaginatorPageSource(pag)
        menu = menus.MenuPages(page_source, delete_message_after=True)
        await menu.start(ctx, wait=True)

    @cmd.command(name='info')
    async def cmd_info(self, ctx, invoke_with):
        """Get info about a given command"""

        try:
            async with self.bot.sql as sql:
                async with sql.execute('select owner_id, template, uses, created_at from custom_commands where guild_id = ? and invoke_with = ?', (ctx.guild.id, invoke_with)) as cur:
                    owner_id, template, uses, created_at = await cur.fetchone()
        except ValueError:
            return await ctx.send(f'No command found in this guild named {invoke_with}')
        try:
            owner = ctx.guild.get_member(owner_id) or await self.bot.fetch_user(owner_id)
        except discord.NotFound:
            owner = None
        if owner:
            mention = f'**Owner mention:** {owner.mention}\n'
        else:
            mention = ''
        embed = discord.Embed(
            title=f'{ctx.prefix}{invoke_with}',
            description=f'**Owner ID:** {owner_id}\n'
                        f'{mention}'
                        f'**Template:** {template}\n'
                        f'**Uses:** {uses}',
            colour=discord.Colour.blurple()
        )
        if owner:
            embed.set_author(name=str(owner), icon_url=str(owner.avatar_url))
        else:
            embed.set_author(name='Owner not found', icon_url=str(ctx.author.default_avatar_url))
        embed.timestamp = datetime.datetime.fromtimestamp(created_at)
        await ctx.send(embed=embed)

    @cmd.command(name='raw')
    async def get_raw_cmd(self, ctx, invoke_with):
        """Get the raw version of the custom command"""

        try:
            async with self.bot.sql as sql:
                async with sql.execute('select template from custom_commands where guild_id = ? and invoke_with = ?', (ctx.guild.id, invoke_with)) as cur:
                    template, = await cur.fetchone()
        except TypeError:
            return await ctx.send('Command not found')
        await ctx.send(discord.utils.escape_markdown(template))


def setup(bot):
    bot.add_cog(CustomCommands(bot))
