import sqlite3
from bot import log
import traceback

dbname = 'data/db.sql'
default_bag = (
    '{name} happily jumped into the bag!',
    '{name} reluctantly clambored into the bag.',
    '{name} turned away!',
    '{name} let out a cry in protest!'
)


def safe_call(func):
    def __call__(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except sqlite3.Error as e:
            log.error('SQL error: %s', traceback.format_exception(type(e), e, e.__traceback__))

    return __call__


@safe_call
def db_init():
    with sqlite3.connect(dbname) as conn:
        c = conn.execute('select exists(select bag from meme)')
        if not c.fetchone():
            c.execute('create table meme (bag text)')
            for line in default_bag:
                c.execute('insert into meme(bag) values (?)', line)

        c = conn.execute('select exists(select * from game)')
        if not c.fetchone():
            c.execute('create table game (id integer, name text, score integer)')


@safe_call
def get_score(ctx):
    with sqlite3.connect(dbname) as conn:
        c = conn.execute('select score from game where id = ? limit 1', ctx.author.id)
        return c.fetchone()


@safe_call
def increment_score(ctx, by=1):
    score = get_score(ctx)
    with sqlite3.connect(dbname) as conn:
        if score is None:
            conn.executemany('insert into game values (?, ?, ?)', (ctx.author.id, ctx.author.name, by))
        else:
            conn.executemany('update game set score = ? where id = ?',
                         (score + by, ctx.author.id))


@safe_call
def get_all_scores():
    with sqlite3.connect(dbname) as conn:
        yield from conn.execute('select * from game order by score desc limit 10')


@safe_call
def add_bag(text):
    with sqlite3.connect(dbname) as conn:
        c = conn.execute('select exists(select * from meme where bag = ?)', text)
        retrieved = c.fetchone()
        if not retrieved:
            c.execute('insert into meme values (?)', text)
    return retrieved


@safe_call
def read_bag():
    with sqlite3.connect(dbname) as conn:
        c = conn.execute('select bag from meme order by random() limit 1')
        return c.fetchone()
