import discord
from discord.ext import commands, tasks, menus
import asyncio
import sqlite3
from . import asqlite3
import contextlib
import typing
import time
import re
import itertools
from .models import PokeapiModels
from textwrap import indent
import traceback


__all__ = 'PokeApiCog',


CommaSeparatedArgs = re.compile(r',\s*').split
type_pat = re.compile(r'\s*type$', re.I)
egg_group_pat = re.compile('\s*egg\s*group$', re.I)


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


DEX_COLORS = (
    0,         # null
    0x585858,  # Black
    0x3088F0,  # Blue
    0xB07030,  # Brown
    0xA0A0A0,  # Gray
    0x40B868,  # Green
    0xF890C8,  # Pink
    0xA868C0,  # Purple
    0xF05868,  # Red
    0xF0F0F0,  # White
    0xF0D048,  # Yellow
)


class Paginator(commands.Paginator):
    def __init__(self, prefix='```', suffix='```', max_size=2000, max_per_page=0):
        super().__init__(prefix, suffix, max_size)
        self.max_per_page = max_per_page

    def add_line(self, line='', *, empty=False):
        max_page_size = self.max_size - self._prefix_len - self._suffix_len - 2
        if len(line) > max_page_size:
            raise RuntimeError('Line exceeds maximum page size %s' % (max_page_size))

        if self._count + len(line) + 1 > self.max_size - self._suffix_len \
                or self.max_per_page and len(self._current_page) >= self.max_per_page:
            self.close_page()

        self._count += len(line) + 1
        self._current_page.append(line)

        if empty:
            self._current_page.append('')
            self._count += 1


class DexsearchParseError(commands.UserInputError):
    pass


async def dexsearch_check(ctx: commands.Context):
    cog = ctx.bot.get_cog('Q20Game')
    if cog and cog[ctx.channel.id].running:
        raise commands.CheckFailure('Dexsearch is banned in this channel while Q20 is running')
    return True


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
            async with self.bot.pokeapi.replace_row_factory(None) as pokeapi:
                start = time.perf_counter()
                async with pokeapi.execute(query) as cur:  # type: asqlite3.Cursor
                    records = await cur.fetchall()
                    end = time.perf_counter()
            header = '|'.join(col[0] for col in cur.description)
            pag = commands.Paginator(max_size=2048)
            for i, row in enumerate(records, 1):  # type: [int, tuple]
                to_add = '|'.join(map(str, row))
                if len(header) * 2 + len(to_add) > 2040:
                    raise ValueError('At least one page of results is too long to fit. Try returning fewer columns?')
                if pag._count + len(to_add) + 1 > 2045 or len(pag._current_page) >= 21:
                    pag.close_page()
                    pag.add_line(header)
                    pag.add_line('-' * len(header))
                pag.add_line(to_add)

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

    async def mon_info(self, ctx: commands.Context, pokemon: PokeapiModels.PokemonSpecies):
        """Gets information about a Pokémon species"""

        async with ctx.typing():
            base_stats: typing.Mapping[str, int] = await self.bot.pokeapi.get_base_stats(pokemon)
            types: typing.List[PokeapiModels.Type] = await self.bot.pokeapi.get_mon_types(pokemon)
            egg_groups: typing.List[PokeapiModels.EggGroup] = await self.bot.pokeapi.get_egg_groups(pokemon)
            image_url: str = await self.bot.pokeapi.get_species_sprite_url(pokemon)
            flavor_text: typing.Optional[str] = await self.bot.pokeapi.get_mon_flavor_text(pokemon)
            evos: typing.List[PokeapiModels.PokemonSpecies] = await self.bot.pokeapi.get_evos(pokemon)
            abilities: typing.List[PokeapiModels.PokemonAbility] = await self.bot.pokeapi.get_mon_abilities_with_flags(pokemon)
            forme: PokeapiModels.PokemonForm = await self.bot.pokeapi.get_default_forme(pokemon)
        embed = discord.Embed(
            title=f'{pokemon.name} (#{pokemon.id})',
            description=flavor_text or 'No flavor text',
            colour=DEX_COLORS[pokemon.pokemon_color.id]
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
        ).set_thumbnail(url=image_url or discord.Embed.Empty)
        if pokemon.evolves_from_species:
            preevo_str = f'Evolves from {pokemon.evolves_from_species.name} (#{pokemon.evolves_from_species.id})\n'
        else:
            preevo_str = ''
        if evos:
            preevo_str += 'Evolves into ' + ', '.join(f'{mon.name} (#{mon.id})' for mon in evos)
        embed.add_field(
            name='Evolution',
            value=preevo_str or 'No evolutions'
        ).add_field(
            name='Abilities',
            value=', '.join(f'_{ability.ability.name}_' if ability.is_hidden else ability.ability.name for ability in abilities) or 'Unknown'
        ).add_field(
            name='Biometrics',
            value=f'Height: {forme.pokemon.height / 10:.1f}m\n'
                  f'Weight: {forme.pokemon.weight / 10:.1f}kg'
        )
        await ctx.send(embed=embed)

    async def move_info(self, ctx: commands.Context, move: PokeapiModels.Move):
        async with ctx.typing():
            attrs: typing.List[PokeapiModels.MoveAttribute] = await self.bot.pokeapi.get_move_attrs(move)
            flavor_text: typing.Optional[str] = await self.bot.pokeapi.get_move_description(move)
            machines: typing.List[PokeapiModels.Machine] = await self.bot.pokeapi.get_machines_teaching_move(move)
        embed = discord.Embed(
            title=f'{move.name} (#{move.id})',
            description=flavor_text or 'No flavor text',
            colour=TYPE_COLORS[move.type.name]
        ).add_field(
            name='Type',
            value=f'Battle: {move.type.name}\n'
                  f'Contest: {move.contest_type.name}'
        ).add_field(
            name='Stats',
            value=f'**Power:** {move.power}\n'
                  f'**Accuracy:** {move.accuracy}\n'
                  f'**Max PP:** {move.pp}\n'
                  f'**Priority:** {move.priority}'
        ).add_field(
            name='Generation',
            value=move.generation.name
        ).add_field(
            name='Attributes',
            value=indent('\n'.join(attr.name for attr in attrs), '\N{WHITE HEAVY CHECK MARK} ') or '\N{CROSS MARK} None'
        ).add_field(
            name='Effect',
            value=f'**Battle:** {move.effect.short_effect}\n'
                  f'**Contest:** {move.contest_effect.effect}\n'
                  f'**Super Contest:** {move.super_contest_effect.flavor_text}'
        ).add_field(
            name='Target',
            value=move.target.name
        )
        if machines:
            machines.sort(key=lambda m: (m.version_group.id, m.number))
            machine_s = []
            for gen, machs in itertools.groupby(machines, lambda m: m.version_group.generation):
                mach_s = set()
                for mach in machs:
                    if mach.number < 100:
                        mach_no_s = f'TM{mach.number:02d}'
                    else:
                        mach_no_s = f'HM{mach.number - 100:02d}'
                    mach_s.add(mach_no_s)
                machine_s.append(f'**{gen.name}:** {", ".join(mach_s)}')
            embed.add_field(
                name='Machines',
                value='\n'.join(machine_s)
            )
        await ctx.send(embed=embed)

    @pokeapi.command(name='info')
    async def mon_or_move_info(self, ctx: commands.Context, *, entity: typing.Union[PokeapiModels.PokemonSpecies, PokeapiModels.Move]):
        """Gets information about a Pokémon species or move"""

        if isinstance(entity, PokeapiModels.PokemonSpecies):
            return await self.mon_info(ctx, entity)
        else:
            return await self.move_info(ctx, entity)

    @commands.command(aliases=['dt'])
    async def details(self, ctx: commands.Context, *, entity: typing.Union[PokeapiModels.PokemonSpecies, PokeapiModels.Move]):
        """Gets information about a Pokémon species or move"""

        await self.mon_or_move_info(ctx, entity=entity)

    @mon_or_move_info.error
    @details.error
    async def details_error(self, ctx: commands.Context, exc: commands.CommandError):
        if isinstance(exc, commands.BadUnionArgument):
            await ctx.send(f'No Pokemon or move named "{exc.errors[0].args[1]}"')
        else:
            if isinstance(exc, commands.CommandInvokeError):
                exc = exc.original
            await self.bot.send_tb(ctx, exc, ignoring=f'Ignoring exception in {ctx.command}:')

    @commands.command(usage='<mon>, <move>')
    async def learn(self, ctx, *, query: CommaSeparatedArgs):
        """Get whether the given pokemon can learn the given move"""
        if len(query) > 2:
            raise commands.BadArgument('mon, move')
        mon = await self.bot.pokeapi.get_species_by_name(query[0])
        if mon is None:
            return await ctx.send(f'Could not find a Pokémon named "{query[0]}"')
        async with self.bot.pokeapi.replace_row_factory(PokeapiModels.PokemonMove) as conn, ctx.typing():
            movelearns = {
                move: list(group)
                for move, group in itertools.groupby(await conn.execute_fetchall("""
            SELECT *
            FROM pokemon_v2_pokemonmove pv2pm
            INNER JOIN pokemon_v2_pokemon pv2p on pv2p.id = pv2pm.pokemon_id
            INNER JOIN pokemon_v2_versiongroup pv2v on pv2v.id = pv2pm.version_group_id
            WHERE pokemon_species_id = :id
            AND is_default = TRUE
            GROUP BY pv2pm.move_id, pv2v.generation_id, pv2v.id, move_learn_method_id, pv2pm.level
            """, {'id': mon.id}), lambda ml: ml.move)}
        if not movelearns:
            return await ctx.send('I do not know anything about this Pokémon\'s move learns yet')
        if len(query) == 1:
            types = await self.bot.pokeapi.get_mon_types(mon)

            class MoveLearnPageSource(menus.ListPageSource):
                async def format_page(self, menu: menus.MenuPages, page: list[PokeapiModels.PokemonMove]):
                    embed = discord.Embed(
                        title=f'{mon}\'s learnset',
                        colour=TYPE_COLORS[types[0].name]
                    ).set_footer(text=f'Page {menu.current_page + 1}/{self.get_max_pages()}')
                    for move, movelearns in page:
                        value = '\n'.join(
                            f'**{gen}:** ' + ', '.join(set(
                                f'Level {ml.level}'
                                if ml.move_learn_method.id == 1
                                else str(ml.move_learn_method)
                                for ml in mls))
                            for gen, mls
                            in itertools.groupby(
                                movelearns,
                                lambda ml: ml.version_group.generation
                            )
                        )
                        embed.add_field(
                            name=str(move),
                            value=value
                        )
                    return embed

            menu = menus.MenuPages(MoveLearnPageSource(list(movelearns.items()), per_page=6), clear_reactions_after=True, delete_message_after=True)
            await menu.start(ctx)
        else:
            move = await self.bot.pokeapi.get_move_by_name(query[1])
            if move is None:
                return await ctx.send(f'Could not find a move named "{query[1]}"')
            flag = 'can' if move in movelearns else 'cannot'
            await ctx.send(f'{mon} **{flag}** learn {move}.')

    async def ds_parse_one(self, fullterm: str) -> typing.Tuple:
        notsearch, term = re.match(r'^(!?)(.+?)$', fullterm).groups()
        if m := re.match(r'^(g(en)?)? ?([1-8])$', term, flags=re.I):
            gen = int(m[3])
            return """
            SELECT pv2psn.name
            FROM pokemon_v2_pokemonspeciesname pv2psn
            INNER JOIN pokemon_v2_pokemonspecies pv2ps on pv2psn.pokemon_species_id = pv2ps.id
            WHERE pv2ps.generation_id = ?
            AND pv2psn.language_id = 9
            """, gen
        elif move := await self.bot.pokeapi.get_model_named('Move', term):
            return """
            SELECT pv2psn.name
            FROM pokemon_v2_pokemonspeciesname pv2psn
            INNER JOIN pokemon_v2_pokemon pv2p ON pv2psn.pokemon_species_id = pv2p.pokemon_species_id
            INNER JOIN pokemon_v2_pokemonmove pv2pm ON pv2p.id = pv2pm.pokemon_id
            WHERE pv2psn.language_id = 9
            AND pv2p.is_default = TRUE
            AND pv2pm.move_id = ?
            """, move.id
        elif type_ := await self.bot.pokeapi.get_model_named('Type', type_pat.sub('', term)):
            return """
            SELECT pv2psn.name
            FROM pokemon_v2_pokemonspeciesname pv2psn
            INNER JOIN pokemon_v2_pokemon pv2p ON pv2psn.pokemon_species_id = pv2p.pokemon_species_id
            INNER JOIN pokemon_v2_pokemontype pv2pt ON pv2p.id = pv2pt.pokemon_id
            WHERE pv2psn.language_id = 9
            AND pv2p.is_default = TRUE
            AND pv2pt.type_id = ?
            """, type_.id
        elif ability := await self.bot.pokeapi.get_model_named('Ability', term):
            return """
            SELECT pv2psn.name
            FROM pokemon_v2_pokemonspeciesname pv2psn
            INNER JOIN pokemon_v2_pokemon pv2p ON pv2psn.pokemon_species_id = pv2p.pokemon_species_id
            INNER JOIN pokemon_v2_pokemonability pv2pa ON pv2p.id = pv2pa.pokemon_id
            WHERE pv2psn.language_id = 9
            AND pv2p.is_default = TRUE
            AND pv2pa.ability_id = ?
            """, ability.id
        elif color := await self.bot.pokeapi.get_model_named('PokemonColor', term):
            return """
            SELECT pv2psn.name
            FROM pokemon_v2_pokemonspeciesname pv2psn
            INNER JOIN pokemon_v2_pokemonspecies pv2ps ON pv2psn.pokemon_species_id = pv2ps.id
            WHERE pv2psn.language_id = 9
            AND pv2ps.pokemon_color_id = ?
            """, color.id,
        elif egg_group := await self.bot.pokeapi.get_model_named('EggGroup', egg_group_pat.sub('', term)):
            return """
            SELECT pv2psn.name
            FROM pokemon_v2_pokemonspeciesname pv2psn
            INNER JOIN pokemon_v2_pokemonegggroup pv2peg ON pv2psn.pokemon_species_id = pv2peg.pokemon_species_id
            WHERE pv2psn.language_id = 9
            AND pv2peg.egg_group_id = ?
            """, egg_group.id
        elif re.match(r'^megas?$', term, re.I):
            return """
            SELECT pv2psn.name
            FROM pokemon_v2_pokemonspeciesname pv2psn
            INNER JOIN pokemon_v2_pokemon pv2p ON pv2psn.pokemon_species_id = pv2p.pokemon_species_id
            INNER JOIN pokemon_v2_pokemonform pv2pf on pv2p.id = pv2pf.pokemon_id
            WHERE pv2psn.language_id = 9
            AND pv2pf.is_mega = TRUE
            """,
        elif re.match(r'^(mono(type)?|single)$', term, re.I):
            return """
            SELECT pv2psn.name
            FROM pokemon_v2_pokemonspeciesname pv2psn
            INNER JOIN pokemon_v2_pokemon pv2p ON pv2psn.pokemon_species_id = pv2p.pokemon_species_id
            INNER JOIN pokemon_v2_pokemontype pv2pt ON pv2p.id = pv2pt.pokemon_id
            WHERE pv2psn.language_id = 9
            AND pv2p.is_default = TRUE
            GROUP BY pv2psn.pokemon_species_id
            HAVING COUNT(pv2pt.type_id) = 1
            """,
        elif re.match(r'^g(iganta)?max$', term, re.I):
            return """
            SELECT pv2psn.name
            FROM pokemon_v2_pokemonspeciesname pv2psn
            INNER JOIN pokemon_v2_pokemon pv2p ON pv2psn.pokemon_species_id = pv2p.pokemon_species_id
            INNER JOIN pokemon_v2_pokemonform pv2pf on pv2p.id = pv2pf.pokemon_id
            WHERE pv2psn.language_id = 9
            AND pv2pf.id > 10412
            """,
        elif re.match(r'^(fe|fully ?evolved)$', term, re.I):
            return """
            SELECT pv2psn.name
            FROM pokemon_v2_pokemonspeciesname pv2psn
            INNER JOIN pokemon_v2_pokemonspecies pv2ps ON pv2psn.pokemon_species_id = pv2ps.id
            WHERE pv2psn.language_id = 9
            AND NOT EXISTS (
                SELECT *
                FROM pokemon_v2_pokemonspecies pv2ps2
                WHERE pv2ps2.evolves_from_species_id = pv2ps.id
            )
            """,
        elif m := re.match(r'^(?P<stat>((?P<special>special|sp[acd]?)\s*)?(?P<attack>at(tac)?k)|(?P<defense>def(en[cs]e)?)|(?P<speed>spe(ed)?)|(?P<hp>hp))\s*(?P<ineq>[<>!]?=|[<>])\s*(?P<value>\d+)$', term, re.I):
            special = m['special'] is not None
            attack = m['attack'] is not None
            defense = m['defense'] is not None
            speed = m['speed'] is not None
            hp = m['hp'] is not None
            assert not (special and (speed or hp)), f'Special {"Speed" if speed else "HP"} is not a thing.'
            stat_id = None
            if hp:
                stat_id = 1
            elif attack:
                stat_id = 2 + 2 * special
            elif defense:
                stat_id = 3 + 2 * special
            elif speed:
                stat_id = 6
            elif special:
                if m['special'] in ('spa', 'spc'):
                    stat_id = 4
                elif m['special'] == 'spd':
                    stat_id = 5
            if stat_id is None:
                raise ValueError('invalid stat: %s' % m['stat'])
            # We use unsafe sql injection here because this is just
            # too complicated to do with args
            return """
            SELECT pv2psn.name
            FROM pokemon_v2_pokemonspeciesname pv2psn
            INNER JOIN pokemon_v2_pokemon pv2p ON pv2psn.pokemon_species_id = pv2p.pokemon_species_id
            INNER JOIN pokemon_v2_pokemonstat pv2pst ON pv2p.id = pv2pst.pokemon_id
            WHERE pv2psn.language_id = 9
            AND pv2p.is_default = TRUE
            AND pv2pst.stat_id = ?
            AND pv2pst.base_stat {} ?
            """.format(m['ineq']), stat_id, m['value']
        elif m := re.match(r'^(?P<stat>bst)\s*(?P<ineq>[<>!]?=|[<>])\s*(?P<value>\d+)$', term, re.I):
            # We use unsafe sql injection here because this is just
            # too complicated to do with args
            return """
            SELECT pv2psn.name
            FROM pokemon_v2_pokemonspeciesname pv2psn
            INNER JOIN pokemon_v2_pokemon pv2p ON pv2psn.pokemon_species_id = pv2p.pokemon_species_id
            INNER JOIN pokemon_v2_pokemonstat pv2pst ON pv2p.id = pv2pst.pokemon_id
            WHERE pv2psn.language_id = 9
            AND pv2p.is_default = TRUE
            GROUP BY pv2psn.pokemon_species_id
            HAVING SUM(pv2pst.base_stat) {} ?
            """.format(m['ineq']), m['value']
        elif m := re.match(r'^(?P<measure>height|weight)\s*(?P<ineq>[<>!]?=|[<>])\s+(?P<amount>(\d+(\.\d+)?|\.\d+))\s*(?P<units>(m(eters?)?|k(ilo)?g(rams?)?)?)', term, re.I):
            return """
            SELECT pv2psn.name
            FROM pokemon_v2_pokemonspeciesname pv2psn
            INNER JOIN pokemon_v2_pokemon pv2p ON pv2psn.pokemon_species_id = pv2p.pokemon_species_id
            WHERE pv2psn.language_id = 9
            AND pv2p.is_default = TRUE
            AND pv2p.{} {} ?
            """.format(m['measure'], m['ineq']), float(m['amount']) * 10
        elif m := re.match(r'^(?P<direction>weak|resists)\s*(?P<type>.+)$', term, re.I):
            is_flying_press = False
            type_ = await self.bot.pokeapi.get_model_named('Type', type_pat.sub('', m['type']))
            if type_ is None:
                move = await self.bot.pokeapi.get_model_named('Move', m['type'])  # type: PokeapiModels.Move
                if move is None:
                    raise DexsearchParseError('No type or move named {}'.format(m['type']))
                if move.move_damage_class.id == 1:
                    raise DexsearchParseError('{} is a status move and can\'t be used with {}'.format(move.name, m['direction']))
                type_ = move.type
                is_flying_press = move.name == 'Flying Press'
            args = (type_.id,)
            if is_flying_press:
                args += (3,)
            return """
            SELECT pv2psn.name
            FROM pokemon_v2_pokemonspeciesname pv2psn
            INNER JOIN pokemon_v2_pokemon pv2p ON pv2psn.pokemon_species_id = pv2p.pokemon_species_id
            INNER JOIN pokemon_v2_pokemontype pv2pt ON pv2p.id = pv2pt.pokemon_id
            INNER JOIN pokemon_v2_typeefficacy pv2te ON pv2pt.type_id = pv2te.target_type_id
            WHERE pv2psn.language_id = 9
            AND pv2te.damage_type_id {}
            GROUP BY pv2psn.pokemon_species_id
            HAVING PRODUCT(pv2te.damage_factor / 100.0) {} 1
            """.format('IN (?, ?)' if is_flying_press else '= ?', '>' if m['direction'] == 'weak' else '<'), *args
        elif re.match(r'^legend(ary)?$', term, re.I):
            return """
            SELECT pv2psn.name
            FROM pokemon_v2_pokemonspeciesname pv2psn
            INNER JOIN pokemon_v2_pokemonspecies pv2ps ON pv2psn.pokemon_species_id = pv2ps.id
            WHERE pv2psn.language_id = 9
            AND pv2ps.is_legendary = TRUE
            """,
        elif re.match(r'^bab{1,2}y?$', term, re.I):
            return """
            SELECT pv2psn.name
            FROM pokemon_v2_pokemonspeciesname pv2psn
            INNER JOIN pokemon_v2_pokemonspecies pv2ps ON pv2psn.pokemon_species_id = pv2ps.id
            WHERE pv2psn.language_id = 9
            AND pv2ps.is_baby = TRUE
            """,
        elif re.match(r'^(unevolved|basic|first stage)$', term, re.I):
            return """
            SELECT pv2psn.name
            FROM pokemon_v2_pokemonspeciesname pv2psn
            INNER JOIN pokemon_v2_pokemonspecies pv2ps ON pv2psn.pokemon_species_id = pv2ps.id
            WHERE pv2psn.language_id = 9
            AND pv2ps.evolves_from_species_id IS NULL
            """,
        elif re.match(r'^(evolve[ds])$', term, re.I):
            return """
            SELECT pv2psn.name
            FROM pokemon_v2_pokemonspeciesname pv2psn
            INNER JOIN pokemon_v2_pokemonspecies pv2ps ON pv2psn.pokemon_species_id = pv2ps.id
            INNER JOIN pokemon_v2_pokemonspecies pv2ps2 ON pv2ps.evolution_chain_id = pv2ps2.evolution_chain_id
            WHERE pv2psn.language_id = 9
            GROUP BY pv2ps.id
            HAVING COUNT(*) > 1
            """,
        else:
            raise DexsearchParseError(f'I did not understand your query (first unrecognized term: {fullterm})')

    async def ds_parse(self, term: str):
        args = []
        terms = re.split(r'\s*\|\s*', term)
        statement = ''

        for i, real_term in enumerate(terms):
            new_statement, *new_args = await self.ds_parse_one(real_term)
            if i == 0:
                joiner = """SELECT name FROM pokemon_v2_pokemonspeciesname WHERE language_id = 9 EXCEPT""" if real_term.startswith('!') else ''
            else:
                joiner = 'EXCEPT' if real_term.startswith('!') else 'UNION'
            args += new_args
            statement += f' {joiner} {new_statement}'
        return statement, args

    @commands.check(dexsearch_check)
    @commands.command(aliases=['ds'], usage='<term[, term[, ...]]>')
    async def dexsearch(self, ctx, *, query: CommaSeparatedArgs):
        """Search the pokedex. Valid terms: generation, move, ability, type, color, mega, monotype, gigantamax, fully evolved, height, weight, stats, bst, weak/resists <type, move>, legendary, baby, unevolved"""

        statements = ()
        args = []
        show_all = False
        async with ctx.typing():
            for fullterm in query:
                if fullterm.lower() == 'all':
                    if ctx.guild:
                        return await ctx.send('Cannot broadcast with "all", try DMs instead')
                    show_all = True
                    continue
                try:
                    new_statement, new_args = await self.ds_parse(fullterm)
                except DexsearchParseError as e:
                    return await ctx.send(e)
                statements += f'({new_statement})',
                args += new_args
        statement = 'SELECT DISTINCT name FROM ' + ' INTERSECT SELECT * FROM '.join(statements) + ' ORDER BY name'
        self.bot.log_info(statement)
        self.bot.log_info(', '.join(map(str, args)))
        async with self.bot.pokeapi.replace_row_factory(lambda c, r: str(*r)) as conn:
            results = await conn.execute_fetchall(statement, args)
        if not results:
            await ctx.send('No results found.')
        elif len(results) > 20 and not show_all:
            await ctx.send(f'{", ".join(results[:20])}, and {len(results) - 20} more')
        else:
            pag = commands.Paginator('', '', max_size=1500)
            [pag.add_line(name) for name in results]
            for i, page in enumerate(pag.pages):
                await ctx.send(page.strip().replace('\n', ', ') + (', ...' if i < len(pag.pages) - 1 else ''))

    @dexsearch.error
    async def dexsearch_error(self, ctx: commands.Context, exc: commands.CommandError):
        if isinstance(exc, commands.CommandInvokeError):
            exc = exc.original
        await ctx.send(f'{exc.__class__.__name__}: {exc}', delete_after=10)

    async def ms_parse_one(self, fullterm: str) -> typing.Tuple:
        notsearch, term = re.match(r'^(!?)(.+?)$', fullterm).groups()
        if m := re.match(r'^(g(en)?)? ?([1-8])$', term, re.I):
            gen = int(m[3])
            return """
            SELECT pv2mn.name
            FROM pokemon_v2_movename pv2mn
            INNER JOIN pokemon_v2_move pv2m on pv2mn.move_id = pv2m.id
            WHERE pv2m.generation_id = ?
            AND pv2mn.language_id = 9
            """, gen
        elif type_ := await self.bot.pokeapi.get_model_named('Type', type_pat.sub('', term)):
            return """
            SELECT pv2mn.name
            FROM pokemon_v2_movename pv2mn
            INNER JOIN pokemon_v2_move pv2m on pv2mn.move_id = pv2m.id
            WHERE pv2mn.language_id = 9
            AND pv2m.type_id = ?
            """, type_.id
        elif mdclass := await self.bot.pokeapi.get_model_named('MoveDamageClass', term):  # type: PokeapiModels.MoveDamageClass
            return """
            SELECT pv2mn.name
            FROM pokemon_v2_movename pv2mn
            INNER JOIN pokemon_v2_move pv2m on pv2mn.move_id = pv2m.id
            WHERE pv2mn.language_id = 9
            AND pv2m.move_damage_class_id = ?
            """, mdclass.id
        elif ctype := await self.bot.pokeapi.get_model_named('ContestType', term):  # type: PokeapiModels.ContestType
            return """
            SELECT pv2mn.name
            FROM pokemon_v2_movename pv2mn
            INNER JOIN pokemon_v2_move pv2m on pv2mn.move_id = pv2m.id
            WHERE pv2mn.language_id = 9
            AND pv2m.contest_type_id = ?
            """, ctype.id
        elif (m := re.match(r'^targets\s+(?P<target>.+)$', term, re.I)) and (target := await self.bot.pokeapi.get_model_named('MoveTarget', m['target'])):  # type: PokeapiModels.MoveTarget
            return """
            SELECT pv2mn.name
            FROM pokemon_v2_movename pv2mn
            INNER JOIN pokemon_v2_move pv2m on pv2mn.move_id = pv2m.id
            WHERE pv2mn.language_id = 9
            AND pv2m.move_target_id = ?
            """, target.id
        elif attr := await self.bot.pokeapi.get_model_named('MoveAttribute', re.sub(r'^bypasses\s*substitute$', 'authentic', term, re.I)):  # type: PokeapiModels.MoveAttribute
            return """
            SELECT pv2mn.name
            FROM pokemon_v2_movename pv2mn
            INNER JOIN pokemon_v2_moveattributemap p on pv2mn.move_id = p.move_id
            WHERE pv2mn.language_id = 9
            AND p.move_attribute_id = ?
            """, attr.id
        else:
            raise DexsearchParseError(f'I did not understand your query (first unrecognized term: {fullterm})')

    async def ms_parse(self, term: str):
        args = []
        terms = re.split(r'\s*\|\s*', term)
        statement = ''

        for i, real_term in enumerate(terms):
            new_statement, *new_args = await self.ms_parse_one(real_term)
            if i == 0:
                joiner = """SELECT name FROM pokemon_v2_movename WHERE language_id = 9 EXCEPT""" if real_term.startswith('!') else ''
            else:
                joiner = 'EXCEPT' if real_term.startswith('!') else 'UNION'
            args += new_args
            statement += f' {joiner} {new_statement}'
        return statement, args

    @commands.command(aliases=['ms'], usage='<term[, term[, ...]]>')
    async def movesearch(self, ctx, *, query: CommaSeparatedArgs):
        """Search the list of moves"""

        statements = ()
        args = []
        show_all = False
        async with ctx.typing():
            for fullterm in query:
                if fullterm.lower() == 'all':
                    if ctx.guild:
                        return await ctx.send('Cannot broadcast with "all", try DMs instead')
                    show_all = True
                    continue
                try:
                    new_statement, new_args = await self.ms_parse(fullterm)
                except DexsearchParseError as e:
                    return await ctx.send(e)
                statements += f'({new_statement})',
                args += new_args
        statement = 'SELECT DISTINCT name FROM ' + ' INTERSECT SELECT * FROM '.join(statements) + ' ORDER BY name'
        self.bot.log_info(statement)
        self.bot.log_info(', '.join(map(str, args)))
        async with self.bot.pokeapi.replace_row_factory(lambda c, r: str(*r)) as conn:
            results = await conn.execute_fetchall(statement, args)
        if not results:
            await ctx.send('No results found.')
        elif len(results) > 20 and not show_all:
            await ctx.send(f'{", ".join(results[:20])}, and {len(results) - 20} more')
        else:
            pag = commands.Paginator('', '', max_size=1500)
            [pag.add_line(name) for name in results]
            for i, page in enumerate(pag.pages):
                await ctx.send(page.strip().replace('\n', ', ') + (', ...' if i < len(pag.pages) - 1 else ''))

    @movesearch.error
    async def movesearch_error(self, ctx: commands.Context, exc: commands.CommandError):
        if isinstance(exc, commands.CommandInvokeError):
            exc = exc.original
        await ctx.send(f'{exc.__class__.__name__}: {exc}', delete_after=10)
