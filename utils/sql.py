import random
import sqlite3
from sqlite3 import Error

dbname = 'data/db.sql'
default_bag = (
    '{name} happily jumped into the bag!',
    '{name} reluctantly clambored into the bag.'
    '{name} turned away!',
    '{name} let out a cry in protest!'
)


def db_init():
    with sqlite3.connect(dbname) as conn:
        c = conn.execute('select * from meme(bag)')
        if c.rowcount == 0:
            c.execute('create table meme (bag text)')
            for line in default_bag:
                c.execute('insert into meme(bag) values (?)', line)

        c = conn.execute('select * from game')
        if c.rowcount == 0:
            c.execute('create table game (id integer, name text, score integer)')


def get_score(ctx):
    with sqlite3.connect(dbname) as conn:
        c = conn.execute('select score from game where id = ?', ctx.author.id)
        return c.fetchone()


def increment_score(ctx, by=1):
    score = get_score(ctx)
    with sqlite3.connect(dbname) as conn:
        if score is None:
            conn.executemany('insert into game values (?, ?, ?)', (ctx.author.id, ctx.author.name, by))
        else:
            conn.executemany('update game set score = ? where id = ?',
                         (score + by, ctx.author.id))


def get_all_scores():
    with sqlite3.connect(dbname) as conn:
        yield from conn.execute('select * from game')


def add_bag(text):
    with sqlite3.connect(dbname) as conn:
        c = conn.execute('select * from meme where bag = ?', text)
        retrieved = c.fetchone()
        if retrieved is None:
            c.execute('insert into meme values (?)', text)
    return retrieved is not None


def read_bag():
    with sqlite3.connect(dbname) as conn:
        c = conn.execute('select bag from meme')
        bag = c.fetchall()
    return random.choice(bag)
