import discord
import math
from discord.ext import commands
from .utils.game import GameBase, GameCogBase, increment_score
import re
import difflib
import random
import nltk
from typing import Tuple, TYPE_CHECKING, Optional, Mapping, Callable, Coroutine, List
if TYPE_CHECKING:
    from ..ext.pokeapi import PokeApi, NamedPokeapiResource


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

    mon_search = {
        re.compile(r'^(nidoran (female|girl)|(female|girl) nidoran)$', re.I): 29,
        re.compile(r'^(nidorina|nidorina (female|girl)|(female|girl) nidorina)$', re.I): 30,
        re.compile(r'^(nidoran (male|boy)|(male|boy) nidoran)$', re.I): 32,
        re.compile(r'^(nidorino|nidorino (female|girl)|(female|girl) nidorino)$', re.I): 33,
        re.compile(r'farfetch[e\']?d|dux', re.I): 83,
        re.compile(r'^(gh?astle?y)$', re.I): 92,
        re.compile(r'mr\.? ?mime', re.I): 122,
        re.compile(r'^dragonair$', re.I): 148,
        re.compile(r'^dragonite$', re.I): 149,
        re.compile(r'porygon[ -]?(2|two)', re.I): 223,
        re.compile(r'ho[ -]?oh', re.I): 250,
        re.compile(r'mime ?jr\.?', re.I): 439,
        re.compile(r'porygon[ -]?z', re.I): 474,
        re.compile(r'flabebe', re.I): 669, # accents!
        re.compile(r'starly', re.I): 396,

        # TPP Mon
        re.compile(r'^(abby)$', re.I): 5,
        re.compile(r'^(tiger)$', re.I): 6,
        re.compile(r'^(bird jesus|jesus)$', re.I): 18,
        re.compile(r'^(jay leno)$', re.I): 19,
        re.compile(r'^(digrat|ace)$', re.I): 20,
        re.compile(r'^(atv)$', re.I): 49,
        re.compile(r'^(rick gh?astly)$', re.I): 92,
        re.compile(r'^(c3ko)$', re.I): 106,
        re.compile(r'^(air)$', re.I): 131,
        re.compile(r'^(lord )?helix$', re.I): 139,
        re.compile(r'^(lord )?dome$', re.I): 141,
        re.compile(r'^(archang(el|le) of justice|battery jesus, re.I)$'): 145,
        re.compile(r'^(laz[oe]rgat[oe]r)$', re.I): 160,
        re.compile(r'^(admiral|adi)$', re.I): 161,
        re.compile(r'^m4$', re.I): 184,
        re.compile(r'^(mighty ?doge)$', re.I): 262,
        re.compile(r'^(lotid)$', re.I): 270,
        re.compile(r'^(bird ?cop)$', re.I): 278,
        re.compile(r'^(c3|ccc)$', re.I): 312,
        re.compile(r'^((lord )?root|potato)$', re.I): 346,
        re.compile(r'^kenya+$', re.I): 383,
        re.compile(r'^de(le){1,} ?wo{2,}p$', re.I): 402,
        re.compile(r'^(sunshine)$', re.I): 403,
        re.compile(r'^(sunbrella)$', re.I): 407,
        re.compile(r'^(dairy queen)$', re.I): 483,
        re.compile(r'^(nonon)$', re.I): 535,
        # re.compile(r'^(5|five)$', re.I): 585,
        re.compile(r'^(peter sparker|sparky)$', re.I): 595,
        re.compile(r'^(deer god)$', re.I): 716,
    }

    move_search = {
        re.compile(r'whirl ?wind', re.I): 18,
        re.compile(r'double[ -]?edge', re.I): 38,
        re.compile(r'twin( ?n)?ee?dle', re.I): 41,
        re.compile(r'flame ?thrower', re.I): 53,
        re.compile(r'smoke ?scree?n', re.I): 108,
        re.compile(r'self[ -]?d[ie]struct', re.I): 120,
        re.compile(r'soft[ -]?boile?d?', re.I): 135,
        re.compile(r'mud[ -]?slap', re.I): 189,
        re.compile(r'lock[ -]?on', re.I): 199,
        re.compile(r'will?[ -]?o[ -]?wh?isp', re.I): 261,
        re.compile(r'super ?power', re.I): 276,
        re.compile(r'wake[ -]?up ?slap', re.I): 358,
        re.compile(r'tail ?wind', re.I): 366,
        re.compile(r'u[ -]?turn', re.I): 369,
        re.compile(r'x[ -]?(scis?sor|sicc?ors)', re.I): 404,
        re.compile(r'v[ -]?create', re.I): 557,
        re.compile(r'trick[ -]?or[ -]?treat', re.I): 567,
        re.compile(r'freeze[ -]?dry', re.I): 573,
        re.compile(r'topse?y[ -]?turve?y', re.I): 576,
        re.compile(r'king\'?s ?sh(ie|ei)ld', re.I): 588,
        re.compile(r'baby[ -]?doll ?eyes', re.I): 608,
        re.compile(r'power[ -]?up ?punch', re.I): 612,
        re.compile(r'land\'?s ?wrath', re.I): 616,
    }

    def __init__(self, game, pokeapi):
        self.game: Q20GameObject = game
        self.bot = game.bot
        self.pokeapi = pokeapi
        self.differ = difflib.SequenceMatcher()
        self.tokenizer = nltk.WordPunctTokenizer()

    async def lookup_name(self, table, q) -> Tuple[Optional[str], 'Optional[NamedPokeapiResource]', float]:
        q = q.lower()
        bank = {
            name.lower().replace('♀', '_F').replace('♂', '_m').replace('é', 'e'): name
            for name in await self.pokeapi.get_names_from(table)
        }

        def get_ratio(w1, w2):
            self.differ.set_seq1(w1)
            self.differ.set_seq2(w2)
            return min(self.differ.real_quick_ratio(), self.differ.quick_ratio(), self.differ.ratio())

        def iter_matches(*, cutoff=0.85):
            yield difflib.get_close_matches(q, bank, cutoff=cutoff), q
            for bigram in re.findall(r'(?=(\S+\s+\S+))', q):
                yield difflib.get_close_matches(bigram, bank, cutoff=cutoff), bigram
            for word in q.split():
                yield difflib.get_close_matches(word, bank, cutoff=cutoff), word

        name = r = next(((bank[r[0]], s) for r, s in iter_matches() if r), None)
        confidence = 0
        if not name:
            def iter_matches(pattern):
                yield pattern.match(q)
                for bigram in re.findall(r'(?=(\S+\s+\S))', q):
                    yield pattern.match(bigram)
                for word in q.split():
                    yield pattern.match(word)

            def get_first_match(lut):
                return discord.utils.find(lambda t: next((m for m in iter_matches(t[0]) if m is not None), None) is not None, lut.items()) or (None, None)

            if table in (self.pokeapi.Pokemon, self.pokeapi.PokemonSpecies):
                pat, id_ = get_first_match(Q20QuestionParser.mon_search)
            elif table is self.pokeapi.Move:
                pat, id_ = get_first_match(Q20QuestionParser.move_search)
            else:
                id_ = None
            if id_:
                r = await self.pokeapi.get_model(table, id_)
                name = await self.pokeapi.get_name(r)
                confidence = 1
        else:
            name, orig = name
            r = await self.pokeapi.get_model_named(table, name)
            confidence = get_ratio(name, orig)
        return name, r, confidence

    async def parse(self, question):
        solution = self.game._solution

        async def pokemon(q):
            q = self.IGNORE_WORDS_1.sub('', q)
            q = re.sub(r'\s+', ' ', q, re.I)
            found: 'Optional[PokeApi.PokemonSpecies]'
            name, found, confidence = await self.lookup_name(self.pokeapi.PokemonSpecies, q)
            won = found and found.id == solution.id
            return name, 0, won, (name is not None) * (1000 if won else 0.5 * confidence)

        async def move(q):
            confidence = len(re.findall(r'\b(learn|know|move|tm)\b', q, re.I)) * 5
            q = self.IGNORE_WORDS_1.sub('', q)
            q = re.sub(r'\b(learn|know|move|tm)\b', '', q, re.I)
            q = re.sub(r'\s+', ' ', q, re.I)
            found: 'Optional[PokeApi.Move]'
            name, found, confidence_f = await self.lookup_name(self.pokeapi.Move, q)
            return name, 0, found and await self.pokeapi.mon_can_learn_move(solution, found), confidence * confidence_f

        async def ability(q):
            confidence = len(re.findall(r'\b(have|ability)\b', q, re.I))
            q = self.IGNORE_WORDS_1.sub('', q)
            q = re.sub(r'\b(have|ability)\b', '', q, re.I)
            q = re.sub(r'\s+', ' ', q, re.I)
            found: 'Optional[PokeApi.Ability]'
            name, found, confidence_f = await self.lookup_name(self.pokeapi.Ability, q)
            return name, 0, found and await self.pokeapi.mon_has_ability(solution, found), confidence * confidence_f

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
            found: 'Optional[PokeApi.Type]'
            name, found, confidence_f = await self.lookup_name(self.pokeapi.Type, q)
            message = 0
            result = False
            flags = 0
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
                    if testeffect == 0:
                        flags |= 0x2000
                else:
                    mon: 'Optional[PokeApi.PokemonSpecies]'
                    name, mon, confidence_f = await self.lookup_name(self.pokeapi.PokemonSpecies, q)
                    if mon:
                        testeffect = await self.pokeapi.get_mon_matchup_against_mon(solution, mon)
                        assert len(testeffect) in (1, 2)
                        message = 3 + (typeeffect < 0)
                        if len(testeffect) == 2:
                            if (testeffect[0] < 1 and testeffect[1] > 1 or testeffect[0] > 1 and testeffect[1] < 1):
                                result = False
                                flags |= 0x10000
                            else:
                                result = testeffect[0] < 1 and typeeffect < 0 or testeffect[0] > 1 and typeeffect > 0 or testeffect[1] < 1 and typeeffect < 0 or testeffect[1] > 1 and typeeffect > 0
                        else:
                            result = testeffect[0] < 1 and typeeffect < 0 or testeffect[0] > 1 and typeeffect > 0
                        if 0 in testeffect:
                            flags |= 0x20000
                    else:
                        _move: 'Optional[PokeApi.Move]'
                        name, _move, confidence_f = await self.lookup_name(self.pokeapi.Move, q)
                        if _move:
                            testeffect = await self.pokeapi.get_mon_matchup_against_move(solution, _move)
                            message = 3 + (typeeffect < 0)
                            result = testeffect < 1 and typeeffect < 0 or testeffect > 1 and typeeffect > 0
                            if testeffect == 0:
                                flags |= 0x20000
            elif found:
                result = await self.pokeapi.mon_has_type(solution, found)
            return name, message, result, confidence * confidence_f + flags

        async def color(q):
            q = self.IGNORE_WORDS_1.sub('', q)
            q = re.sub(r'\s+', ' ', q, re.I)
            _color: 'Optional[PokeApi.PokemonColor]'
            name, _color, confidence = await self.lookup_name(self.pokeapi.PokemonColor, q)
            return name, 0, _color and _color == solution.pokemon_color, confidence / len(re.findall(r'\w+', q)) if q else 0

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
            res: 'Optional[PokeApi.PokemonSpecies]'
            name, res, confidence = await self.lookup_name(self.pokeapi.PokemonSpecies, q)
            return name, 0, res and any(mon.id == solution.id for mon in await self.pokeapi.get_evo_line(res)), confidence

        async def pokedex(q):
            is_mine = re.search(r'\b(generation|gen|poke(dex)?|dex|region)\b', q, re.I) is not None
            q = self.IGNORE_WORDS_1.sub('', q)
            q = re.sub(r'\b(generation|gen|poke(dex)?|dex|in|region)\b', '', q, re.I)
            patterns = [
                r'\b(1|1st|first|i)\b',
                r'\b(2|2nd|second|ii)\b',
                r'\b(3|3rd|third|iii)\b',
                r'\b(4|4th|fourth|iv)\b',
                r'\b(5|5th|fifth|v)\b',
                r'\b(6|6th|sixth|vi)\b',
                r'\b(7|7th|seventh|vii)\b',
                r'\b(8|8th|eighth|viii)\b',
            ]
            generation, _ = discord.utils.find(lambda pat: re.search(pat[1], q, re.I) is not None, enumerate(patterns, 1)) or (-1, None)
            for pat in patterns:
                q = re.sub(pat, '', q, re.I)
            q = re.sub(r'\s+', '', q)
            dex: 'Optional[PokeApi.Pokedex]'
            dex_name, dex, confidence = await self.lookup_name(self.pokeapi.Pokedex, q)
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
                region: 'Optional[PokeApi.Region]'
                region_name, region, confidence = await self.lookup_name(self.pokeapi.Region, q)
                if region_name is None:
                    return None, 0, False, 0
                result = solution.generation.id == region.id
                message = 0
                item = f'{region_name} region'
            return item, message, result, 10 * confidence

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
            confidence = 1
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
                elif m := re.match(r'^([><=]?)([0-9]+(?:\.[0-9]+)?)(m|meters?)?$', word, re.I):
                    size_literal = float(m[2])
                    is_this_question |= bool(m[3])
                    size_compare = (size_compare + (m[1] == '>') - (m[1] == '<')) * (m[1] != '=')
                else:
                    unknown_tokens.append(word)
            if not is_this_question:
                return None, 0, False, 0
            solution_forme = await self.pokeapi.get_default_forme(solution)
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
                    mon: 'Optional[PokeApi.PokemonSpecies]'
                    name, mon, confidence_f = await self.lookup_name(self.pokeapi.PokemonSpecies, conglom)
                    if mon:
                        mon: 'Optional[PokeApi.PokemonForm]' = await self.pokeapi.get_default_forme(mon)
                        size_literal = mon.pokemon.height / 10
                        confidence = confidence_f
            if size_literal > 0:
                if wrong_scale_error:
                    return 'error', 4, False, 1
                compare_size_literal = round(size_literal * 10)
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
                return item, message, result, 10 * confidence

            return None, 0, False, 0

        async def weight(q):
            size_compare = 0
            is_this_question = False
            size_literal = -1
            wrong_scale_error = False
            unknown_tokens = []
            name = 'kilograms'
            equal_message = 2
            confidence = 1
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
                elif m := re.match(r'^([><=]?)([0-9]+(?:\.[0-9]+)?)(kg|kilo(gram)?s?)?$', word, re.I):
                    size_literal = float(m[2])
                    is_this_question |= bool(m[3])
                    size_compare = (size_compare + (m[1] == '>') - (m[1] == '<')) * (m[1] != '=')
                else:
                    unknown_tokens.append(word)
            if not is_this_question:
                return None, 0, False, 0
            solution_forme = await self.pokeapi.get_default_forme(solution)
            _weight = solution_forme.pokemon.weight
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
                    mon: 'Optional[PokeApi.PokemonSpecies]'
                    name, mon, confidence_f = await self.lookup_name(self.pokeapi.PokemonSpecies, conglom)
                    if mon:
                        mon: 'Optional[PokeApi.PokemonForm]' = await self.pokeapi.get_default_forme(mon)
                        size_literal = mon.pokemon.weight / 10
                        confidence = confidence_f
            if size_literal > 0:
                if wrong_scale_error:
                    return 'error', 4, False, 1
                compare_size_literal = round(size_literal * 10)
                if size_compare < 0:
                    message = 0
                    result = _weight < compare_size_literal
                elif size_compare > 0:
                    message = 1
                    result = _weight > compare_size_literal
                else:
                    message = equal_message
                    result = _weight == compare_size_literal
                if name == 'kilograms':
                    item = f'{size_literal}m'
                else:
                    item = name
                return item, message, result, 10 * confidence

            return None, 0, False, 0

        async def habitat(q):
            if not re.search(r'\b(live|habitat)\b', q, re.I):
                return None, 0, False, 0
            q = self.IGNORE_WORDS_1.sub('', q)
            q = re.sub(r'\b(live|habitat|does|along|in|around)\b', '', q, re.I)
            q = re.sub('\s+', '', q)
            _habitat: 'Optional[PokeApi.PokemonHabitat]'
            name, _habitat, confidence = await self.lookup_name(self.pokeapi.PokemonHabitat, q)
            return name, 0, _habitat == solution.habitat, confidence

        async def stats(q):
            return None, 0, False, 0

        async def body(q):
            if not re.search(r'\b(shaped?|form(ed)?)\b', q, re.I):
                return None, 0, False, 0
            q = self.IGNORE_WORDS_1.sub('', q)
            q = re.sub(r'\b(shaped?|form(ed)?|like)', '', q, re.I)
            shape: 'Optional[PokeApi.PokemonShape]'
            name, shape, confidence = await self.lookup_name(self.pokeapi.PokemonShape, q)
            message = 0
            if not name:
                mon: 'Optional[PokeApi.PokemonSpecies]'
                name, mon, confidence = await self.lookup_name(self.pokeapi.PokemonSpecies, q)
                if not name:
                    return None, 0, False, 0
                message = 1
                shape = mon.shape
            return name, message, shape == solution.shape, confidence

        async def egg(q):
            return None, 0, False, 0

        async def mating(q):
            # owo
            return None, 0, False, 0

        methods: Mapping[Callable[[str], Coroutine[None, None, Tuple[Optional[str], int, bool, float]]], List[str]] = {
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
            body: ['Is it {}-shaped?', 'Is it the same shape as {}?'],
            egg: [''],
            mating: ['']
        }
        responses: List[Tuple[float, str, bool, bool]] = []
        for i, (method, msgbank) in enumerate(methods.items()):
            _item, _message, match, _confidence = await method(question)
            valid = True
            if _item:
                match_t = 'Yes' if match else 'No'
                if method == pokemon and match:
                    match_t = '**YES!!**'
                elif method == type_:
                    if solution.id == 493:
                        match_t = {
                            'single': 'HAHAHAHAHAHAHAHAHA!!!',
                            'dual': 'Nah'
                        }.get(_item, 'Sometimes')
                    else:
                        if _confidence >= 0x20000:
                            _confidence -= 0x20000
                            match_t = 'It is immune'
                        if _confidence >= 0x10000:
                            _confidence -= 0x10000
                            if match_t == 'It is immune':
                                match_t = 'It is sometimes immune'
                            else:
                                match_t = 'Sometimes'
                elif method == pokedex and _item == 'National':
                    match_t = 'Duh.'
                elif method in (size, weight) and _message == 4:
                    valid = False
                elif method == evolution and _message == 3 and match:
                    match_t = 'Yes, it has evolved' if solution.evolves_from_species else 'Yes, it will evolve'
                elif method == move and solution.id > 807:
                    match_t = 'I have no clue'
                if valid:
                    response_s = f'`{msgbank[_message].format(_item)}`: {match_t}'
                    valid = match_t != 'I have no clue'
                else:
                    response_s = msgbank[_message].format(_item)
                responses.append((_confidence, response_s, method == pokemon and match, valid))
        if not responses:
            return 'Huh? I didn\'t understand that', False, False
        responses.sort(reverse=True)
        return responses[0][1:]


class Q20GameObject(GameBase):
    _sample_questions = (
        "is it Magikarp?",
        "is it Lapras",
        "is it Dux?",
        "can it have sturdy",
        "does it have the ability sand veil",
        "could it have the ability volt absorb?",
        "is it a fire type",
        "is it weak to ice?",
        "does it resist water?",
        "is it dual typed",
        "is it part of the eevee family?",
        "is it in the ralts evolutionary line",
        "can it learn flamethrower",
        "can it learn Ice Beam?",
        "does it learn trick room",
        "is it taller than 2 meters",
        "is it shorter than a house?",
        "is it smaller than pikachu?",
        "is it bigger than 5m?",
        "is it a legendary",
        "is it a fossil pokemon?",
        "is it blue?",
        "is it red",
        "can it evolve",
        "can it mega evolve?",
        "is it in the kanto pokedex?",
        "is it in the national pokedex",
        "is it in the fifth gen?",
        "is it humanoid shaped?",
    )

    def __init__(self, bot):
        super().__init__(bot, timeout=None)
        self._attempts = 20
        self._parser = Q20QuestionParser(self, bot.pokeapi)

    def reset(self):
        super().reset()
        self._solution = ''
        self._state = []
        self.attempts = 0

    @property
    def state(self):
        return '\n'.join(f'{i:>2d}: {q}' for i, q in enumerate(self._state, 1))

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
            samples = random.sample(self._sample_questions, 3)
            prefix, *_ = await self.bot.get_prefix(ctx.message)
            await ctx.send(f'I am thinking of a Pokemon. You have {self.attempts:d} questions to guess correctly.\n\n'
                           f'Use `{prefix}<question>` to narrow it down.\n\n'
                           f'**Examples:**\n' + '\n'.join(f'`{prefix}{q}`' for q in samples))
            await super().start(ctx)

    async def end(self, ctx: commands, failed=False, aborted=False):
        if self.running:
            name = self._solution.name
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
                bonus = math.ceil(self._max_score / 200 * (21 - self._attempts))
                async with self.bot.sql as sql:
                    await increment_score(sql, ctx.author, by=bonus)
                score = await self.award_points()
                tries = f'{20 - self._attempts} tries' if self._attempts < 19 else 'a single try'
                await ctx.send(f'{ctx.author.mention} has guessed the solution! It was {name}!\n'
                               f'The following players each earn {score:d} points:\n'
                               f'```{self.get_player_names()}```\n'
                               f'{ctx.author.mention} gets an extra {bonus} points for getting it right in {tries}!')
            self.reset()
        else:
            await ctx.send(f'{ctx.author.mention}: The Q20 game is not running here. '
                           f'Start a game by saying `{ctx.prefix}start`.',
                           delete_after=10)

    async def ask(self, ctx: commands.Context, question):
        if not self.running:
            if ctx.command:
                await ctx.send('Q20 is not running here.')
            return
        async with ctx.typing():
            message, res, valid = await self._parser.parse(question)
        if message in self._state:
            return await ctx.send('You\'ve already asked that!')
        await ctx.send(message)
        if not valid:
            return
        self._state.append(message)
        self.attempts -= 1
        self.add_player(ctx.author)
        if res:
            return await self.end(ctx)
        elif self.attempts == 0:
            return await self.end(ctx, failed=True)
        await self._message.edit(content=self)


class Q20Game(GameCogBase):
    gamecls = Q20GameObject

    def cog_check(self, ctx):
        return self._local_check(ctx)

    @commands.group(case_insensitive=True, aliases=['q'])
    async def q20(self, ctx):
        """Play Q20

        **Known issues**
        [`Steel is interpreted as Seel`](https://github.com/PikalaxALT/pikalaxbot/issues/7)
        """
        if ctx.invoked_subcommand is None:
            await ctx.send_help(self.q20)

    @q20.command()
    async def start(self, ctx):
        """Start a game in the current channel"""
        await self.game_cmd('start', ctx)

    @commands.command(name='q20start', aliases=['qst', 'start'])
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

    @commands.command(name='q20end', aliases=['qe', 'qend', 'end'])
    async def q20_end(self, ctx):
        """Abort the Q20 game early"""

        await self.end(ctx)

    @GameCogBase.listener()
    async def on_message(self, message):
        if message.author == self.bot.user:
            return
        if not self[message.channel.id].running:
            return
        ctx = await self.bot.get_context(message)
        if not ctx.prefix or ctx.valid:
            return
        content = message.content[len(ctx.prefix):]
        await self.ask(ctx, question=content)

    async def cog_command_error(self, ctx, error):
        await self._error(ctx, error)


def setup(bot):
    bot.add_cog(Q20Game(bot))
