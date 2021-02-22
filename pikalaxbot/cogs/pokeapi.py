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
from discord.ext import commands, tasks, menus
import asyncio
import sqlite3
import typing
import time
import re
from ..pokeapi import PokeapiModel
from textwrap import indent
import traceback
import operator
import aioitertools
from . import *
import asyncstdlib.builtins as abuiltins
from contextlib import asynccontextmanager as acm
if typing.TYPE_CHECKING:
    from .q20_game import Q20Game


__all__ = 'PokeApiCog',


CommaSeparatedArgs = re.compile(r',\s*').split
type_pat = re.compile(r'\s*type$', re.I)
egg_group_pat = re.compile(r'\s*egg\s*group$', re.I)


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
            raise RuntimeError('Line exceeds maximum page size %s' % max_page_size)

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


async def dexsearch_check(ctx: MyContext):
    cog: typing.Optional['Q20Game'] = ctx.bot.get_cog('Q20Game')
    if cog and cog[ctx.channel.id].running:
        raise commands.CheckFailure('Dexsearch is banned in this channel while Q20 is running')
    return True


class ConfirmationMenu(menus.Menu):
    async def send_initial_message(self, ctx: MyContext, channel):
        return await ctx.reply('This can take up to 30 minutes. Are you sure?')

    @menus.button('\N{CROSS MARK}')
    async def abort(self, payload: discord.RawReactionActionEvent):
        await self.message.edit(content='Aborting', delete_after=10)
        self.stop()

    @menus.button('\N{WHITE HEAVY CHECK MARK}')
    async def confirm(self, payload: discord.RawReactionActionEvent):
        await self.message.edit(content='Confirmed', delete_after=10)
        await self.ctx.cog.do_rebuild_pokeapi(self.ctx)
        self.stop()

    async def finalize(self, timed_out):
        if timed_out:
            await self.message.edit(content='Request timed out', delete_after=10)


class SqlResponseEmbed(menus.ListPageSource):
    def format_page(self, menu: menus.MenuPages, page: str):
        return discord.Embed(
            title=menu.sql_cmd,
            description=page,
            colour=0xf47fff
        ).set_footer(
            text=f'Page {menu.current_page + 1}/{self.get_max_pages()} | '
                 f'{menu.row_count} records fetched in {menu.duration * 1000:.1f} ms'
        )


class PokeApiCog(BaseCog, name='PokeApi'):
    """Commands relating to the bot's local clone of the PokeAPI database."""

    def __init__(self, bot):
        super().__init__(bot)
        self._lock = asyncio.Lock()

    def cog_unload(self):
        assert not self._lock.locked(), 'PokeApi is locked'

    @acm
    async def disable_pokeapi(self):
        self.bot.pokeapi._enabled = False
        yield
        self.bot.pokeapi._enabled = True

    async def do_rebuild_pokeapi(self, ctx: MyContext):
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

        done, pending = await asyncio.wait(
            {update_msg.start(), asyncio.create_task(shell.wait)},
            return_when=asyncio.FIRST_COMPLETED
        )
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
    async def pokeapi(self, ctx: MyContext):
        """Commands for interfacing with pokeapi"""

    @commands.max_concurrency(1)
    @commands.is_owner()
    @pokeapi.command(name='rebuild', aliases=['update'])
    async def rebuild_pokeapi(self, ctx: MyContext):
        """Rebuild the pokeapi database"""

        async with self._lock, self.disable_pokeapi():
            menu = ConfirmationMenu(timeout=60.0, clear_reactions_after=True)
            await menu.start(ctx, wait=True)

    @pokeapi.command(name='sql')
    @commands.is_owner()
    async def execute_sql(self, ctx: MyContext, *, query: str):
        """Run arbitrary sql command"""

        async with ctx.typing():
            start = time.perf_counter()
            async with self.bot.pokeapi.execute(query) as cur:
                records: list[tuple] = await cur.fetchall()
                end = time.perf_counter()
            header = '|'.join(col[0] for col in cur.description)
            pag = commands.Paginator(max_size=2048)
            pag.add_line(header)
            pag.add_line('-' * len(header))
            for i, row in enumerate(records, 1):
                to_add = '|'.join(map(str, row))
                if len(header) * 2 + len(to_add) > 2040:
                    raise ValueError('At least one page of results is too long to fit. Try returning fewer columns?')
                if pag._count + len(to_add) + 1 > 2045 or len(pag._current_page) >= 21:
                    pag.close_page()
                    pag.add_line(header)
                    pag.add_line('-' * len(header))
                pag.add_line(to_add)

        if pag.pages:
            menu = menus.MenuPages(
                SqlResponseEmbed(pag.pages, per_page=1),
                delete_message_after=True,
                clear_reactions_after=True
            )
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

    async def mon_info(self, ctx: MyContext, pokemon: 'PokeapiModel.classes.PokemonSpecies'):
        """Gets information about a Pokémon species"""

        async with ctx.typing():
            base_stats = await self.bot.pokeapi.get_base_stats(pokemon)
            types = await self.bot.pokeapi.get_mon_types(pokemon)
            egg_groups = await self.bot.pokeapi.get_egg_groups(pokemon)
            image_url = await self.bot.pokeapi.get_species_sprite_url(pokemon)
            flavor_text = await self.bot.pokeapi.get_mon_flavor_text(pokemon)
            evos = await self.bot.pokeapi.get_evos(pokemon)
            abilities = await self.bot.pokeapi.get_mon_abilities_with_flags(pokemon)
            forme = await self.bot.pokeapi.get_default_forme(pokemon)
        embed = discord.Embed(
            title=f'{pokemon} (#{pokemon.id})',
            description=flavor_text or 'No flavor text',
            colour=DEX_COLORS[(await pokemon.pokemon_color).id]
        ).add_field(
            name='Generation',
            value=(await pokemon.generation).qualified_name or 'Unknown'
        ).add_field(
            name='Types',
            value='/'.join(type_.qualified_name for type_ in types) or 'Unknown'
        ).add_field(
            name='Base Stats',
            value='\n'.join(
                f'{stat}: {value}' for stat, value in base_stats.items()
            ) + f'\n**Total:** {sum(base_stats.values())}' or 'Unknown'
        ).add_field(
            name='Egg Groups',
            value='/'.join(grp.qualified_name for grp in egg_groups) or 'Unknown'
        ).add_field(
            name='Gender Ratio',
            value=f'{12.5 * pokemon.gender_rate}% Female' if pokemon.gender_rate >= 0 else 'Gender Unknown' or 'Unknown'
        ).set_thumbnail(url=image_url or discord.Embed.Empty)
        evolves_from_species = await pokemon.evolves_from_species
        if evolves_from_species:
            preevo_str = f'Evolves from {evolves_from_species} (#{evolves_from_species.id})\n'
        else:
            preevo_str = ''
        if evos:
            preevo_str += 'Evolves into ' + ', '.join(f'{mon} (#{mon.id})' for mon in evos)
        default_mon = await forme.pokemon
        embed.add_field(
            name='Evolution',
            value=preevo_str or 'No evolutions'
        ).add_field(
            name='Abilities',
            value=', '.join([
                '_{}_'.format(await ability.ability)
                if ability.is_hidden
                else (await ability.ability).qualified_name
                for ability in abilities
            ]) or 'Unknown'
        ).add_field(
            name='Biometrics',
            value=f'Height: {default_mon.height / 10:.1f}m\n'
                  f'Weight: {default_mon.weight / 10:.1f}kg'
        )
        await ctx.send(embed=embed)

    async def move_info(self, ctx: MyContext, move: 'PokeapiModel.classes.Move'):
        async with ctx.typing():
            attrs = await self.bot.pokeapi.get_move_attrs(move)
            flavor_text = await self.bot.pokeapi.get_move_description(move)
            machines = await self.bot.pokeapi.get_machines_teaching_move(move)
            move_effect = await move.move_effect
            short_effect = (await move_effect.move_effect_effect_texts).get(language_id=9).short_effect
            contest_effect = await move.contest_effect
            contest_effect_text = (await contest_effect.contest_effect_effect_texts).get(language_id=9).effect
            super_contest_effect = await move.super_contest_effect
            super_contest_effect_text = (
                await super_contest_effect.super_contest_effect_flavor_texts
            ).get(language_id=9).flavor_text

        embed = discord.Embed(
            title=f'{move} (#{move.id})',
            description=flavor_text or 'No flavor text',
            colour=TYPE_COLORS[(await move.type).qualified_name]
        ).add_field(
            name='Type',
            value=f'Battle: {await move.type}\n'
                  f'Contest: {await move.contest_type}'
        ).add_field(
            name='Stats',
            value=f'**Power:** {move.power}\n'
                  f'**Accuracy:** {move.accuracy}\n'
                  f'**Max PP:** {move.pp}\n'
                  f'**Priority:** {move.priority}'
        ).add_field(
            name='Generation',
            value=(await move.generation).qualified_name
        ).add_field(
            name='Attributes',
            value=indent('\n'.join(attr.name for attr in attrs), '\N{WHITE HEAVY CHECK MARK} ') or '\N{CROSS MARK} None'
        ).add_field(
            name='Effect',
            value=f'**Battle:** {short_effect}\n'
                  f'**Contest:** {contest_effect_text}\n'
                  f'**Super Contest:** {super_contest_effect_text}'
        ).add_field(
            name='Target',
            value=(await move.move_target).qualified_name
        )
        if machines:

            machines.sort(key=operator.attrgetter('version_group_id', 'machine_number'))
            machine_s = []

            async def group_key(mach):
                return await (await mach.version_group).generation

            async for gen, machs in aioitertools.groupby(machines, group_key): \
                    # type: PokeapiModel.classes.Generation, typing.Iterable[PokeapiModel.classes.Machine]
                mach_s = set()
                for mach in machs:
                    if mach.machine_number < 100:
                        mach_no_s = f'TM{mach.machine_number:02d}'
                    else:
                        mach_no_s = f'HM{mach.machine_number - 100:02d}'
                    mach_s.add(mach_no_s)
                machine_s.append(f'**{gen}:** {", ".join(mach_s)}')
            embed.add_field(
                name='Machines',
                value='\n'.join(machine_s)
            )
        await ctx.send(embed=embed)

    @pokeapi.command(name='info')
    async def mon_or_move_info(
            self,
            ctx: MyContext,
            *,
            entity: 'typing.Union[PokeapiModel.classes.PokemonSpecies, PokeapiModel.classes.Move]'
    ):
        """Gets information about a Pokémon species or move"""

        if isinstance(entity, PokeapiModel.classes.PokemonSpecies):
            return await self.mon_info(ctx, entity)
        else:
            return await self.move_info(ctx, entity)

    @commands.command(aliases=['dt'])
    async def details(
            self,
            ctx: MyContext,
            *,
            entity: 'typing.Union[PokeapiModel.classes.PokemonSpecies, PokeapiModel.classes.Move]'
    ):
        """Gets information about a Pokémon species or move"""

        await self.mon_or_move_info(ctx, entity=entity)

    @mon_or_move_info.error
    @details.error
    async def details_error(self, ctx: MyContext, exc: commands.CommandError):
        if isinstance(exc, commands.BadUnionArgument):
            await ctx.send(f'No Pokemon or move named "{exc.errors[0].args[1]}"')
        else:
            if isinstance(exc, commands.CommandInvokeError):
                exc = exc.original
            await self.bot.get_cog('ErrorHandling').send_tb(ctx, exc, origin=str(ctx.command))

    @commands.command(usage='<mon>, <move>')
    async def learn(self, ctx, *, query: CommaSeparatedArgs):
        """Get whether the given pokemon can learn the given move"""
        if len(query) > 2:
            raise commands.BadArgument('mon, move')
        mon = await PokeapiModel.classes.PokemonSpecies.get_named(
            query[0]
        )
        if mon is None:
            return await ctx.send(f'Could not find a Pokémon named "{query[0]}"')

        async def sort_key(pokemon_move):
            return (
                await pokemon_move.move,
                await (await pokemon_move.version_group).generation,
                await pokemon_move.move_learn_method,
                pokemon_move.level
            )

        async def group_key(pokemon_move):
            return await pokemon_move.move

        all_move_learns = await abuiltins.sorted(
            await self.bot.pokeapi.get_mon_learnset_with_flags(mon),
            key=sort_key
        )
        if not all_move_learns:
            return await ctx.send('I do not know anything about this Pokémon\'s move learns yet')
        movelearns = {
            move: list(group)
            async for move, group in aioitertools.groupby(all_move_learns, group_key)}
        if len(query) == 1:
            types = await self.bot.pokeapi.get_mon_types(mon)

            class MoveLearnPageSource(menus.ListPageSource):
                async def format_page(self, menu_: menus.MenuPages, page: list[PokeapiModel.classes.PokemonMove]):
                    embed = discord.Embed(
                        title=f'{mon}\'s learnset',
                        colour=TYPE_COLORS[types[0].qualified_name]
                    ).set_footer(text=f'Page {menu_.current_page + 1}/{self.get_max_pages()}')

                    async def group_key(move_learn):
                        return await (await move_learn.version_group).generation

                    for move, movelearns_ in page:
                        value = '\n'.join([
                            f'**{gen}:** ' + ', '.join(set([
                                f'Level {ml.level}'
                                if (await ml.move_learn_method).id == 1
                                else str(await ml.move_learn_method)
                                for ml in mls]))
                            async for gen, mls
                            in aioitertools.groupby(
                                movelearns_,
                                group_key)
                        ])
                        embed.add_field(
                            name=str(move),
                            value=value
                        )
                    return embed

            menu = menus.MenuPages(
                MoveLearnPageSource(list(movelearns.items()), per_page=6),
                clear_reactions_after=True,
                delete_message_after=True
            )
            await menu.start(ctx)
        else:
            try:
                move = await PokeapiModel.classes.Move.convert(ctx, query[1])
            except commands.BadArgument:
                return await ctx.send(f'Could not find a move named "{query[1]}"')
            flag = 'can' if move in movelearns else 'cannot'
            await ctx.send(f'{mon} **{flag}** learn {move}.')

    async def ds_parse_one(self, fullterm: str) -> tuple:
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
        elif move := await PokeapiModel.classes.Move.get_named(term):
            return """
            SELECT pv2psn.name
            FROM pokemon_v2_pokemonspeciesname pv2psn
            INNER JOIN pokemon_v2_pokemon pv2p ON pv2psn.pokemon_species_id = pv2p.pokemon_species_id
            INNER JOIN pokemon_v2_pokemonmove pv2pm ON pv2p.id = pv2pm.pokemon_id
            WHERE pv2psn.language_id = 9
            AND pv2p.is_default = TRUE
            AND pv2pm.move_id = ?
            """, move.id
        elif type_ := await PokeapiModel.classes.Type.get_named(type_pat.sub('', term)):
            return """
            SELECT pv2psn.name
            FROM pokemon_v2_pokemonspeciesname pv2psn
            INNER JOIN pokemon_v2_pokemon pv2p ON pv2psn.pokemon_species_id = pv2p.pokemon_species_id
            INNER JOIN pokemon_v2_pokemontype pv2pt ON pv2p.id = pv2pt.pokemon_id
            WHERE pv2psn.language_id = 9
            AND pv2p.is_default = TRUE
            AND pv2pt.type_id = ?
            """, type_.id
        elif ability := await PokeapiModel.classes.Ability.get_named(term):
            return """
            SELECT pv2psn.name
            FROM pokemon_v2_pokemonspeciesname pv2psn
            INNER JOIN pokemon_v2_pokemon pv2p ON pv2psn.pokemon_species_id = pv2p.pokemon_species_id
            INNER JOIN pokemon_v2_pokemonability pv2pa ON pv2p.id = pv2pa.pokemon_id
            WHERE pv2psn.language_id = 9
            AND pv2p.is_default = TRUE
            AND pv2pa.ability_id = ?
            """, ability.id
        elif color := await PokeapiModel.classes.PokemonColor.get_named(term):
            return """
            SELECT pv2psn.name
            FROM pokemon_v2_pokemonspeciesname pv2psn
            INNER JOIN pokemon_v2_pokemonspecies pv2ps ON pv2psn.pokemon_species_id = pv2ps.id
            WHERE pv2psn.language_id = 9
            AND pv2ps.pokemon_color_id = ?
            """, color.id,
        elif egg_group := await PokeapiModel.classes.EggGroup.get_named(egg_group_pat.sub('', term)):
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
        elif m := re.match(
                r'^(?P<stat>((?P<special>special|sp[acd]?)\s*)?'
                r'(?P<attack>at(tac)?k)|'
                r'(?P<defense>def(en[cs]e)?)|'
                r'(?P<speed>spe(ed)?)|'
                r'(?P<hp>hp))'
                r'\s*(?P<ineq>[<>!]?=|[<>])\s*'
                r'(?P<value>\d+)$',
                term,
                re.I
        ):
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
        elif m := re.match(
                r'^(?P<measure>height|weight)\s*'
                r'(?P<ineq>[<>!]?=|[<>])\s*'
                r'(?P<amount>(\d+(\.\d+)?|\.\d+))\s*'
                r'(?P<units>(m(eters?)?|k(ilo)?g(rams?)?)?)',
                term,
                re.I
        ):
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
            type_ = await PokeapiModel.classes.Type.get_named(type_pat.sub('', m['type']))
            if type_ is None:
                move = await PokeapiModel.classes.Move.get_named(
                    m['type']
                )  # type: PokeapiModel.classes.Move
                if move is None:
                    raise DexsearchParseError('No type or move named {}'.format(m['type']))
                if move.move_damage_class.id == 1:
                    raise DexsearchParseError('{} is a status move and can\'t be used with {}'.format(
                        move.name,
                        m['direction']
                    ))
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
                joiner = """SELECT name FROM pokemon_v2_pokemonspeciesname WHERE language_id = 9 EXCEPT""" \
                    if real_term.startswith('!') else ''
            else:
                joiner = 'EXCEPT' if real_term.startswith('!') else 'UNION'
            args += new_args
            statement += f' {joiner} {new_statement}'
        return statement, args

    @commands.check(dexsearch_check)
    @commands.command(aliases=['ds'], usage='<term[, term[, ...]]>')
    async def dexsearch(self, ctx, *, query: CommaSeparatedArgs):
        """Search the pokedex. Valid terms: generation, move, ability, type, color, mega, monotype, gigantamax,
        fully evolved, height, weight, stats, bst, weak/resists <type, move>, legendary, baby, unevolved"""

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
        self.bot.log_debug(statement)
        self.bot.log_debug(', '.join(map(str, args)))
        results = [name for name, in await self.bot.pokeapi.execute_fetchall(statement, args)]
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
    async def dexsearch_error(self, ctx: MyContext, exc: commands.CommandError):
        if isinstance(exc, commands.CommandInvokeError):
            exc = exc.original
        await ctx.send(f'{exc.__class__.__name__}: {exc}', delete_after=10)

    async def ms_parse_one(self, fullterm: str) -> tuple:
        target = None
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
        elif type_ := await PokeapiModel.classes.Type.get_named(type_pat.sub('', term)):
            return """
            SELECT pv2mn.name
            FROM pokemon_v2_movename pv2mn
            INNER JOIN pokemon_v2_move pv2m on pv2mn.move_id = pv2m.id
            WHERE pv2mn.language_id = 9
            AND pv2m.type_id = ?
            """, type_.id
        elif mdclass := await PokeapiModel.classes.MoveDamageClass.get_named(term):
            return """
            SELECT pv2mn.name
            FROM pokemon_v2_movename pv2mn
            INNER JOIN pokemon_v2_move pv2m on pv2mn.move_id = pv2m.id
            WHERE pv2mn.language_id = 9
            AND pv2m.move_damage_class_id = ?
            """, mdclass.id
        elif ctype := await PokeapiModel.classes.ContestType.get_named(term):
            return """
            SELECT pv2mn.name
            FROM pokemon_v2_movename pv2mn
            INNER JOIN pokemon_v2_move pv2m on pv2mn.move_id = pv2m.id
            WHERE pv2mn.language_id = 9
            AND pv2m.contest_type_id = ?
            """, ctype.id
        elif (m := re.match(r'^targets\s+(?P<target>.+)$', term, re.I)) \
                and (target := await PokeapiModel.classes.MoveTarget.get_named(m['target'])):
            return """
            SELECT pv2mn.name
            FROM pokemon_v2_movename pv2mn
            INNER JOIN pokemon_v2_move pv2m on pv2mn.move_id = pv2m.id
            WHERE pv2mn.language_id = 9
            AND pv2m.move_target_id = ?
            """, target.id
        elif attr := await PokeapiModel.classes.MoveAttribute.get_named(
                re.sub(r'^bypasses\s*substitute$', 'authentic', term, re.I)
        ):
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
                joiner = """SELECT name FROM pokemon_v2_movename WHERE language_id = 9 EXCEPT""" \
                    if real_term.startswith('!') else ''
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
        self.bot.log_debug(statement)
        self.bot.log_debug(', '.join(map(str, args)))
        results = [name for name, in await self.bot.pokeapi.execute_fetchall(statement, args)]
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
    async def movesearch_error(self, ctx: MyContext, exc: commands.CommandError):
        if isinstance(exc, commands.CommandInvokeError):
            exc = exc.original
        await ctx.send(f'{exc.__class__.__name__}: {exc}', delete_after=10)


def setup(bot):
    bot.add_cog(PokeApiCog(bot))
