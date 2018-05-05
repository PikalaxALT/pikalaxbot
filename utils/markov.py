"""
Unapologetically aped from https://github.com/TwitchPlaysPokemon/tpp/utils/markov.py
"""


from collections import defaultdict
from random import randint


class Chain:
    # tbl = { ( state0, state1, ... ): { next_obj: count, ... }, ... }
    def __init__(self, state_size=2, store_lowercase=False):
        self.tbl = defaultdict(dict)
        self.state_size = state_size
        self.store_lowercase = store_lowercase

    def __weighted_choice(self, items):
        s = 0
        for key in items:
            s += items[key]
        r = randint(0, s - 1)
        s = 0
        for key in items:
            s += items[key]
            if r < s:
                return key

    def __lower(self, obj):
        if self.store_lowercase:
            return str(obj).lower()
        else:
            return obj

    def learn(self, state, obj):
        if obj in self.tbl[state]:
            self.tbl[state][obj] += 1
        else:
            self.tbl[state][obj] = 1

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
                if len(self.tbl[state]) == 0: self.tbl.pop(state)

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
            if next_obj == None:
                break
            result.append(next_obj)
            state = state[1:] + (self.__lower(next_obj),)
        return result

    def generate_str(self, max_count=64):
        return str.join(' ', self.generate(max_count))
