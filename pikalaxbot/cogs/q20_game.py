import discord
import math
from discord.ext import commands
from .utils.game import GameBase, GameCogBase, increment_score
import re
import difflib
import nltk
from ..ext.pokeapi.models import *


class Q20QuestionParser:
    IGNORE_WORDS_1 = re.compile(r'\b(an?|the|i[stn]|(in)?to|can|does|could|are)\b', re.IGNORECASE)
    FOSSILS = (
        138,
        139,
        140,
        141,
        142,
        345,
        346,
        347,
        348,
        408,
        409,
        410,
        411,
        564,
        565,
        566,
        567,
        696,
        697,
        698,
        699,
        880,
        881,
        882,
        883
    )

    def __init__(self, game, pokeapi):
        self.game: Q20GameObject = game
        self.bot = game.bot
        self.pokeapi = pokeapi

    async def lookup_name(self, table, q):
        q = q.lower()

        async def inner():
            bank = {name.lower().replace('♀', '_F').replace('♂', '_m').replace('é', 'e'): name for name in await self.pokeapi.get_names_from(table)}

            def innermost(cutoff=0.9):
                yield difflib.get_close_matches(q, bank, cutoff=cutoff)
                for bigram in re.findall(r'(?=(\S+\s+\S+))', q):
                    yield difflib.get_close_matches(bigram, bank, cutoff=cutoff)
                for word in q.split():
                    yield difflib.get_close_matches(word, bank, cutoff=cutoff)

            return next((bank[r[0]] for r in innermost() if r), None)

        name = r = await inner()
        if name:
            r = await self.pokeapi.get_model_named(table, name)
        return name, r

    async def parse(self, question):
        solution: PokemonSpecies = self.game._solution

        async def pokemon(q):
            q = self.IGNORE_WORDS_1.sub('', q)
            q = re.sub(r'\s+', ' ', q, re.I)
            name, found = await self.lookup_name(PokemonSpecies, q)
            won = found and found.id == solution.id
            return name, 0, won, (name is not None) * (1000 if won else 0.5)

        async def move(q):
            confidence = len(re.findall(r'\b(learn|know|move|tm)\b', q, re.I)) * 5
            q = self.IGNORE_WORDS_1.sub('', q)
            q = re.sub(r'\b(learn|know|move|tm)\b', '', q, re.I)
            q = re.sub(r'\s+', ' ', q, re.I)
            name, found = await self.lookup_name(Move, q)
            return name, 0, found and await self.pokeapi.mon_can_learn_move(solution, found), confidence

        async def ability(q):
            confidence = len(re.findall(r'\b(have|ability)\b', q, re.I))
            q = self.IGNORE_WORDS_1.sub('', q)
            q = re.sub(r'\b(have|ability)\b', '', q, re.I)
            q = re.sub(r'\s+', ' ', q, re.I)
            name, found = await self.lookup_name(Ability, q)
            return name, 0, found and await self.pokeapi.mon_has_ability(solution, found), confidence

        async def type_(q):
            # fuck you tustin
            typeeffect = 0
            singletype = 0
            dualtype = 0
            nwords = len(re.findall(r'\w+', q))
            if re.search(r'\begg\b', q):
                return None, 0, False, 0
            q = re.sub(r'\s+', ' ', q, re.I)
            typeeffect -= len(re.findall(r'\b(resist|strong)\b', q, re.I))
            typeeffect += len(re.findall(r'\bweak\b', q, re.I))
            for match in re.findall(r'\b(((not )?very|super) )?effect[ia]ve\b', q, re.I):
                if 'not very' in match:
                    typeeffect -= 4
                elif 'super' in match:
                    typeeffect += 2
                else:
                    typeeffect += 1
            singletype += len(re.findall(r'\b(pure|single|one)\b', q, re.I))
            dualtype += len(re.findall(r'\b(du[ea]l|duo|two)\b', q, re.I))
            q = self.IGNORE_WORDS_1.sub('', q)
            q = re.sub(r'\b(type[ds]?|have|moves?|against|resist|strong|weak|(((not )?very|super) )?effect[ia]ve)\b', '', q, re.I)
            q = re.sub(r'\s+', ' ', q, re.I)
            nunkwords = len(re.findall(r'\w+', q))
            confidence = (nwords - nunkwords) / nwords * 5
            name, found = await self.lookup_name(Type, q)
            message = 0
            result = False
            if singletype and not found:
                mon_types = await self.pokeapi.get_mon_types(solution)
                result = len(mon_types) == 1
                name = 'single'
            elif dualtype and not found:
                mon_types = await self.pokeapi.get_mon_types(solution)
                result = len(mon_types) == 2
                name = 'dual'
            elif typeeffect:
                if found:
                    testeffect = await self.pokeapi.get_mon_matchup_against_type(solution, found)
                    message = 1 + (typeeffect < 0)
                    result = testeffect > 1 and typeeffect > 0 or testeffect < 1 and typeeffect < 0
                else:
                    _, mon = await self.lookup_name(PokemonSpecies, q)
                    if mon:
                        testeffect = await self.pokeapi.get_mon_matchup_against_mon(solution, mon)
                        message = 3 + (typeeffect < 0)
                        if len(testeffect) == 2:
                            if (testeffect[0] < 1 and testeffect[1] > 1 or testeffect[0] > 1 and testeffect[1] < 1):
                                result = False
                                confidence += 0x10000
                            else:
                                result = testeffect[0] < 1 and typeeffect < 0 or testeffect[0] > 1 and typeeffect > 0 or testeffect[1] < 1 and typeeffect < 0 or testeffect[1] > 1 and typeeffect > 0
                        else:
                            result = testeffect[0] < 1 and typeeffect < 0 or testeffect[0] > 1 and typeeffect > 0
                        name = await self.pokeapi.get_name(mon, clean=False)
                        if 0 in testeffect:
                            confidence += 0x20000
                    else:
                        name, move = await self.lookup_name(Move, q)
                        if move:
                            testeffect = await self.pokeapi.get_mon_matchup_against_move(solution, move)
                            message = 3 * typeeffect < 0
                            result = testeffect < 1 and typeeffect < 0 or testeffect > 1 and typeeffect > 0
                            if testeffect == 0:
                                confidence += 0x20000
            elif found:
                result = await self.pokeapi.mon_has_type(solution, found)
            return name, message, result, confidence

        async def color(q):
            q = self.IGNORE_WORDS_1.sub('', q)
            q = re.sub(r'\s+', ' ', q, re.I)
            name, color = await self.lookup_name(PokemonColor, q)
            return name, 0, color and color == solution.pokemon_color, 1 / len(re.findall(r'\w+', q))

        async def evolution(q):
            nwords = len(re.findall(r'\w+', q))
            q = self.IGNORE_WORDS_1.sub('', q)
            has = len(re.findall(r'\b(evolve|evolutions)\b', q, re.I))
            mega = len(re.findall(r'\bmega\b', q, re.I))
            branch = len(re.findall(r'\bbranch\b', q, re.I))
            stone = len(re.findall(r'\b(stone|fire|water|sun)\b', q, re.I))
            trade = len(re.findall(r'\btrade\b', q, re.I))
            q = re.sub(r'\b(evolve|evolutions|mega|branch|stone|fire|water|sub|trade)\b', '', q, re.I)
            q = re.sub(r'\s+', ' ', q, re.I)
            nunkwords = len(re.findall(r'\w+', q))
            confidence = (nwords - nunkwords) / nwords
            item = None
            message = 0
            result = False
            if mega:
                item = 'found'
                message = 2
                result = await self.pokeapi.has_mega_evolution(solution)
            elif has:
                item = 'found'
                message = 3
                result = solution.evolves_from_species is not None or len(await self.pokeapi.get_evos(solution)) > 0
            elif branch or stone or trade:
                message = 4
                result = False
            return item, message, result, confidence

        async def family(q):
            if not re.search(r'\b(family|evolution(ary)?|tree|line)\b', q, re.I):
                return None, 0, False, 0
            q = self.IGNORE_WORDS_1.sub('', q)
            q = re.sub(r'\b(family|evolution(ary)?|tree|line|part|of)\b', '', q, re.I)
            q = re.sub(r'\s+', ' ', q)
            name, res = await self.lookup_name(PokemonSpecies, q)
            return name, 0, res and any(mon.id == solution.id for mon in await self.pokeapi.get_evo_line(res)), name is not None

        async def pokedex(q):
            is_mine = re.search(r'\b(generation|gen|poke(dex)?|dex)\b', q, re.I) is not None
            q = self.IGNORE_WORDS_1.sub('', q)
            q = re.sub(r'\b(generation|gen|poke(dex)?|dex|in)\b', '', q, re.I)
            patterns = [
                r'\b(1|1st|first)\b',
                r'\b(2|2nd|second)\b',
                r'\b(3|3rd|third)\b',
                r'\b(4|4th|fourth)\b',
                r'\b(5|5th|fifth)\b',
                r'\b(6|6th|sixth)\b',
                r'\b(7|7th|seventh)\b',
                r'\b(8|8th|eighth)\b',
            ]
            generation, _ = discord.utils.find(lambda pat: re.search(pat[1], q, re.I) is not None, enumerate(patterns, 1)) or (-1, None)
            for pat in patterns:
                q = re.sub(pat, '', q, re.I)
            q = re.sub(r'\s+', '', q)
            dex_name, dex = await self.lookup_name(Pokedex, q)
            if dex_name is None and not is_mine:
                return None, 0, False, 0
            if dex_name is not None:
                result = await self.pokeapi.mon_is_in_dex(solution, dex)
                message = 1
                item = dex_name
            elif generation > -1:
                result = solution.generation.id == generation
                message = 0
                item = f'Generation {generation}'
            else:
                return None, 0, False, 0
            return item, message, result, 10

        async def booleans(q):
            fossil = re.search(r'\b(revived|fossil)\b', q, re.I) is not None
            legendary = re.search(r'\blegendary\b', q, re.I) is not None
            mythical = re.search(r'\bmythical\b', q, re.I) is not None
            if mythical:
                return 'Mythical', 0, solution.is_mythical, 10
            if legendary:
                return 'Legendary', 0, solution.is_legendary, 10
            if fossil:
                return 'Fossil', 0, solution.id in self.FOSSILS, 10
            return None, 0, False, 0

        async def size(q):
            size_compare = 0
            is_this_question = False
            size_literal = -1
            wrong_scale_error = False
            unknown_tokens = []
            name = 'meters'
            equal_message = 2
            for word in nltk.TreebankWordTokenizer().tokenize(q):
                if not word or self.IGNORE_WORDS_1.match(word):
                    pass
                elif re.match(r'^as$', word, re.I):
                    size_compare *= 0
                elif re.match(r'^th[ae]n$', word, re.I):
                    size_compare *= 2
                elif re.match(r'^(meters?|m|h(ei|ie)ght|size)$', word, re.I):
                    is_this_question = True
                elif re.match(r'^same$', word, re.I):
                    size_compare = 0
                elif re.match(r'^(tall(er)?|big(ger)?|>)$', word, re.I):
                    is_this_question = True
                    size_compare += 1
                elif re.match(r'^((short|small)(er)?|<)$', word, re.I):
                    is_this_question = True
                    size_compare -= 1
                elif re.match(r'[\'"]|\b(inch|inches|feet|foot|centimeters|cm)\b', word, re.I):
                    wrong_scale_error = True
                    size_literal = 999999
                elif (m := re.match(r'^([><=]?)([0-9]+(?:\.[0-9]+)?)(m|meters?)?$', word, re.I)):
                    size_literal = float(m[2])
                    is_this_question |= bool(m[3])
                    size_compare = (size_compare + (m[1] == '>') - (m[1] == '<')) * (m[1] != '=')
                else:
                    unknown_tokens.append(word)
            if not is_this_question:
                return None, 0, False, 0
            solution_forme: PokemonForm = await self.pokeapi.get_default_forme(solution)
            height = solution_forme.pokemon.height
            if size_literal <= 0:
                equal_message = 3
                conglom = ' '.join(unknown_tokens)
                if re.search(r'(hum[ao]n|person|trainer|man|woman|boy|girl)', conglom, re.I):
                    size_literal = 16
                    name = 'an average person'
                elif re.search(r'(house|home)', conglom, re.I):
                    size_literal = 76
                    name = 'a 2-story house'
                elif re.search(r'(bread(box)?|loaf)', conglom, re.I):
                    size_literal = 3
                    name = 'a breadbox'
                elif re.search(r'penis', conglom, re.I):
                    size_literal = 0.1
                    name = 'your penis'
                else:
                    name, mon = await self.lookup_name(PokemonSpecies, conglom)
                    if mon:
                        mon = await self.pokeapi.get_default_forme(mon)
                        size_literal = mon.height
            if size_literal > 0:
                if wrong_scale_error:
                    return 'error', 4, False, 1
                compare_size_literal = size_literal * 10
                if size_compare < 0:
                    message = 0
                    result = height < compare_size_literal
                elif size_compare > 0:
                    message = 1
                    result = height > compare_size_literal
                else:
                    message = equal_message
                    result = height == compare_size_literal
                if name == 'meters':
                    item = f'{size_literal}m'
                else:
                    item = name
                return item, message, result, 10

            return None, 0, False, 0

        async def weight(q):
            size_compare = 0
            is_this_question = False
            size_literal = -1
            wrong_scale_error = False
            unknown_tokens = []
            name = 'kilograms'
            equal_message = 2
            for word in nltk.TreebankWordTokenizer().tokenize(q):
                if not word or self.IGNORE_WORDS_1.match(word):
                    pass
                elif re.match(r'^as$', word, re.I):
                    size_compare *= 0
                elif re.match(r'^th[ae]n$', word, re.I):
                    size_compare *= 2
                elif re.match(r'^(kilo(gram)?s?|kg|w(ei|ie)gh[ts]?|mass)$', word, re.I):
                    is_this_question = True
                elif re.match(r'^same$', word, re.I):
                    size_compare = 0
                elif re.match(r'^(heav(y|ier)|more|>)$', word, re.I):
                    is_this_question = True
                    size_compare += 1
                elif re.match(r'^(light(er)?|less|<)$', word, re.I):
                    is_this_question = True
                    size_compare -= 1
                elif re.match(r'\b(lbs?|pound|grams?)\b', word, re.I):
                    wrong_scale_error = True
                    size_literal = 999999
                elif (m := re.match(r'^([><=]?)([0-9]+(?:\.[0-9]+)?)(kg|kilo(gram)?s?)?$', word, re.I)):
                    size_literal = float(m[2])
                    is_this_question |= bool(m[3])
                    size_compare = (size_compare + (m[1] == '>') - (m[1] == '<')) * (m[1] != '=')
                else:
                    unknown_tokens.append(word)
            if not is_this_question:
                return None, 0, False, 0
            solution_forme: PokemonForm = await self.pokeapi.get_default_forme(solution)
            weight = solution_forme.pokemon.weight
            if size_literal <= 0:
                equal_message = 3
                conglom = ' '.join(unknown_tokens)
                if re.search(r'(hum[ao]n|person|trainer|man|woman|boy|girl)', conglom, re.I):
                    size_literal = 66
                    name = 'an average person'
                elif re.search(r'(house|home)', conglom, re.I):
                    size_literal = 1800
                    name = 'a 2-story house'
                elif re.search(r'(bread(box)?|loaf)', conglom, re.I):
                    size_literal = 3
                    name = 'a breadbox'
                else:
                    name, mon = await self.lookup_name(PokemonSpecies, conglom)
                    if mon:
                        mon = await self.pokeapi.get_default_forme(mon)
                        size_literal = mon.weight
            if size_literal > 0:
                if wrong_scale_error:
                    return 'error', 4, False, 1
                compare_size_literal = size_literal * 10
                if size_compare < 0:
                    message = 0
                    result = weight < compare_size_literal
                elif size_compare > 0:
                    message = 1
                    result = weight > compare_size_literal
                else:
                    message = equal_message
                    result = weight == compare_size_literal
                if name == 'kilograms':
                    item = f'{size_literal}m'
                else:
                    item = name
                return item, message, result, 10

            return None, 0, False, 0

        async def habitat(q):
            if not re.search(r'\b(live|habitat)\b', q, re.I):
                return None, 0, False, 0
            q = self.IGNORE_WORDS_1.sub('', q)
            q = re.sub(r'\b(live|habitat|does|along|in|around)\b', '', q, re.I)
            q = re.sub('\s+', '', q)
            name, habitat = await self.lookup_name(PokemonHabitat, q)
            return name, 0, habitat == solution.habitat, name is not None

        async def stats(q):
            return None, 0, False, 0

        async def body(q):
            return None, 0, False, 0

        async def egg(q):
            return None, 0, False, 0

        async def mating(q):
            # owo
            return None, 0, False, 0

        methods = {
            pokemon: ['Is it {}?'],
            move: ['Can it learn {}?'],
            ability: ['Can it have the ability {}?'],
            type_: ['Is it {} type?', 'Is it weak to {} type?', 'Does it resist {} type?', 'Is it weak against {}?', 'Does it resist {}?'],
            color: ['Is its colour {}?'],
            evolution: ['Does it evolve into {}?', 'Does it evolve from {}?', 'Does it have a mega evolution?', 'Does it evolve?', 'I don\'t know anything about evolution methods lol'],
            family: ['Is it part of the {} family?'],
            pokedex: ['Is it a {} generation Pokemon?', 'Is it in the {} Pokedex?'],
            booleans: ['Is it a {}?'],
            size: ['Is it smaller than {}?', 'Is it taller than {}?', 'Is it {} tall?', 'Is it as tall as {}?', 'I can only understand height measurements in meters.'],
            weight: ['Does it weigh less than {}?', 'Does it weigh more than {}?', 'Does it weigh {}?', 'Does it weigh the same as {}', ],
            habitat: ['Does it live in the {} habitat?'],
            stats: [''],
            body: [''],
            egg: [''],
            mating: ['']
        }
        responses = []
        for i, (method, msgbank) in enumerate(methods.items()):
            item, message, match, confidence = await method(question)
            valid = True
            if item:
                match_t = 'Yes' if match else 'No'
                if method == pokemon and match:
                    match_t = '**YES!!**'
                if method == type_ and solution.id == 493:
                    match_t = {
                        'single': 'HAHAHAHAHAHAHAHAHA!!!',
                        'dual': 'Nah'
                    }.get(item, 'Sometimes')
                if method == type_:
                    if confidence >= 0x20000:
                        confidence -= 0x20000
                        match_t = 'It is immune'
                    if confidence >= 0x10000:
                        confidence -= 0x10000
                        if match_t == 'It is immune':
                            match_t = 'It is sometimes immune'
                        else:
                            match_t = 'Sometimes'
                if method == pokedex and item == 'National':
                    match_t = 'Duh.'
                if method in (size, weight) and message == 4:
                    valid = False
                if valid:
                    response_s = f'`{msgbank[message].format(item)}`: {match_t}'
                else:
                    response_s = msgbank[message].format(item)
                responses.append((confidence, response_s, method == pokemon and match, valid))
        if not responses:
            return 'Huh? I didn\'t understand that', False, False
        responses.sort(reverse=True)
        return responses[0][1:]


class Q20GameObject(GameBase):
    def __init__(self, bot):
        super().__init__(bot, timeout=300)
        self._attempts = 20

    def reset(self):
        super().reset()
        self._solution = ''
        self._state = []
        self.attempts = 0

    @property
    def state(self):
        return '\n'.join(self._state)

    def __str__(self):
        return f'```Players: {self.get_player_names()}\n' \
               f'Remaining questions: {self.attempts}\n' \
               f'Questions asked:\n' \
               f'{self.state}\n' \
               f'```'

    async def start(self, ctx: commands.Context):
        if self.running:
            await ctx.send(f'{ctx.author.mention}: Q20 is already running here.', delete_after=10)
        else:
            pokeapi = self.bot.pokeapi
            self._solution: pokeapi.PokemonSpecies = await pokeapi.random_pokemon()
            self.attempts = self._attempts
            await ctx.send(f'I am thinking of a Pokemon. You have {self.attempts:d} questions and {self._timeout:d} '
                           f'seconds to guess correctly.\n\n'
                           f'Use `{ctx.prefix}q20 ask <question>` to narrow it down.')
            await super().start(ctx)

    async def end(self, ctx: commands, failed=False, aborted=False):
        if self.running:
            pokeapi = self.bot.pokeapi
            name = await pokeapi.get_name(self._solution, clean=False)
            if self._task and not self._task.done():
                self._task.cancel()
                self._task = None
            await self._message.edit(content=self)
            if aborted:
                await ctx.send(f'Game terminated by {ctx.author.mention}\n'
                               f'Solution: {name}')
            elif failed:
                await ctx.send(f'You did not guess what I was thinking of.\n'
                               f'Solution: {name}')
            else:
                bonus = math.ceil(self._max_score / 10)
                async with self.bot.sql as sql:
                    await increment_score(sql, ctx.author, by=bonus)
                score = await self.award_points()
                await ctx.send(f'{ctx.author.mention} has guessed the solution! It was {name}!\n'
                               f'The following players each earn {score:d} points:\n'
                               f'```{self.get_player_names()}```\n'
                               f'{ctx.author.mention} gets an extra {bonus} points for solving the puzzle!')
            self.reset()
        else:
            await ctx.send(f'{ctx.author.mention}: The Q20 game is not running here. '
                           f'Start a game by saying `{ctx.prefix}q20 start`.',
                           delete_after=10)

    async def ask(self, ctx: commands.Context, question):
        if not self.running:
            if ctx.command:
                await ctx.send('Q20 is not running here.')
            return
        pokeapi = self.bot.pokeapi
        async with ctx.typing():
            message, res, valid = await Q20QuestionParser(self, pokeapi).parse(question)
        if message in self._state:
            return await ctx.send('You\'ve already asked that!')
        await ctx.send(message)
        if not valid:
            return
        self._state.append(message)
        if res:
            self.add_player(ctx.author)
            return await self.end(ctx)
        else:
            self.attempts -= 1
            if self.attempts == 0:
                return await self.end(ctx, failed=True)
        await self._message.edit(content=self)


class Q20Game(GameCogBase):
    gamecls = Q20GameObject

    def cog_check(self, ctx):
        return self._local_check(ctx)

    @commands.group(case_insensitive=True, aliases=['q'])
    async def q20(self, ctx):
        """Play Q20"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(self.q20)

    @q20.command()
    async def start(self, ctx):
        """Start a game in the current channel"""
        await self.game_cmd('start', ctx)

    @commands.command(name='q20start', aliases=['qst'])
    async def q20_start(self, ctx):
        """Start a game in the current channel"""
        await self.start(ctx)

    @q20.command()
    async def ask(self, ctx, *, question):
        """Ask a question"""
        await self.game_cmd('ask', ctx, question)

    @commands.command(name='q20ask', aliases=['qa', 'ask'])
    async def q20_ask(self, ctx, *, question):
        """Ask a question"""
        await self.ask(ctx, question=question)

    @q20.command()
    async def show(self, ctx):
        """Show the Q20 game state"""

        await self.game_cmd('show', ctx)

    @commands.command(name='q20show', aliases=['qsh'])
    async def q20_show(self, ctx):
        """Show the Q20 game state"""

        await self.show(ctx)

    @q20.command()
    async def end(self, ctx):
        """Abort the Q20 game early"""

        await self.game_cmd('end', ctx, aborted=True)

    @commands.command(name='q20end', aliases=['qe', 'qend'])
    async def q20_end(self, ctx):
        """Abort the Q20 game early"""

        await self.end(ctx)


def setup(bot):
    bot.add_cog(Q20Game(bot))
