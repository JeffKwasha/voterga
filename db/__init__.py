import re
from typing import List, Any, Iterable
from util import first, longest, logging


class Fields(dict):
    """ a list of names to be loaded from a source """
    def __init__(self, fields: Any = ()):
        """ create a 'fields' which is a dict of names that performs matching apart from the Name Class"""
        if isinstance(fields, dict):
            fields = list(Name(n.strip(), p) for n, p in fields.items())
        elif isinstance(fields, (set, list)):
            if all([isinstance(f, str) for f in fields]):
                fields = list(Name(f.strip()) for f in fields)
            elif all([type(f) is tuple and 0 < len(f) < 3 for f in fields]):
                fields = list(Name(*f) for f in fields)
        elif type(fields) is tuple:
            fields = Name(*fields) if 0 < len(fields) <= 2 else ()
        elif isinstance(fields, str):
            fields = [Name(fields.strip())]
        super().__init__()
        for name in fields:
            if name in self:
                raise ValueError(f"Collision initializing fields: {name} exists with patterns"
                                 f"{name.pattern}/{self[name].pattern}")
            self[name] = name

    def search(self, item, best_match: bool = True):
        if isinstance(item, str):
            item = item.strip()
            rv = super().get(item)
            if rv:
                return rv
            best = ''
            for k in self:
                if k == item:
                    if not best_match:
                        return k
                    elif len(k) > len(best):
                        best = k
            return super().__getitem__(best) if best else None
        elif type(item) is tuple:
            if len(item) <= 2:
                return self.search(item[0], best_match)
            raise ValueError("Search for an incompatible tuple")
        elif type(item) is dict:
            return self.search(first(item), best_match)
        return super().get(item)

    def __add__(self, other: Any):
        exists = self.search(other)
        if exists is not None:
            return exists
        rv = Fields(self)
        if isinstance(other, Name):
            rv[other] = other
        elif type(other) is tuple and len(other) == 2:
            rv[other[0]] = Name(*other)
        elif type(other) is dict and len(other) == 1:
            other = Name(*first(other))
            rv[other] = other
        else:
            ValueError(f"add hates you {other}")
        return rv

    def _get(self, other: Any, default=None):
        try:
            return super().get(other, default=default)
        except KeyError:
            pass
        return default

    def add(self, other: Any, value=None, best_match: bool = True):
        rv = self.search(other, best_match=best_match)
        if rv is not None:
            self[rv] = value
            return rv
        if not isinstance(other, Name):
            other = Name(other)
        super().__setitem__(other, value)
        return other

    def append(self, other, value=None, best_match: bool = True):
        return self.add(other, value, best_match)

    def build(self, item: str, obj: callable, *args, **kwargs):
        """ If item is not already present, call obj with args, kwargs and store/return the result """
        rv = self.search(item)
        if rv is not None:
            return rv
        self[item] = rv = obj(*args, **kwargs)
        return rv

    def __setitem__(self, item: str, value):
        if type(item) is str:
            item = Name.add(item)
        super().__setitem__(item, value)

    def __getitem__(self, item):
        rv = self.search(item, best_match=False)
        if rv is not None:
            return rv
        raise KeyError(repr(item))

    def __contains__(self, item):
        if super().__contains__(item):
            return True
        return bool(self.search(item, best_match=False))


class Name(str):
    """ Names of candidates, races, etc.. will not match exactly
    - trim spaces
    - recognize variations based on regex
    - use slots as this needs to act like a string
    """
    __slots__ = ['pattern']
    _all = Fields()

    @classmethod
    def add(cls, name: str, pattern: re.Pattern = None):
        """ searches for existing name match or create a Name if nothing matches """
        if type(name) is Name:
            raise ValueError(f"{name} is already a name")
        name = name.strip() if name else None
        rv = cls.search(name, best_match=True)
        if rv:
            return rv
        return Name(name, pattern=pattern)

    def __new__(cls, name: str, pattern: re.Pattern = None, flags: re.RegexFlag = re.IGNORECASE):
        """ create a name as long as the_exact_string doesn't already exist """
        name = name.strip() if type(name) is str else name
        rv = cls._all.get(name)
        if rv is not None:
            if pattern and not rv.pattern:
                rv.set_pattern(pattern)
            return rv
        return super().__new__(cls, name)

    def __init__(self, name: str, pattern: re.Pattern = None, flags: re.RegexFlag = re.IGNORECASE):
        self.pattern = pattern
        if name and type(pattern) is not re.Pattern:
            self.set_pattern(pattern, flags)
        self._all.add(self)

    def set_pattern(self, pattern: str or None, flags: re.RegexFlag = re.IGNORECASE):
        if pattern is None:
            pattern = fr'.*\b{str(self)}\b.*'
        self.pattern = re.compile(pattern, flags)

    def __eq__(self, other):
        if not isinstance(other, str):
            other = str(other)
        if super().__eq__(other):
            return True
        if self.pattern and self.pattern.fullmatch(other):
            return True
        return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        # hash the string. ignore the pattern
        return hash(str(self))

    @classmethod
    def search(cls, item, best_match: bool = True):
        return cls._all.search(item, best_match=best_match)

    def __class_getitem__(cls, item):
        return cls._all.search(item)

    def match(self, item, best_match: bool = True) -> re.Match or list:
        if isinstance(item, str):
            return self._match_str(item)
        matches = [hk for hk in item if self._match_str(item)]
        if not best_match:
            return matches
        return longest(matches)

    def _match_str(self, item) -> re.Match:
        if not self.pattern:
            return re.fullmatch(str(self), item)
        return self.pattern.fullmatch(item)

    def fullmatch(self, item) -> re.Match:
        if self.pattern:
            return self.pattern.fullmatch(item)

    def __repr__(self):
        return str(self)

    def pop_pattern(self, haystack: Iterable):
        """ find and remove self from haystack return whatever was removed
         ex: (dict) haystack.pop(self, None) """
        if isinstance(haystack, dict):
            val = haystack.pop(self, None)
            if val is None:
                key = longest([hk for hk in haystack.keys() if self.match(hk)])
                val = haystack.pop(key, None)
            return val
        elif isinstance(haystack, (tuple, list)):
            i = haystack.index(self)
            if i >= 0:
                return haystack.pop(i)
            longest([hk for hk in haystack if self.match(hk)])
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
