import aiosqlite
import re
import math
import typing
import sqlite3
import pathlib
import random
import json
import contextlib

from .models import PokeapiModel, collection


__all__ = ('PokeApi', 'connect')


RowFactory = typing.Callable[[sqlite3.Cursor, tuple], typing.Any]


class PokeApi(aiosqlite.Connection):
    @staticmethod
    def _clean_name(name: str):
        name = name.replace('♀', '_F').replace('♂', '_M').replace('é', 'e')
        name = re.sub(r'\W+', '_', name).title()
        return name

    async def _connect(self) -> "PokeApi":
        await super()._connect()
        await PokeapiModel.prepare(self)
        return self

    @staticmethod
    def get_name(entity: PokeapiModel, *, clean=False):
        name = entity.qualified_name
        if clean:
            name = PokeApi._clean_name(name)
        return name

    async def get_species(self, id_: int) -> 'PokeapiModel.classes.PokemonSpecies':
        return await PokeapiModel.classes.PokemonSpecies.get(self, id_)

    async def random_species(self) -> 'PokeapiModel.classes.PokemonSpecies':
        return await PokeapiModel.classes.PokemonSpecies.get_random(self)

    random_pokemon = random_species

    async def random_pokemon_name(self, *, clean=False):
        return PokeApi.get_name(await self.random_species(), clean=clean)

    async def random_move(self) -> 'PokeapiModel.classes.Move':
        return await PokeapiModel.classes.Move.get_random(self)

    async def random_move_name(self, *, clean=False):
        return PokeApi.get_name(await self.random_move(), clean=clean)

    @staticmethod
    def sprite_url(dbpath: str):
        return re.sub(r'^/media', 'https://raw.githubusercontent.com/PokeAPI/sprites/master/', dbpath)

    @staticmethod
    def get_sprite_path(sprites: dict[str, typing.Union[str, dict]], *path: str) -> typing.Optional[str]:
        try:
            for term in path:
                sprites = sprites[term]
        except (KeyError, TypeError):
            return None
        return sprites

    @staticmethod
    async def get_species_sprite_url(mon: 'PokeapiModel.classes.PokeomnSpecies'):
        default_poke = await PokeApi.get_default_pokemon(mon)
        sprites = json.loads((await default_poke.pokemon_spriteses)[0].sprites)
        options = (
            ('front_default',),
            ('versions', 'generation-vii', 'ultra-sun-ultra-moon', 'front_default'),
            ('versions', 'generation-viii', 'icons', 'front_default')
        )
        for option in options:
            if path := PokeApi.get_sprite_path(sprites, *option):
                return PokeApi.sprite_url(path)

    @staticmethod
    async def get_default_pokemon(mon: 'PokeapiModel.classes.PokemonSpecies'):
        return (await mon.pokemons).get(is_default=True)

    @staticmethod
    async def get_mon_types( mon: 'PokeapiModel.classes.PokemonSpecies') -> list['PokeapiModel.classes.Type']:
        default_mon = await PokeApi.get_default_pokemon(mon)
        return [await ptype.type for ptype in await default_mon.pokemon_types]

    @staticmethod
    async def get_mon_matchup_against_type(
            mon: 'PokeapiModel.classes.PokemonSpecies',
            type_: 'PokeapiModel.classes.Type'
    ) -> float:
        start = 1.0
        default_mon = await PokeApi.get_default_pokemon(mon)
        for ptyp in await default_mon.pokemon_types:
            typ = await ptyp.type
            for efficacy in await typ.type_efficacys__target_type:
                if await efficacy.damage_type == type_:
                    start *= efficacy.damage_factor / 100.0
        return start

    @staticmethod
    async def get_mon_matchup_against_move(
            mon: 'PokeapiModel.classes.PokemonSpecies',
            move: 'PokeapiModel.classes.Type'
    ) -> float:
        if move.id == 560:
            types = [await move.type, await PokeapiModel.classes.Type.get(3)]
        else:
            types = [await move.type]
        return math.prod(await PokeApi.get_mon_matchup_against_type(mon, type_) for type_ in types)

    @staticmethod
    async def get_mon_matchup_against_mon(
            mon: 'PokeapiModel.classes.PokemonSpecies',
            mon2: 'PokeapiModel.classes.PokemonSpecies',
    ) -> list[float]:
        return [await PokeApi.get_mon_matchup_against_type(mon, type_) for type_ in await PokeApi.get_mon_types(mon2)]

    @staticmethod
    async def get_preevo(
            mon: 'PokeapiModel.classes.PokemonSpecies'
    ) -> typing.Optional['PokeapiModel.classes.PokemonSpecies']:
        return await mon.evolves_from_species

    @staticmethod
    async def get_evos(
            mon: 'PokeapiModel.classes.PokemonSpecies'
    ) -> collection['PokeapiModel.classes.PokemonSpecies']:
        return await mon.evolves_into_species

    @staticmethod
    async def get_mon_learnset(mon: 'PokeapiModel.classes.PokemonSpecies') -> set['PokeapiModel.classes.Move']:
        default_pokemon = await PokeApi.get_default_pokemon(mon)
        return set(await pm.move for pm in await default_pokemon.pokemon_moves)

    @staticmethod
    async def get_mon_learnset_with_flags(
            mon: 'PokeapiModel.classes.PokemonSpecies'
    ) -> list['PokeapiModel.classes.PokemonMove']:
        default_mon = await PokeApi.get_default_pokemon(mon)
        return await default_mon.pokemon_moves

    @staticmethod
    async def mon_can_learn_move(mon: 'PokeapiModel.classes.PokemonSpecies', move: 'PokeapiModel.classes.Move'):
        default_mon = await PokeApi.get_default_pokemon(mon)
        for pm in await default_mon.pokemon_moves:
            if await pm.move == move:
                return True
        return False

    @staticmethod
    async def get_mon_abilities_with_flags(
            mon: 'PokeapiModel.classes.PokemonSpecies'
    ) -> collection['PokeapiModel.classes.PokemonAbility']:
        default_mon = await PokeApi.get_default_pokemon(mon)
        return await default_mon.pokemon_abilitys

    @staticmethod
    async def get_mon_abilities(
            mon: 'PokeapiModel.classes.PokemonSpecies'
    ) -> list['PokeapiModel.classes.Ability']:
        pokemon_abilities = await PokeApi.get_mon_abilities_with_flags(mon)
        return [await pab.ability for pab in pokemon_abilities]

    @staticmethod
    async def mon_has_ability(
            mon: 'PokeapiModel.classes.PokemonSpecies',
            ability: 'PokeapiModel.classes.Ability'
    ) -> bool:
        for pab in await PokeApi.get_mon_abilities_with_flags(mon):
            if await pab.ability == ability:
                return True
        return False

    @staticmethod
    async def mon_has_type(
            mon: 'PokeapiModel.classes.PokemonSpecies',
            type_: 'PokeapiModel.classes.Type'
    ) -> bool:
        default_mon = await PokeApi.get_default_pokemon(mon)
        for pty in await default_mon.pokemon_types:
            if await pty.type == type_:
                return True
        return False

    @staticmethod
    async def has_mega_evolution(mon: 'PokeapiModel.classes.PokemonSpecies') -> bool:
        for poke in await mon.pokemons:
            for forme in await poke.pokemon_forms:
                if forme.is_mega:
                    return True
        return False

    @staticmethod
    async def get_evo_line(
            mon: 'PokeapiModel.classes.PokemonSpecies'
    ) -> collection['PokeapiModel.classes.PokemonSpecies']:
        return await (await mon.evolution_chain).pokemon_species

    @staticmethod
    async def has_evos(mon: 'PokeapiModel.classes.PokemonSpecies') -> bool:
        return len(await PokeApi.get_evo_line(mon)) > 1

    @staticmethod
    async def is_in_evo_line(
            needle: 'PokeapiModel.classes.PokemonSpecies',
            haystack: 'PokeapiModel.classes.PokemonSpecies'
    ) -> bool:
        return needle in await PokeApi.get_evo_line(haystack)

    @staticmethod
    async def has_branching_evos(mon: 'PokeapiModel.classes.PokemonSpecies') -> bool:
        return any([len(await poke.evolves_into_species) > 1 for poke in await PokeApi.get_evo_line(mon)])

    @staticmethod
    async def mon_is_in_dex(
            mon: 'PokeapiModel.classes.PokemonSpecies',
            dex: 'PokeapiModel.classes.Pokedex'
    ) -> bool:
        for dnum in await mon.pokemon_dex_numbers:
            if await dnum.pokedex == dex:
                return True
        return False

    @staticmethod
    async def get_formes(mon: 'PokeapiModel.classes.PokemonSpecies') -> list['PokeapiModel.classes.PokemonForm']:
        return [form for poke in await mon.pokemons for form in await poke.pokemon_forms]

    @staticmethod
    async def get_default_forme(mon: 'PokeapiModel.classes.PokemonSpecies') -> 'PokeapiModel.classes.PokemonForm':
        for poke in await mon.pokemons:
            for form in await poke.pokemon_forms:
                if form.is_default:
                    return form

    @staticmethod
    async def get_base_stats(mon: 'PokeapiModel.classes.PokemonSpecies') -> dict[str, int]:
        default_mon = await PokeApi.get_default_pokemon(mon)
        return {(await bs.stat).qualified_name: bs.base_stat for bs in await default_mon.pokemon_stats}

    @staticmethod
    async def get_egg_groups(mon: 'PokeapiModel.classes.PokemonSpecies') -> list['PokeapiModel.classes.EggGroup']:
        return [await peg.egg_group for peg in await mon.pokemon_egg_groups]

    @staticmethod
    async def mon_is_in_egg_group(
            mon: 'PokeapiModel.classes.PokemonSpecies',
            egg_group: 'PokeapiModel.classes.EggGroup'
    ) -> bool:
        return egg_group in await PokeApi.get_egg_groups(mon)

    @staticmethod
    async def mon_can_mate_with(
            mon: 'PokeapiModel.classes.PokemonSpecies',
            mate: 'PokeapiModel.classes.PokemonSpecies'
    ) -> bool:
        # Babies can't breed
        if mon.is_baby or mate.is_baby:
            return False

        # Undiscovered can't breed together, and Ditto can't breed Ditto
        # Other than that, same species can breed together.
        if mon.id == mate.id:
            return mon.id != 132 \
                   and mon.gender_rate not in {0, 8, -1} \
                   and not await PokeApi.mon_is_in_undiscovered_egg_group(mon)

        # Anything that's not undiscovered can breed with Ditto
        if mon.id == 132 or mate.id == 132:
            if mon.id == 132:
                mon = mate
            return not await PokeApi.mon_is_in_undiscovered_egg_group(mon)

        # All-male and all-female species can't breed with each other,
        # and genderless species can't breed except with Ditto.
        if mon.gender_rate == mate.gender_rate == 0 \
                or mon.gender_rate == mate.gender_rate == 8 \
                or -1 in {mon.gender_rate, mate.gender_rate}:
            return False

        # If the two species share egg groups, we good.
        mon_egg_groups = await PokeApi.get_egg_groups(mon)
        mate_egg_groups = await PokeApi.get_egg_groups(mate)
        return any(grp in mon_egg_groups for grp in mate_egg_groups)

    @staticmethod
    async def get_mon_flavor_text(
            mon: 'PokeapiModel.classes.PokemonSpecies',
            version: 'PokeapiModel.classes.Version' = None
    ) -> str:
        flavor_texts = await mon.pokemon_species_flavor_texts
        if version:
            for txt in flavor_texts:
                if await txt.version == version and txt.language_id == 9:
                    return txt.flavor_text
        return random.choice([
            txt.flavor_text
            for txt in flavor_texts
            if txt.language_id == 9
        ])

    @staticmethod
    async def get_mon_evolution_methods(
            mon: 'PokeapiModel.classes.PokemonSpecies'
    ) -> list['PokeapiModel.classes.PokemonEvolution']:
        return [await poke.pokemon_evolution for poke in await mon.evolves_into_species]

    @staticmethod
    async def mon_is_in_undiscovered_egg_group(mon: 'PokeapiModel.classes.PokemonSpecies') -> bool:
        return (await mon.pokemon_egg_groups).get(egg_group_id=15) is not None

    @staticmethod
    async def get_versions_in_group(
            grp: 'PokeapiModel.classes.VersionGroup'
    ) -> collection['PokeapiModel.classes.Version']:
        return await grp.versions

    @staticmethod
    async def get_move_attrs(move: 'PokeapiModel.classes.Move') -> list['PokeapiModel.classes.MoveAttribute']:
        return [await mam.move_attribute for mam in await move.move_attribute_maps]

    @staticmethod
    async def get_move_description(
            move: 'PokeapiModel.classes.Move',
            version: 'PokeapiModel.classes.Version' = None
    ) -> str:
        flavor_texts = await move.move_flavor_texts
        if version:
            for txt in flavor_texts:
                if await txt.version == version and txt.language_id == 9:
                    return txt.flavor_text
        return random.choice([
            txt.flavor_text
            for txt in flavor_texts
            if txt.language_id == 9
        ])

    @staticmethod
    async def get_machines_teaching_move(
            move: 'PokeapiModel.classes.Move'
    ) -> collection['PokeapiModel.classes.Machine']:
        return await move.machines

    @staticmethod
    async def get_version_group_name(version_group: 'PokeapiModel.classes.VersionGroup') -> str:
        *versions, last = await version_group.versions
        if versions:
            if len(versions) == 1:
                return f'{versions[0].qualified_name} and {last.qualified_name}'
            return ', '.join(v.qualified_name for v in versions) + ', and ' + last.qualified_name
        return last.qualified_name


def connect(
    database: typing.Union[str, pathlib.Path],
    *,
    iter_chunk_size=64,
    **kwargs
) -> PokeApi:
    """Create and return a connection proxy to the sqlite database."""

    def connector() -> sqlite3.Connection:
        if isinstance(database, str):
            loc = database
        elif isinstance(database, bytes):
            loc = database.decode("utf-8")
        else:
            loc = str(database)

        return sqlite3.connect(loc, **kwargs)

    return PokeApi(connector, iter_chunk_size)
