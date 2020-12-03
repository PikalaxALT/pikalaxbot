import collections
import typing


__all__ = 'PokeApiModel', 'PokemonSpecies', 'Move', 'Type', 'Ability', 'PokemonColor', 'Pokedex'
PokeApiModel = typing.Union[__all__[1:]]


class PokemonSpecies(typing.NamedTuple):
    id: int
    name: str
    order: int
    gender_rate: int
    capture_rate: int
    base_happiness: int
    is_baby: bool
    hatch_counter: int
    has_gender_differences: bool
    forms_switchable: bool
    evolution_chain_id: int
    generation_id: int
    growth_rate_id: int
    pokemon_color_id: int
    pokemon_habitat_id: int
    pokemon_shape_id: int
    is_legendary: bool
    is_mythical: bool
    evolves_from_species_id: int


class Move(typing.NamedTuple):
    id: int
    power: int
    pp: int
    accuracy: int
    priority: int
    move_effect_chance: int
    generation_id: int
    move_damage_class_id: int
    move_effect_id: int
    move_target_id: int
    type_id: int
    contest_effect_id: int
    contest_type_id: int
    super_contest_effect_id: int
    name: str


class Ability(typing.NamedTuple):
    id: int
    is_main_series: bool
    generation_id: int
    name: str


class Type(typing.NamedTuple):
    id: int
    generation_id: int
    move_damage_class_id: int
    name: str


class PokemonColor(typing.NamedTuple):
    id: int
    name: str


class Pokedex(typing.NamedTuple):
    id: int
    is_main_series: bool
    region_id: int
    name: str
