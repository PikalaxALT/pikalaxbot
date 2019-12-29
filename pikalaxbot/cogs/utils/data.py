# PikalaxBOT - A Discord bot in discord.py
# Copyright (C) 2018  PikalaxALT
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

import csv
import random
import os


__all__ = ('data',)


def roman(s):
    table = {
        'I': 1,
        'V': 5,
        'X': 10,
        'L': 50,
        'C': 100,
        'D': 500,
        'M': 1000
    }
    return sum(map(lambda t: table.get(t, 0), s.upper()))


def safe_int(s: str) -> int:
    return 0 if not s.isnumeric() else int(s)


class Data:
    pokemon_categories = {
        'number': int,
        'name': str,
        'type': lambda s: s.split(',')
    }
    move_categories = {
        'num': int,
        'name': str,
        'type': str,
        'category': str,
        'contest': str,
        'pp': safe_int,
        'power': safe_int,
        'accuracy': lambda s: safe_int(s.rstrip('%')),
        'gen': roman
    }

    def __init__(self):
        self.pokemon = []
        self.moves = []

        dname = os.path.abspath(f'{os.path.dirname(__file__)}/../../data')
        with open(os.path.join(dname, 'pokemon.tsv')) as fp:
            reader = csv.DictReader(fp, dialect='excel-tab')
            for row in reader:
                for key in reader.fieldnames:
                    row[key] = self.pokemon_categories.get(key, str)(row[key])
                self.pokemon.append(row)
        with open(os.path.join(dname, 'moves.tsv')) as fp:
            reader = csv.DictReader(fp, dialect='excel-tab')
            for row in reader:
                for key in reader.fieldnames:
                    row[key] = self.move_categories.get(key, str)(row[key].rstrip(' *'))
                self.moves.append(row)

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
