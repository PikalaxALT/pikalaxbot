import discord
from discord.ext import commands, tasks, menus
import asyncio
import traceback
import sqlite3
import aiosqlite
import contextlib
import typing
import time
import re
from .models import PokeapiModels


__all__ = 'PokeApiCog',


TYPE_COLORS = {
    'Normal': 0xA8A77A,
    'Fire': 0xEE8130,
    'Water': 0x6390F0,
    'Electric': 0xF7D02C,
    'Grass': 0x7AC74C,
    'Ice': 0x96D9D6,
    'Fighting': 0xC22E28,
    'Poison': 0xA33EA1,
    'Ground': 0xE2BF65,
    'Flying': 0xA98FF3,
    'Psychic': 0xF95587,
    'Bug': 0xA6B91A,
    'Rock': 0xB6A136,
    'Ghost': 0x735797,
    'Dragon': 0x6F35FC,
    'Dark': 0x705746,
    'Steel': 0xB7B7CE,
    'Fairy': 0xD685AD,
}


class ConfirmationMenu(menus.Menu):
    async def send_initial_message(self, ctx, channel):
        return await ctx.reply('This can take up to 30 minutes. Are you sure?')

    @menus.button('\N{CROSS MARK}')
    async def abort(self, payload):
        await self.message.edit(content='Aborting', delete_after=10)
        self.stop()

    @menus.button('\N{WHITE HEAVY CHECK MARK}')
    async def confirm(self, payload):
        await self.message.edit(content='Confirmed', delete_after=10)
        await self.ctx.cog.do_rebuild_pokeapi(self.ctx)
        self.stop()

    async def finalize(self, timed_out):
        if timed_out:
            await self.message.edit(content='Request timed out', delete_after=10)


class SqlResponseEmbed(menus.ListPageSource):
    async def format_page(self, menu: menus.MenuPages, page):
        return discord.Embed(
            title=menu.sql_cmd,
            description=page,
            colour=0xf47fff
        ).set_footer(
            text=f'Page {menu.current_page + 1}/{self.get_max_pages()} | {menu.row_count} records fetched in {menu.duration * 1000:.1f} ms'
        )


class PokeApiCog(commands.Cog, name='PokeApi'):
    """Commands relating to the bot's local clone of the PokeAPI database."""

    def __init__(self, bot):
        self.bot = bot
        self._lock = asyncio.Lock()

    @contextlib.asynccontextmanager
    async def disable_pokeapi(self):
        factory = self.bot._pokeapi
        self.bot.pokeapi = None
        yield
        self.bot.pokeapi = factory

    def cog_unload(self):
        assert not self._lock.locked(), 'PokeApi is locked'

    async def do_rebuild_pokeapi(self, ctx):
        shell = await asyncio.create_subprocess_shell('../../../setup_pokeapi.sh')
        embed = discord.Embed(title='Updating PokeAPI', description='Started', colour=0xf47fff)
        msg = await ctx.send(embed=embed)

        @tasks.loop(seconds=10)
        async def update_msg():
            elapsed = (update_msg._next_iteration - msg.created_at).total_seconds()
            embed.description = f'Still running... ({elapsed:.0f}s)'
            await msg.edit(embed=embed)

        @update_msg.before_loop
        async def update_before():
            await asyncio.sleep(10)

        done, pending = await asyncio.wait({update_msg.start(), self.bot.loop.create_task(shell.wait)}, return_when=asyncio.FIRST_COMPLETED)
        [task.cancel() for task in pending]
        try:
            done.pop().result()
        except Exception as e:
            embed.colour = discord.Colour.red()
            tb = ''.join(traceback.format_exception(e.__class__, e, e.__traceback__))
            if len(tb) > 2040:
                tb = '...\n' + tb[-2036:]
            embed.title = 'Update failed'
            embed.description = f'```\n{tb}\n```'
        else:
            embed.colour = discord.Colour.green()
            embed.title = 'Update succeeded!'
            embed.description = 'You can now use pokeapi again'
        await msg.edit(embed=embed)

    @commands.group()
    async def pokeapi(self, ctx):
        """Commands for interfacing with pokeapi"""

    @commands.max_concurrency(1)
    @commands.is_owner()
    @pokeapi.command(name='rebuild', aliases=['update'])
    async def rebuild_pokeapi(self, ctx):
        """Rebuild the pokeapi database"""

        async with self._lock, self.disable_pokeapi():
            menu = ConfirmationMenu(timeout=60.0, clear_reactions_after=True)
            await menu.start(ctx, wait=True)

    @pokeapi.command(name='sql')
    @commands.is_owner()
    async def execute_sql(self, ctx: commands.Context, *, query):
        """Run arbitrary sql command"""

        async with ctx.typing():
            pokeapi = self.bot.pokeapi
            start = time.perf_counter()
            async with pokeapi.execute(query) as cur:  # type: aiosqlite.Cursor
                records = await cur.fetchall()
            end = time.perf_counter()
            header = '|'.join(col[0] for col in cur.description)
            pag = commands.Paginator(f'```\n{header}\n{"-" * len(header)}', max_size=2048)
            for i, row in enumerate(records, 1):  # type: [int, tuple]
                pag.add_line('|'.join(map(str, row)))
                if i % 20 == 0:
                    pag.close_page()

        if pag.pages:
            menu = menus.MenuPages(SqlResponseEmbed(pag.pages, per_page=1), delete_message_after=True, clear_reactions_after=True)
            menu.sql_cmd = query if len(query) < 256 else '...' + query[-253:]
            menu.duration = end - start
            menu.row_count = i
            await menu.start(ctx)
        else:
            await ctx.send('Operation completed, no rows returned.', delete_after=10)
        await ctx.message.add_reaction('\N{white heavy check mark}')

    @execute_sql.error
    async def pokeapi_sql_error(self, ctx, error):
        if isinstance(error, commands.CommandInvokeError):
            error = error.original
        if isinstance(error, sqlite3.Error):
            query = ctx.kwargs['query']
            query = query if len(query) < 256 else '...' + query[-253:]
            await ctx.message.add_reaction('\N{cross mark}')
            embed = discord.Embed(
                title=query,
                description=f'**ERROR**: {error}',
                colour=discord.Colour.red()
            )
            await ctx.send(embed=embed)

    @pokeapi.command(name='info')
    async def mon_info(self, ctx: commands.Context, pokemon: PokeapiModels.PokemonSpecies):
        """Gets information about a Pokémon species"""

        async with ctx.typing():
            base_stats: typing.Mapping[str, int] = await self.bot.pokeapi.get_base_stats(pokemon)
            types: typing.List[PokeapiModels.Type] = await self.bot.pokeapi.get_mon_types(pokemon)
            egg_groups: typing.List[PokeapiModels.EggGroup] = await self.bot.pokeapi.get_egg_groups(pokemon)
            image_url: str = await self.bot.pokeapi.get_species_sprite_url(pokemon)
            flavor_text: typing.Optional[str] = await self.bot.pokeapi.get_mon_flavor_text(pokemon)
            evos: typing.List[PokeapiModels.PokemonSpecies] = await self.bot.pokeapi.get_evos(pokemon)
        embed = discord.Embed(
            title=f'{pokemon.name} (#{pokemon.id})',
            description=flavor_text or 'No flavor text',
            colour=TYPE_COLORS[types[0].name]
        ).add_field(
            name='Generation',
            value=pokemon.generation.name or 'Unknown'
        ).add_field(
            name='Types',
            value='/'.join(type_.name for type_ in types) or 'Unknown'
        ).add_field(
            name='Base Stats',
            value='\n'.join(f'{stat}: {value}' for stat, value in base_stats.items()) + f'\n**Total:** {sum(base_stats.values())}' or 'Unknown'
        ).add_field(
            name='Egg Groups',
            value='/'.join(grp.name for grp in egg_groups) or 'Unknown'
        ).add_field(
            name='Gender Ratio',
            value=f'{12.5 * pokemon.gender_rate}% Female' if pokemon.gender_rate >= 0 else 'Gender Unknown' or 'Unknown'
        ).set_image(url=image_url or discord.Embed.Empty)
        if pokemon.evolves_from_species:
            preevo_str = f'Evolves from {pokemon.evolves_from_species.name} (#{pokemon.evolves_from_species.id})\n'
        else:
            preevo_str = ''
        if evos:
            preevo_str += 'Evolves into ' + ', '.join(f'{mon.name} (#{mon.id})' for mon in evos)
        embed.add_field(
            name='Evolution',
            value=preevo_str or 'No evolutions'
        )
        await ctx.send(embed=embed)

    @commands.command(usage='<mon>, <move>')
    async def learn(self, ctx, *, query: re.compile(r', *').split):
        """Get whether the given pokemon can learn the given move"""
        if len(query) > 2:
            raise commands.BadArgument('mon, move')
        mon = await self.bot.pokeapi.get_species_by_name(query[0])
        if mon is None:
            return await ctx.send(f'Could not find a Pokémon named "{query[0]}"')
        async with self.bot.pokeapi.replace_row_factory(PokeapiModels.PokemonMove) as conn, ctx.typing():
            movelearns = await conn.execute_fetchall("""
            SELECT *
            FROM pokemon_v2_pokemonmove pv2pm
            INNER JOIN pokemon_v2_pokemon pv2p on pv2p.id = pv2pm.pokemon_id
            WHERE pokemon_species_id = :id
            AND is_default = TRUE
            ORDER BY version_group_id, 'order'
            """, {'id': mon.id})
        if not movelearns:
            return await ctx.send('I do not know anything about this Pokémon\'s move learns yet')
        if len(query) == 1:
            class MoveLearnPageSource(menus.ListPageSource):
                async def format_page(self, menu, page: list[PokeapiModels.PokemonMove]):
                    embed = discord.Embed(
                        title=f'{mon}\'s learnset'
                    ).set_footer(text=f'Page {menu.current_page + 1}/{self.get_max_pages()}')
                    for movelearn in page:
                        method = f'Level {movelearn.level}' if movelearn.move_learn_method.id == 1 else str(movelearn.move_learn_method)
                        embed.add_field(
                            name=str(movelearn.move),
                            value=f'Method: {method}\n'
                                  f'{movelearn.version_group.name.title().replace("-", ", ")}'
                        )
                    return embed

            menu = menus.MenuPages(MoveLearnPageSource(movelearns, per_page=12), clear_reactions_after=True, delete_message_after=True)
            await menu.start(ctx)
        else:
            move = await self.bot.pokeapi.get_move_by_name(query[1])
            if move is None:
                return await ctx.send(f'Could not find a move named "{query[1]}"')
            flag = 'can' if await self.bot.pokeapi.mon_can_learn_move(mon, move) else 'cannot'
            await ctx.send(f'{mon} **{flag}** learn {move}.')
