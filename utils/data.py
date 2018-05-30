import csv
import random


class Data:
    def __init__(self):
        with open('data/pokemon.tsv') as fp:
            self.pokemon = list(csv.DictReader(fp))
        with open('data/moves.tsv') as fp:
            self.moves = list(csv.DictReader(fp))

    def random_pokemon(self):
        return random.choice(self.pokemon)

    def random_pokemon_attr(self, attr, default=None):
        return self.random_pokemon().get(attr, default)

    def random_move(self):
        return random.choice(self.moves)

    def random_move_attr(self, attr, default=None):
        return self.random_move().get(attr, default)

    def random_pokemon_name(self):
        return self.random_pokemon_attr('name', 'Phancero')

    def random_move_name(self):
        return self.random_move_attr('name', 'Struggle')


data = Data()
