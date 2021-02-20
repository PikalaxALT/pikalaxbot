import sqlite3
import contextlib
import typing
import re
import collections
import asyncio
import difflib
import aiosqlite
import discord
import inflect
import functools
from ..context import MyContext
from discord.ext import commands


__all__ = ('PokeapiModel',)

_T = typing.TypeVar('_T')
_R = typing.TypeVar('_R')

_garbage_pat = re.compile(r'[. \t-\'"]')
DICTIONARY = [
    'characteristic', 'description', 'preference', 'pokeathlon', 'generation', 'experience', 'evolution', 'encounter',
    'condition', 'attribute', 'location', 'language', 'efficacy', 'category', 'version', 'trigger', 'sprites',
    'species', 'pokemon', 'pokedex', 'machine', 'habitat', 'contest', 'ailment', 'ability', 'target', 'region',
    'pocket', 'number', 'nature', 'method', 'growth', 'gender', 'flavor', 'effect', 'damage', 'change', 'battle',
    'super', 'style', 'shape', 'learn', 'index', 'group', 'fling', 'combo', 'color', 'class', 'chain', 'berry', 'type',
    'text', 'stat', 'slot', 'rate', 'park', 'name', 'move', 'meta', 'item', 'game', 'form', 'area', 'pal', 'map',
    'egg', 'dex'
]
pluralizer = inflect.engine()
_prep_lock = asyncio.Lock()


def tblname_to_classname(name: str):
    name = name[11:]
    for word in DICTIONARY:
        name = name.replace(word, '_' + word.upper())
    return name.title().replace('_', '')


def sqlite3_type(coltype: str) -> type:
    if coltype.startswith('varchar'):
        return str
    return {
        'integer': int,
        'real': float,
        'text': str,
        'bool': bool
    }.get(coltype)


RowFactory = typing.Callable[[sqlite3.Cursor, tuple], typing.Any]


class collection(list[_T]):
    def get(self, **attrs) -> typing.Optional[_T]:
        return discord.utils.get(self, **attrs)


class relationship:
    def __init__(self, target: str, local_col: str, foreign_col: str, attrname: str):
        self.target = target
        self.local_col = local_col
        self.foreign_col = foreign_col
        self.attrname = attrname

    def __get__(self, instance: typing.Optional['PokeapiModel'], owner: typing.Optional[typing.Type['PokeapiModel']]):
        if instance is None:
            return self
        target_cls: typing.Type['PokeapiModel'] = getattr(instance.classes, tblname_to_classname(self.target))
        fk_id = getattr(instance, self.local_col)
        result = PokeapiModel.__cache__.get((target_cls, fk_id))
        if result is None:
            cursor = instance.connection.execute(
                'select * '
                'from "{}" '
                'where {} = ?'.format(self.target, self.foreign_col),
                (fk_id,)
            )
            result = target_cls(cursor, cursor.fetchone())
        return result


class backref:
    def __init__(self, target: str, local_col: str, foreign_col: str, attrname: str):
        self.target = target
        self.local_col = local_col
        self.foreign_col = foreign_col
        self.attrname = attrname

    def __get__(self, instance: typing.Optional['PokeapiModel'], owner: typing.Optional[typing.Type['PokeapiModel']]):
        if instance is None:
            return self
        target_cls: typing.Type['PokeapiModel'] = getattr(instance.classes, tblname_to_classname(self.target))
        cursor = instance.connection.execute(
            'select * '
            'from "{}" '
            'where {} = ?'.format(self.target, self.foreign_col),
            (getattr(instance, self.local_col),)
        )
        result = collection(target_cls.from_row(cursor, row) for row in cursor.fetchall())
        setattr(instance, self.attrname, result)
        return result


def name_for_scalar_relationship(
        local_cls: typing.Type['PokeapiModel'],
        dest_cls: typing.Type['PokeapiModel'],
        local_col: str,
        dest_col: str,
        constraints: typing.Iterable[sqlite3.Row]
):
    return local_col[:-3]


def name_for_collection_relationship(
        local_cls: typing.Type['PokeapiModel'],
        dest_cls: typing.Type['PokeapiModel'],
        local_col: str,
        dest_col: str,
        constraints: typing.Iterable[sqlite3.Row]
):
    if local_cls is dest_cls:
        return 'evolves_into_species'
    parts = re.findall(r'[A-Z][a-z]+', dest_cls.__name__)
    parts[-1] = pluralizer.plural(parts[-1])
    name = '_'.join(parts).lower()
    ambiguities = collections.Counter(constraint[2] for constraint in constraints)
    if ambiguities[local_cls.__tablename__] > 1:
        name += '__' + dest_col[:-3]
    return name


class classproperty:
    def __init__(self, func: typing.Callable[[type], _R]):
        self._func = func

    def __get__(self, instance: typing.Optional[_T], owner: typing.Optional[typing.Type[_T]]):
        if owner is None:
            owner = type(instance)
        return self._func(owner)


@functools.total_ordering
class PokeapiModel:
    __abstract__ = True
    __columns__: dict[str, type] = {}
    __cache__: dict[tuple[typing.Type['PokeapiModel'], int], 'PokeapiModel'] = {}
    __prepared__ = False
    classes = None

    @classproperty
    def __tablename__(cls):
        return 'pokemon_v2_' + cls.__name__.lower()

    @classmethod
    def from_row(cls, cursor: sqlite3.Cursor, row: typing.Optional[tuple]) -> typing.Optional['PokeapiModel']:
        if row is None:
            return
        return cls.__cache__.get((cls, row[0])) or cls(cursor, row)

    def __init__(self, cursor: sqlite3.Cursor, row: tuple):
        if self.__abstract__:
            raise TypeError('trying to instantiate an abstract base class')
        self.__class__.__cache__[(self.__class__, row[0])] = self
        self.connection: sqlite3.Connection = cursor.connection
        for (colname, *_), value in zip(cursor.description, row):
            setattr(self, colname, value)
        # for key, value in self.__class__.__dict__.items():
        #     if isinstance(value, (relationship, backref)):
        #         getattr(self, key)
        try:
            self.qualified_name
        except AttributeError:
            pass

    def __iter__(self):
        for column in self.__columns__:
            yield column, getattr(self, column)

    @classmethod
    async def _prepare(cls, connection: aiosqlite.Connection):
        classes: dict[str, typing.Type['PokeapiModel']] = {}
        tbl_names = [x async for x, in await connection.execute(
            "select tbl_name "
            "from sqlite_master "
            "where type = 'table' "
            "and tbl_name like 'pokemon_v2_%'"
        )]
        for tbl_name in tbl_names:
            cls_name = tblname_to_classname(tbl_name)
            colspec: dict[str, type] = {
                colname: sqlite3_type(coltype)
                async for cid, colname, coltype, notnull, dflt, pk in await connection.execute(
                        'pragma table_info ("{}")'.format(tbl_name)
                )
            }

            table_cls = type(
                cls_name,
                (cls,),
                {
                    '__abstract__': False,
                    '__columns__': colspec
                }
            )
            classes[cls_name] = table_cls
        for tbl_name in tbl_names:
            cls_name = tblname_to_classname(tbl_name)
            table_cls = classes[cls_name]
            foreign_keys = await connection.execute_fetchall(
                'pragma foreign_key_list ("{}")'.format(tbl_name)
            )
            for id_, seq, dest, local_col, dest_col, on_update, on_delete, match in foreign_keys:
                dest_cls_name = tblname_to_classname(dest)
                dest_cls = classes[dest_cls_name]
                manytoonekey = name_for_scalar_relationship(
                    table_cls,
                    dest_cls,
                    local_col,
                    dest_col,
                    foreign_keys
                )
                onetomanykey = name_for_collection_relationship(
                    dest_cls,
                    table_cls,
                    dest_col,
                    local_col,
                    foreign_keys
                )

                setattr(table_cls, manytoonekey, relationship(dest, local_col, dest_col, manytoonekey))
                setattr(dest_cls, onetomanykey, backref(tbl_name, dest_col, local_col, onetomanykey))
        cls.classes = type('Base', (object,), classes)

    @classmethod
    async def prepare(cls, connection: aiosqlite.Connection):
        if not cls.__prepared__:
            async with _prep_lock:
                if not cls.__prepared__:
                    await cls._prepare(connection)
                    cls.__prepared__ = True

        differ = difflib.SequenceMatcher(lambda s: _garbage_pat.match(s) is not None)

        def fuzzy_ratio(a, b):
            differ.set_seqs(a, b)
            return differ.ratio()

        await connection.create_function(
            'FUZZY_RATIO',
            2,
            fuzzy_ratio
        )

    @classmethod
    async def get(
            cls: typing.Type[_T],
            connection: aiosqlite.Connection,
            id_: int
    ) -> typing.Optional[_T]:
        async with connection.execute(
            'select * '
            'from {} '
            'where id = ?'.format(cls.__tablename__),
            (id_,)
        ) as cur:
            return cls.from_row(cur, await cur.fetchone())

    @classmethod
    async def get_random(
            cls: typing.Type[_T],
            connection: aiosqlite.Connection
    ) -> _T:
        async with connection.execute(
            'select * '
            'from {} '
            'order by random()'.format(cls.__tablename__)
        ) as cur:
            return cls.from_row(cur, await cur.fetchone())

    @property
    def qualified_name(self):
        if self.__class__.__name__ == 'Language':
            attrs = {'local_language_id': 9}
            collection_name = 'language_names__language'
        else:
            attrs = {'language_id': 9}
            collection_name = re.sub(r'([a-z])([A-Z])', r'\1_\2', self.__class__.__name__).lower() + '_names'
        names = getattr(self, collection_name)
        return discord.utils.get(names, **attrs).name

    @classmethod
    async def get_named(
            cls: typing.Type[_T],
            conn: aiosqlite.Connection,
            name: str,
            *,
            cutoff=0.9
    ) -> typing.Optional[_T]:
        name_cls = getattr(cls.classes, cls.__name__ + 'Name')
        fk_name = re.sub(r'([a-z])([A-Z])', r'\1_\2', cls.__name__).lower() + '_id'
        select = 'SELECT * FROM {0} INNER JOIN {1} ON {0}.id = {1}.{2}'
        fuzzy_clause = 'FUZZY_RATIO({1}.name, :name) > :cutoff'
        if hasattr(cls, 'name'):
            fuzzy_clause += ' OR FUZZY_RATIO({0}.name, :name) > :cutoff'
        lang_attr_name = 'local_language_id' if cls.__name__ == 'Language' else 'language_id'
        lang_clause = '{1}.{3} = 9'
        statement = f'{select} WHERE {lang_clause} AND ({fuzzy_clause})'.format(cls.__tablename__, name_cls.__tablename__, fk_name, lang_attr_name)
        async with conn.execute(statement, dict(name=name, cutoff=cutoff)) as cur:
            return cls.from_row(cur, await cur.fetchone())

    @classmethod
    async def convert(
            cls: typing.Type[_T],
            ctx: MyContext,
            argument: str
    ) -> _T:
        conn: aiosqlite.Connection = ctx.bot.pokeapi
        try:
            argument = int(argument)
        except ValueError:
            methd = cls.get_named
        else:
            methd = cls.get
        try:
            obj = await methd(conn, argument)
            assert obj is not None
        except Exception as e:
            raise commands.BadArgument(f'Failed to convert value "{argument}" into {cls.__name__}') from e
        return obj

    def __str__(self):
        try:
            return self.qualified_name
        except AttributeError:
            return '<{0.__class__.__name__} id={0.id}>'.format(self)

    def __repr__(self):
        try:
            return '<{0.__class__.__name__} id={0.id} name={0.qualified_name}>'.format(self)
        except AttributeError:
            return '<{0.__class__.__name__} id={0.id}>'.format(self)

    def __eq__(self, other):
        try:
            return self.__class__ is other.__class__ and self.id == other.id
        except AttributeError:
            return False

    def __lt__(self, other):
        if self.__class__ is other.__class__:
            return self.id < other.id
        return NotImplemented

    def __hash__(self):
        return hash((self.__class__, self.id))
