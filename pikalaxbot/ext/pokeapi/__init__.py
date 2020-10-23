import random
import re
import csv
import os
import discord


class PokeApi:
    path = os.path.dirname(__file__) + '/../../../pokeapi/data/v2/csv'
    language = '9'
    __slots__ = (
        'abilities',
        'ability_names',
        'egg_groups',
        'evolution_chains',
        'generation_names',
        'generations',
        'move_names',
        'moves',
        'pokemon',
        'pokemon_abilities',
        'pokemon_color_names',
        'pokemon_colors',
        'pokemon_dex_numbers',
        'pokemon_egg_groups',
        'pokemon_evolution',
        'pokemon_form_names',
        'pokemon_forms',
        'pokemon_habitat_names',
        'pokemon_habitats',
        'pokemon_moves',
        'pokemon_shapes',
        'pokemon_species',
        'pokemon_species_names',
        'pokemon_stats',
        'pokemon_types',
        'stat_names',
        'stats',
        'type_efficacy',
        'type_names',
        'types'
    )

    def __init__(self):
        for attrname in PokeApi.__slots__:
            file = f'{PokeApi.path}/{attrname}.csv'
            with open(file) as fp:
                reader = csv.DictReader(fp)
                if attrname.endswith('_names'):
                    data = [row for row in reader if row['local_language_id'] == PokeApi.language]
                else:
                    data = list(csv.DictReader(fp))
                setattr(self, attrname, data)

    def __repr__(self):
        return f'<{self.__class__.__name__}>'

    @staticmethod
    def clean_name(name):
        name = name.replace('♀', '_F').replace('♂', '_m')
        name = re.sub(r'\W+', '_', name).replace('é', 'e').title()
        return name

    def random_species(self):
        mon = random.choice(self.pokemon_species)
        return mon

    random_pokemon = random_species
    
    def get_name(self, item, from_, *, clean=True):
        def find_cb(row):
            return row[f'{from_}_id'] == item['id']
        
        name = discord.utils.find(find_cb, getattr(self, f'{from_}_names'))['name']
        if clean:
            name = self.clean_name(name)
        return name

    def get_mon_name(self, mon, *, clean=True):
        return self.get_name(mon, 'pokemon_species', clean=clean)

    def random_species_name(self, *, clean=True):
        mon = self.random_species()
        return self.get_mon_name(mon, clean=clean)

    random_pokemon_name = random_species_name

    def random_move(self):
        return random.choice(self.moves)

    def random_move_name(self, *, clean=True):
        move = self.random_move()
        return self.get_name(move, 'move', clean=clean)

    def get_mon_types(self, mon):
        """Returns a list of type names for that Pokemon"""
        types = set(row['type_id'] for row in self.pokemon_types if row['pokemon_id'] == mon['id'])
        return [row['name'] for row in self.type_names if row['type_id'] in types]


def setup(bot):
    bot.pokeapi = PokeApi()


def teardown(bot):
    bot.pokeapi = None
