import collections
import aiosqlite
import typing


__all__ = 'PokemonSpecies', 'Move', 'Type', 'Ability', 'PokemonColor'


PokemonSpecies = collections.namedtuple(
    'PokemonSpecies',
    'id '
    'name '
    'order '
    'gender_rate '
    'capture_rate '
    'base_happiness '
    'is_baby '
    'hatch_counter '
    'has_gender_differences '
    'forms_switchable '
    'evolution_chain_id '
    'generation_id '
    'growth_rate_id '
    'pokemon_color_id '
    'pokemon_habitat_id '
    'pokemon_shape_id '
    'is_legendary '
    'is_mythical '
    'evolves_from_species_id'
)

Move = collections.namedtuple(
    'Move',
    'id '
    'power '
    'pp '
    'accuracy '
    'priority '
    'move_effect_chance '
    'generation_id '
    'move_damage_class_id '
    'move_effect_id '
    'move_target_id '
    'type_id '
    'contest_effect_id '
    'contest_type_id '
    'super_contest_effect_id '
    'name'
)

Ability = collections.namedtuple(
    'Ability',
    'id '
    'is_main_series '
    'generation_id name'
)

Type = collections.namedtuple(
    'Type',
    'id '
    'generation_id '
    'move_damage_class_id '
    'name'
)

PokemonColor = collections.namedtuple(
    'PokemonColor',
    'id '
    'name'
)
