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
    @contextlib.asynccontextmanager
    async def replace_row_factory(self, row_factory: typing.Optional[RowFactory]):
        old_factory: typing.Optional[RowFactory] = self.row_factory
        try:
            self.row_factory = row_factory
            yield
        finally:
            self.row_factory = old_factory

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
    def get_species_sprite_url(mon: 'PokeapiModel.classes.PokeomnSpecies'):
        sprites = json.loads(mon.pokemon_sprites[0].sprites)
        options = (
            ('front_default',),
            ('versions', 'generation-vii', 'ultra-sun-ultra-moon', 'front_default'),
            ('versions', 'generation-viii', 'icons', 'front_default')
        )
        for option in options:
            if path := PokeApi.get_sprite_path(sprites, *option):
                return PokeApi.sprite_url(path)

    @staticmethod
    def get_default_pokemon(mon: 'PokeapiModel.classes.PokemonSpecies'):
        return mon.pokemons.get(is_default=True)

    @staticmethod
    def get_mon_types(mon: 'PokeapiModel.classes.PokemonSpecies') -> list['PokeapiModel.classes.Type']:
        return [ptype.type for ptype in PokeApi.get_default_pokemon(mon).pokemon_types]

    @staticmethod
    def get_mon_matchup_against_type(
            mon: 'PokeapiModel.classes.PokemonSpecies',
            type_: 'PokeapiModel.classes.Type'
    ) -> float:
        return math.prod(
            effic.damage_factor / 100.0
            for ptyp in PokeApi.get_default_pokemon(mon).pokemon_types
            for effic in ptyp.type.type_efficacys__target_type
            if effic.damage_type == type_
        )

    @staticmethod
    def get_mon_matchup_against_move(
            mon: 'PokeapiModel.classes.PokemonSpecies',
            move: 'PokeapiModel.classes.Type'
    ) -> float:
        result = PokeApi.get_mon_matchup_against_type(mon, move.type)
        if move.id == 560:
            result *= math.prod(
                effic.damage_factor / 100.0
                for ptyp in PokeApi.get_default_pokemon(mon).pokemon_types
                for effic in ptyp.type.type_efficacys__target_type
                if effic.damage_type.id == 3
            )
        return result

    @staticmethod
    def get_mon_matchup_against_mon(
            mon: 'PokeapiModel.classes.PokemonSpecies',
            mon2: 'PokeapiModel.classes.PokemonSpecies',
    ) -> list[float]:
        return [PokeApi.get_mon_matchup_against_type(mon, type_) for type_ in PokeApi.get_mon_types(mon2)]

    @staticmethod
    def get_preevo(
            mon: 'PokeapiModel.classes.PokemonSpecies'
    ) -> typing.Optional['PokeapiModel.classes.PokemonSpecies']:
        return mon.evolves_from_species

    @staticmethod
    def get_evos(mon: 'PokeapiModel.classes.PokemonSpecies'):
        return mon.evolves_into_species

    @staticmethod
    def get_mon_learnset(mon: 'PokeapiModel.classes.PokemonSpecies') -> set['PokeapiModel.classes.Move']:
        return set(pm.move for pm in PokeApi.get_default_pokemon(mon).pokemon_moves)

    @staticmethod
    def mon_can_learn_move(mon: 'PokeapiModel.classes.PokemonSpecies', move: 'PokeapiModel.classes.Move'):
        return PokeApi.get_default_pokemon(mon).pokemon_moves.get(move=move) is not None

    @staticmethod
    def get_mon_abilities_with_flags(
            mon: 'PokeapiModel.classes.PokemonSpecies'
    ) -> collection['PokeapiModel.classes.PokemonAbility']:
        return PokeApi.get_default_pokemon(mon).pokemon_abilities

    @staticmethod
    def get_mon_abilities(
            mon: 'PokeapiModel.classes.PokemonSpecies'
    ) -> list['PokeapiModel.classes.Ability']:
        return [pab.ability for pab in PokeApi.get_mon_abilities_with_flags(mon)]

    @staticmethod
    def mon_has_ability(
            mon: 'PokeapiModel.classes.PokemonSpecies',
            ability: 'PokeapiModel.classes.Ability'
    ) -> bool:
        return PokeApi.get_mon_abilities_with_flags(mon).get(ability=ability) is not None

    @staticmethod
    def mon_has_type(
            mon: 'PokeapiModel.classes.PokemonSpecies',
            type_: 'PokeapiModel.classes.Type'
    ) -> bool:
        return PokeApi.get_default_pokemon(mon).pokemon_types.get(type=type_) is not None

    @staticmethod
    def has_mega_evolution(mon: 'PokeapiModel.classes.PokemonSpecies') -> bool:
        return mon.pokemons.get(pokemon_forms__is_mega=True) is not None

    @staticmethod
    def get_evo_line(
            mon: 'PokeapiModel.classes.PokemonSpecies'
    ) -> collection['PokeapiModel.classes.PokemonSpecies']:
        return mon.evolution_chain.pokemon_species

    @staticmethod
    def has_evos(mon: 'PokeapiModel.classes.PokemonSpecies') -> bool:
        return len(PokeApi.get_evo_line(mon)) > 1

    @staticmethod
    def is_in_evo_line(
            needle: 'PokeapiModel.classes.PokemonSpecies',
            haystack: 'PokeapiModel.classes.PokemonSpecies'
    ) -> bool:
        return needle in PokeApi.get_evo_line(haystack)

    @staticmethod
    def has_branching_evos(mon: 'PokeapiModel.classes.PokemonSpecies') -> bool:
        return any(len(poke.evolves_into_species) > 1 for poke in PokeApi.get_evo_line(mon))

    @staticmethod
    def mon_is_in_dex(
            mon: 'PokeapiModel.classes.PokemonSpecies',
            dex: 'PokeapiModel.classes.Pokedex'
    ) -> bool:
        return mon.pokemon_dex_numbers.get(pokedex=dex) is not None

    @staticmethod
    def get_formes(mon: 'PokeapiModel.classes.PokemonSpecies') -> list['PokeapiModel.classes.PokemonForm']:
        return [poke.pokemon_form for poke in mon.pokemons]

    @staticmethod
    def get_default_forme(mon: 'PokeapiModel.classes.PokemonSpecies') -> 'PokeapiModel.classes.PokemonForm':
        return PokeApi.get_default_pokemon(mon).pokemon_form

    @staticmethod
    def get_base_stats(mon: 'PokeapiModel.classes.PokemonSpecies') -> dict[str, int]:
        default_mon = PokeApi.get_default_pokemon(mon)
        return {bs.stat.qualified_name: bs.base_stat for bs in default_mon.pokemon_stats}

    @staticmethod
    def get_egg_groups(mon: 'PokeapiModel.classes.PokemonSpecies') -> list['PokeapiModel.classes.EggGroup']:
        return [peg.egg_group for peg in mon.pokemon_egg_groups]

    @staticmethod
    def mon_is_in_egg_group(
            mon: 'PokeapiModel.classes.PokemonSpecies',
            egg_group: 'PokeapiModel.classes.EggGroup'
    ) -> bool:
        return mon.pokemon_egg_groups.get(egg_group=egg_group) is not None

    @staticmethod
    def mon_can_mate_with(
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
                   and mon.pokemon_egg_groups.get(egg_group_id=15) is None

        # Anything that's not undiscovered can breed with Ditto
        if mon.id == 132 or mate.id == 132:
            if mon.id == 132:
                mon = mate
            return mon.pokemon_egg_groups.get(egg_group_id=15) is None

        # All-male and all-female species can't breed with each other,
        # and genderless species can't breed except with Ditto.
        if mon.gender_rate == mate.gender_rate == 0 \
                or mon.gender_rate == mate.gender_rate == 8 \
                or -1 in {mon.gender_rate, mate.gender_rate}:
            return False

        # If the two species share egg groups, we good.
        return any(grp in PokeApi.get_egg_groups(mon) for grp in PokeApi.get_egg_groups(mate))

    @staticmethod
    def get_mon_flavor_text(
            mon: 'PokeapiModel.classes.PokemonSpecies',
            version: 'PokeapiModel.classes.Version' = None
    ) -> str:
        if version:
            return random.choice([txt.flavor_text for txt in mon.pokemon_species_flavor_texts if txt.language_id == 9])
        return mon.pokemon_species_flavor_texts.get(language_id=9, version=version)

    @staticmethod
    def get_mon_evolution_methods(
            mon: 'PokeapiModel.classes.PokemonSpecies'
    ) -> list['PokeapiModel.classes.PokemonEvolution']:
        return [poke.pokemon_evolution for poke in PokeApi.get_evos(mon)]

    @staticmethod
    def mon_is_in_undiscovered_egg_group(mon: 'PokeapiModel.classes.PokemonSpecies') -> bool:
        return mon.pokemon_egg_groups.get(egg_group_id=15) is not None

    @staticmethod
    def get_versions_in_group(grp: 'PokeapiModel.classes.VersionGroup') -> collection['PokeapiModel.classes.Version']:
        return grp.versions

    @staticmethod
    def get_move_attrs(move: 'PokeapiModel.classes.Move') -> list['PokeapiModel.classes.MoveAttribute']:
        return [mam.move_attribute for mam in move.move_attribute_maps]

    @staticmethod
    def get_move_description(
            move: 'PokeapiModel.classes.Move',
            version: 'PokeapiModel.classes.Version' = None
    ) -> str:
        if version:
            return random.choice([txt.flavor_text for txt in move.move_flavor_texts if txt.language_id == 9])
        return move.move_flavor_texts.get(language_id=9, version=version)

    @staticmethod
    def get_machines_teaching_move(move: 'PokeapiModel.classes.Move') -> collection['PokeapiModel.classes.Machine']:
        return move.machines

    @staticmethod
    def get_version_group_name(version_group: 'PokeapiModel.classes.VersionGroup') -> str:
        *versions, last = version_group.versions
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
