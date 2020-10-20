import random
import re
import csv
import os
import discord


class PokeApi:
    path = os.path.dirname(__file__) + '/../../pokeapi/data/v2/csv'
    language = '9'

    @staticmethod
    def clean_name(name):
        name = name.replace('♀', '_F').replace('♂', '_m')
        name = re.sub(r'\W+', '_', name).replace('é', 'e').title()
        return name

    def __getattr__(self, item):
        if item not in self.__dict__:
            try:
                with open(f'{PokeApi.path}/{item}.csv') as fp:
                    self.__dict__[item] = list(csv.DictReader(fp))
            except OSError:
                raise AttributeError(f'Object of type {self.__class__.__name__} has no attribute \'{item}\'')
        return self.__dict__[item]

    def random_pokemon(self):
        return random.choice(self.pokemon)

    def random_pokemon_name(self, *, clean=True):
        def find_cb(row):
            return row['pokemon_species_id'] == mon['id'] and row['local_language_id'] == PokeApi.language

        mon = self.random_pokemon()
        name = discord.utils.find(find_cb, self.pokemon_species_names + self.pokemon_form_names)['name']
        if clean:
            name = self.clean_name(name)
        return name

    def random_move(self):
        return random.choice(self.moves)

    def random_move_name(self, *, clean=True):
        move = self.random_move()
        name = discord.utils.find(lambda row: row['move_id'] == move['id'] and row['local_language_id'] == PokeApi.language, self.move_names)['identifier']
        if clean:
            name = self.clean_name(name)
        return name
