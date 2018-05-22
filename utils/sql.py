import os
import sqlite3

dbname = 'data/db.sql'
default_bag = (
    'happily jumped into the bag!',
    'reluctantly clambored into the bag.',
    'turned away!',
    'let out a cry in protest!'
)


def db_init():
    os.makedirs(os.path.dirname(dbname), exist_ok=True)
    with sqlite3.connect(dbname) as conn:
        try:
            conn.execute('select * from meme')
        except sqlite3.OperationalError:
            c = conn.execute('create table meme (bag text)')
            for line in default_bag:
                c.execute("insert into meme(bag) values (?)", (line,))

        try:
            conn.execute('select * from game')
        except sqlite3.OperationalError:
            conn.execute('create table game (id integer, name text, score integer)')

        try:
            conn.execute('select * from voltorb')
        except sqlite3.OperationalError:
            conn.execute('create table voltorb (id integer, level integer)')


def db_clear():
    os.makedirs(os.path.dirname(dbname), exist_ok=True)
    with sqlite3.connect(dbname) as conn:
        try:
            conn.execute("drop table meme")
        except sqlite3.Error:
            pass
        try:
            conn.execute("drop table game")
        except sqlite3.Error:
            pass


def get_score(author):
    with sqlite3.connect(dbname) as conn:
        c = conn.execute('select score from game where id = ? limit 1', (author.id,))
        score = c.fetchone()
        if hasattr(score, '__getitem__'):
            score = score[0]
        return score


def increment_score(ctx, by=1):
    with sqlite3.connect(dbname) as conn:
        c = conn.execute("select score from game where id = ?", (ctx.author.id,))
        score = c.fetchone()
        if score is None:
            conn.execute("insert into game values (?, ?, ?)", (ctx.author.id, ctx.author.name, by))
        else:
            conn.execute('update game set score = score + ? where id = ?', (by, ctx.author.id))


def get_all_scores():
    with sqlite3.connect(dbname) as conn:
        yield from conn.execute('select * from game order by score desc limit 10')


def add_bag(text):
    with sqlite3.connect(dbname) as conn:
        c = conn.execute('select * from meme where bag = ?', (text,))
        res = c.fetchone() is None
        if res:
            conn.execute("insert into meme(bag) values (?)", (text,))
        return res


def read_bag():
    with sqlite3.connect(dbname) as conn:
        c = conn.execute('select bag from meme order by random() limit 1')
        msg = c.fetchone()
    if msg is not None:
        return msg[0]


def get_voltorb_level(ctx):
    with sqlite3.connect(dbname) as conn:
        c = conn.execute('select level from voltorb where id = ?', (ctx.channel.id,))
        level = c.fetchone()
        if level is None:
            conn.execute('insert into voltorb values (?, 1)', (ctx.channel.id,))
            level = 1
        else:
            level, = level
    return level


def set_voltorb_level(ctx, new_level):
    with sqlite3.connect(dbname) as conn:
        c = conn.execute('select level from voltorb where id = ? limit 1', (ctx.channel.id,))
        level = c.fetchone()
        if level is None:
            conn.execute('insert into voltorb values (?, ?)', (ctx.channel.id, new_level))
        else:
            conn.execute('update voltorb set level = ? where id = ?', (new_level, ctx.channel.id))
