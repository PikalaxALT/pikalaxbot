# PikalaxBOT - A Discord bot in discord.py
# Copyright (C) 2018-2021  PikalaxALT
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import re
from sqlalchemy.ext.asyncio import create_async_engine, AsyncConnection
from sqlalchemy.orm import as_declarative, declared_attr


__all__ = ('BaseTable', 'async_engine_parameterized')


@as_declarative()
class BaseTable(object):
    @declared_attr
    def __tablename__(cls):
        return re.sub(r'([a-z])([A-Z])', r'\1_\2', cls.__name__).lower()

    @classmethod
    async def create(cls, connection: AsyncConnection):
        return await connection.run_sync(cls.__table__.create, checkfirst=True)

    @classmethod
    def unlink(cls):
        cls.metadata.remove(cls.__table__)


def get_database_url(*, username: str, password: str, host: str, port=5432, dbname: str):
    return f'postgresql+asyncpg://{username}:{password}@{host}:{port}/{dbname}'


def async_engine_parameterized(*, username: str, password: str, host: str, port=5432, dbname: str, **kwargs):
    url = get_database_url(username=username, password=password, host=host, port=port, dbname=dbname)
    return create_async_engine(url, **kwargs)
