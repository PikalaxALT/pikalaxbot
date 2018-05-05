class Data:
    def __init__(self):
        with open('data/pokemon.txt') as fp:
            self.pokemon = tuple(line.strip() for line in fp)


data = Data()
