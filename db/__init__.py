""" Objects for representing data:
"""

import re
import yaml
from pathlib import Path
from typing import Any, Iterable
from util import first, longest, LogSelf, dict_sum, dict_diff
from collections import namedtuple

SearchResult = namedtuple('SearchResult', field_names=('name', 'value'), defaults=(None, None))
SearchResult.__bool__ = lambda t: bool(t[0])
NOT_FOUND = SearchResult('', None)


class Fields(dict):
    """ a Dictionary that uses Name for keys instead of str
    ex: print(Fields({Name('Joe Biden', r'.*\b(brandon|biden)\b.*'): 'y.k.t.t.' })['biden'] == 'y.k.t.t.')
    """
    _all: 'Fields' = None

    def __init__(self, fields: Any = (), key: str = None, filename: Path or str = None):
        """ create a 'fields' dict with Names for keys, allowing field['string'] to return as if field['THE_STRING']
            keys can be non strings - especially tuples, but lookups of non-string keys require exact matches
        """
        super().__init__()
        self.name = key
        self.add_all(fields)
        if filename:
            if type(filename) is not Path:
                filename = Path(filename).expanduser()
            with open(filename, 'r') as f:
                self.add_all(yaml.safe_load(f))
        if not key:
            return
        if Fields._all is None:
            Fields._all = Fields()
        if key in Fields._all:
            raise NameError(f"Collision with existing Fields")
        Fields._all[key] = self

    def search(self, key, best_match: bool = True) -> SearchResult:
        best = NOT_FOUND
        if isinstance(key, str):
            key = key.strip()
            for k, v in self.items():
                if k == key:
                    if len(k) > len(best[0]):
                        best = SearchResult(k, v)
                    if not best_match:
                        break
            return best
        elif type(key) is re.Pattern:
            for k, v in self.items():
                if key.match(str(k)):
                    if not best_match:
                        return v
                    elif len(k) > len(best[0]):
                        best = SearchResult(k, v)
            return best
        elif type(key) is dict:
            return self.search(first(key), best_match)
        else:
            v = super().get(key, NOT_FOUND)
            if v:
                return key, v
        return NOT_FOUND

    def __add__(self, other: Any):
        # Fields() + Fields() returns a new combined Fields
        exists = self.search(other)
        if exists:
            return exists[0]
        rv = Fields(key=None, fields=self)
        if isinstance(other, Name):
            rv[other] = None
        elif type(other) is tuple and len(other) == 2:
            rv[Name(*other)] = None
        elif type(other) is dict:
            if 'pattern' in other:
                rv[Name(**other)] = None
            else:
                rv.add_all(other)
        else:
            ValueError(f"add hates you {other}")
        return rv

    def add_all(self, fields) -> int:
        if isinstance(fields, str):
            fields = [fields]
        elif isinstance(fields, dict):
            for k, v in fields.items():
                self.add(key=k, value=v)
            return len(fields)
        for f in fields:
            if isinstance(f, dict):
                self.add(**f)
            elif isinstance(f, str):
                self.add(key=f)
            elif isinstance(f, (tuple, list)):
                self.add(*f)
        return len(fields)

    def _get(self, other: Any, default=None):
        try:
            return super().get(other, default=default)
        except KeyError:
            pass
        return default

    def add(self, key: Any, value=None, pattern: re.Pattern or str = '', best_match: bool = True) -> 'Name':
        rv = self.search(key, best_match=best_match)
        if not rv:
            rv = (key, rv[1]) if isinstance(key, Name) or type(key) is tuple else (Name(key, pattern), None)
        super().__setitem__(rv[0], value if value is not None else rv[1])
        return rv[0]

    def append(self, key, value=None, pattern: re.Pattern or str = '', best_match: bool = True):
        return self.add(key, value, pattern, best_match=best_match)

    def build(self, name: str, obj: callable, *args, **kwargs):
        """ If name is not already present, call obj with args, kwargs and store/return the result """
        rv = self.search(name)[1]
        if rv is not None:
            return rv
        self[name] = rv = obj(*args, **kwargs)
        return rv

    def __setitem__(self, item: str, value):
        if type(item) is str:
            item = Name.add(item)
        super().__setitem__(item, value)

    def __getitem__(self, item):
        try:
            rv = super().__getitem__(item)
            return rv
        except KeyError:
            pass
        rv = self.search(item, best_match=False)
        if rv is not None:
            return rv[1]
        raise KeyError(repr(item))

    def __contains__(self, item):
        if super().__contains__(item):
            return True
        return bool(self.search(item, best_match=False)[0])

    def __class_getitem__(cls, item: str) -> 'Fields':
        if not item:
            raise ValueError(f"{item} isn't valid")
        rv = Fields._all.search(item)
        if rv:
            return rv[1]
        return Fields(key=item)


class Name(str):
    """ A magic string that compares based on a regex
    Names of candidates, races, etc.. will not match exactly
    - trim spaces
    - recognize variations based on regex
    - use slots as this needs to act like a string

    print(Name('Trump') == 'Donald Trump')
    """
    __slots__ = ['_pattern']
    _all = Fields()

    @classmethod
    def add(cls, name: str or tuple, pattern: re.Pattern = None):
        """ searches for existing name match or create a Name if nothing matches """
        if type(name) is tuple:   ## and all(type(n) is Name for n in name):
            return name
        if type(name) is Name:
            raise ValueError(f"{name} is already a name")
        name = name.strip() if name else None
        rv = cls.search(name, best_match=True)
        if rv:
            return rv
        rv = Name(name, pattern=pattern)
        cls._all[rv] = None
        return rv

    def __new__(cls, name: str, pattern: re.Pattern = None, flags: re.RegexFlag = re.IGNORECASE):
        """ create a name as long as the_exact_string doesn't already exist """
        name = name.strip() if type(name) is str else name
        rv = cls._all.get(name)
        if rv is not None:
            if pattern:
                rv.set_pattern(pattern)
            return rv
        return super().__new__(cls, name)

    def __init__(self, name: str, pattern: str or re.Pattern = '', flags: re.RegexFlag = re.IGNORECASE):
        self.set_pattern(pattern, flags)

    def set_pattern(self, pattern: str or None, flags: re.RegexFlag = re.IGNORECASE):
        if pattern is None:
            self._pattern = pattern             # None is allowed: it prevents fancy matching
            return
        if not pattern:                         # other False values get the default pattern
            pattern = fr'.*\b{str(self)}\b.*'
        self._pattern = pattern if type(pattern) is re.Pattern else re.compile(pattern, flags)

    def __eq__(self, other: str) -> bool:
        other = str(other)
        if other == str(self):
            return True
        if not self._pattern:
            return False
        return bool(self._pattern.fullmatch(other))

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        # hash the string. ignore the pattern
        return hash(str(self))

    @classmethod
    def search(cls, item, best_match: bool = True) -> ('Name', Any):
        return cls._all.search(item, best_match=best_match)

    def __class_getitem__(cls, item) -> Any:
        return cls._all.search(item)[1]

    def match(self, item) -> re.Match:
        return self._pattern.fullmatch(str(item))

    def _match_str(self, item: str) -> re.Match:
        return self._pattern.fullmatch(item)

    def __repr__(self):
        return str(self)

    def pop_pattern(self, haystack: Iterable):
        """ find and remove self from haystack return whatever was removed
         ex: (dict) haystack.pop(self, None) """
        if isinstance(haystack, dict):
            val = haystack.pop(self, None)
            if val is None:
                key = longest([hk for hk in haystack.keys() if self == hk])
                val = haystack.pop(key, None)
            return val
        elif isinstance(haystack, (tuple, list)):
            i = haystack.index(self)
            if i >= 0:
                return haystack.pop(i)
            longest([hk for hk in haystack if self == hk])
        elif isinstance(haystack, set):
            if self in haystack:
                haystack.remove(self)
                return self
            return None

    def find_pattern(self, haystack: Iterable):
        if isinstance(haystack, dict):
            val = haystack.get(self, None)
            if val is None:
                val = haystack.get(str(self), None)
            return val
        elif isinstance(haystack, (tuple, list)):
            i = haystack.index(self)
            return haystack.pop(i) if i >= 0 else None
        elif isinstance(haystack, set):
            if self in haystack:
                haystack.remove(self)
                return self
            return None


if __name__ == "__main__":
    import timeit
    print('main')
