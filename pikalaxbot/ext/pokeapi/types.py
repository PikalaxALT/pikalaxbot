from typing import Type, TypeVar, Union, Callable
from sqlite3 import Cursor
from .models import PokeapiResource, NamedPokeapiResource


__all__ = ('Model', 'ModelType', 'T', 'RowFactory')


T = TypeVar('T')
Model = TypeVar("Model", PokeapiResource, NamedPokeapiResource)
ModelType = Type[Model]
RowFactory = Union['ModelType', Callable[[Cursor, tuple], ...]]

