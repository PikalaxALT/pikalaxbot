from typing import TypeVar
from .models import PokeapiResource, NamedPokeapiResource


__all__ = ('Model',)


Model = TypeVar("Model", PokeapiResource, NamedPokeapiResource)
