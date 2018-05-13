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


def suppress_sql_error(func):
    def __call__(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except sqlite3.Error as e:
            log.error('SQL error: %s', traceback.format_exception(type(e), e, e.__traceback__))

    return __call__


@suppress_sql_error
def db_init():
    with sqlite3.connect(dbname) as conn:
        c = conn.execute('select exists(select bag from meme)')
        if not c.fetchone()[0]:
            c.execute('create table meme (bag text)')
            for line in default_bag:
                c.execute('insert into meme(bag) values (?)', line)

        c = conn.execute('select exists(select * from game)')
        if not c.fetchone()[0]:
            c.execute('create table game (id integer, name text, score integer)')


@suppress_sql_error
def get_score(ctx):
    with sqlite3.connect(dbname) as conn:
        c = conn.execute('select score from game where id = ? limit 1', ctx.author.id)
        return c.fetchone()[0]


@suppress_sql_error
def increment_score(ctx, by=1):
    with sqlite3.connect(dbname) as conn:
        c = conn.execute('select exists(select score from game where id = ?)', ctx.author.id)
        if c.fetchone()[0]:
            conn.executemany('update game set score = score + ? where id = ?', (by, ctx.author.id))
        else:
            conn.executemany('insert into game values (?, ?, ?)', (ctx.author.id, ctx.author.name, by))


@suppress_sql_error
def get_all_scores():
    with sqlite3.connect(dbname) as conn:
        yield from conn.execute('select * from game order by score desc limit 10')


@suppress_sql_error
def add_bag(text):
    with sqlite3.connect(dbname) as conn:
        c = conn.execute('select exists(select * from meme where bag = ?)', text)
        retrieved = c.fetchone()[0]
        if not retrieved:
            c.execute('insert into meme values (?)', text)
    return retrieved


@suppress_sql_error
def read_bag():
    with sqlite3.connect(dbname) as conn:
        c = conn.execute('select bag from meme order by random() limit 1')
        return c.fetchone()
