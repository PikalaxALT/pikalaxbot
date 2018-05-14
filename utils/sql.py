import sqlite3

dbname = 'data/db.sql'
default_bag = (
    '{name} happily jumped into the bag!',
    '{name} reluctantly clambored into the bag.',
    '{name} turned away!',
    '{name} let out a cry in protest!'
)


def db_init():
    with sqlite3.connect(dbname) as conn:
        try:
            conn.execute('select exists(select * from meme)')
        except sqlite3.OperationalError:
            c = conn.execute('create table meme (bag text)')
            for line in default_bag:
                c.execute("insert into meme(bag) values ('?')", (line,))

        try:
            conn.execute('select exists(select * from game)')
        except sqlite3.OperationalError:
            conn.execute('create table game (id integer, name text, score integer)')


def get_score(ctx):
    with sqlite3.connect(dbname) as conn:
        try:
            c = conn.execute('select score from game where id = ? limit 1', (ctx.author.id,))
            return c.fetchone()[0]
        except sqlite3.OperationalError:
            return None


def increment_score(ctx, by=1):
    with sqlite3.connect(dbname) as conn:
        try:
            conn.executemany('update game set score = score + ? where id = ?', (by, ctx.author.id))
        except sqlite3.OperationalError:
            conn.executemany("insert into game values (?, '?', ?)", (ctx.author.id, ctx.author.name, by))


def get_all_scores():
    with sqlite3.connect(dbname) as conn:
        yield from conn.execute('select * from game order by score desc limit 10')


def add_bag(text):
    with sqlite3.connect(dbname) as conn:
        try:
            c = conn.execute('select exists(select * from meme where bag = ?)', (text,))
            return True
        except sqlite3.OperationalError:
            conn.execute("insert into meme(bag) values ('?')", (text,))
            return False


def read_bag():
    with sqlite3.connect(dbname) as conn:
        c = conn.execute('select bag from meme order by random() limit 1')
        return c.fetchone()
