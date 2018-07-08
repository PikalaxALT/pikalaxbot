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
#
# Unapologetically aped from https://github.com/TwitchPlaysPokemon/tpp/utils/markov.py

from collections import defaultdict, Counter
from random import choices


class Chain:
    # tbl = { ( state0, state1, ... ): { next_obj: count, ... }, ... }
    def __init__(self, state_size=2, store_lowercase=False):
        self.tbl = defaultdict(Counter)
        self.state_size = state_size
        self.store_lowercase = store_lowercase

    @staticmethod
    def __weighted_choice(items):
        return choices(list(items), weights=items.values())[0]

    def __lower(self, obj):
        return str(obj).lower() if self.store_lowercase else obj

    def learn(self, state, obj):
        self.tbl[state][obj] += 1

    def learn_list(self, objs):
        state = (None,) * self.state_size
        for obj in objs:
            self.learn(state, obj)
            state = state[1:] + (self.__lower(obj),)
        self.learn(state, None)

    def learn_str(self, string):
        self.learn_list(string.split())

    def unlearn(self, state, obj):
        if obj in self.tbl[state]:
            self.tbl[state][obj] -= 1
            if self.tbl[state][obj] == 0:
                self.tbl[state].pop(obj)
                if len(self.tbl[state]) == 0:
                    self.tbl.pop(state)

    def unlearn_list(self, objs):
        state = (None,) * self.state_size
        for obj in objs:
            self.unlearn(state, obj)
            state = state[1:] + (self.__lower(obj),)
        self.unlearn(state, None)

    def unlearn_str(self, string):
        self.unlearn_list(string.split())

    def generate(self, max_count=64):
        result = []
        state = (None,) * self.state_size
        for _ in range(max_count):
            if state not in self.tbl:
                break
            next_obj = self.__weighted_choice(self.tbl[state])
            if next_obj is None:
                break
            result.append(next_obj)
            state = state[1:] + (self.__lower(next_obj),)
        return result

    def generate_str(self, max_count=64):
        return str.join(' ', self.generate(max_count))
