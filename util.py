from typing import Iterable, NamedTuple, Callable
from datetime import datetime
from pytz import utc
from pathlib import Path
import re
import logging
from logging import INFO

# data path should contain a year (1900 <= even years <= 2098)  and county ex: /foo/bar/2020/fulton/data
_data_path_re = re.compile(str(Path('').joinpath('.*', r'(?P<year>(19|20)\d[02468])', r'(?P<county>\w+)', '.*')), re.I)


def now() -> datetime:
    return datetime.now(utc).replace(microsecond=0)


class ErrorKey(NamedTuple):
    level: int = INFO         # report_level
    why: str = None         # reason (missing, mismatch, junk)
    what: str = None        # object (race, precinct, tabulator...)
    when: datetime = None   # time of the error occurred
    who: str = None         # source / file / data path ...


def parse_path(p: Path):
    """ :returns {'year': str, 'county': str} """
    global _data_path_re
    path = str(p.absolute())
    m = _data_path_re.match(f"{path}/")     # regex requires a minimum one slash
    if m:
        return m.groupdict()


def first(di: Iterable, default=None):
    try:
        if isinstance(di, dict):
            return next(iter(di.items()))
        return next(iter(di))
    except StopIteration:
        pass
    return default


def longest(li: Iterable, default=None) -> str or None:
    # li can be any Iterable that supports len()
    long = ''
    for i in li:
        if len(i) > len(long):
            long = i
    return long or default


def pop_pattern(haystack, pattern: str, ignore_case=True, default=None):
    p = re.compile(pattern, flags=(ignore_case and re.I)) if type(pattern) is not re.Pattern else pattern
    for key in haystack:
        if p.match(key):
            return haystack.pop(key)
    return default


def dict_sum(a: dict, b: dict, modify: bool or dict = True) -> dict:
    _sum = a
    if not modify:
        _sum = a.copy()
    elif isinstance(modify, dict):
        _sum = modify
    for k, v in b.items():
        if k in _sum:
            _sum[k] = _sum[k] + v
        else:
            _sum[k] = v
    return _sum


def dict_diff(a: dict, b: dict) -> dict:
    diff = a.copy()
    for k, v in b.items():
        if k in diff:
            diff[k] = diff[k] - v
        else:
            diff[k] = v
    return diff


def deep_set(di: dict, keys: tuple, value, dict_type: Callable = dict):
    for n, k in enumerate(keys):
        if n == len(keys) - 1:
            di[k] = value
            return value
        if k not in di or not isinstance(di[k], dict):
            di[k] = dict_type()
        di = di[k]
    return None


def deep_tally(di: dict, keys: tuple):
    if not isinstance(di, dict):
        return di
    for n, k in enumerate(keys):
        if k is None:
            return sum([deep_tally(di[_key], keys[n + 1:]) for _key in di])
        if k not in di:
            return 0
        if n == len(keys) - 1:
            di = di[k]
            return di if not isinstance(di, dict) else deep_tally(di, (None,))
        di = di[k]
    return 0


class LogSelf:
    ERROR = logging.ERROR
    WARN  = logging.WARN
    INFO = logging.INFO
    DEBUG = logging.DEBUG
    EXCEPTION = -1
    _classes = set()
    _errors = {}    # and it will stay empty

    def __init_subclass__(cls, **kwargs):
        cls._errors = {}    # set(errors) by (level, category)
        LogSelf._classes.add(cls)

    @property
    def log_name(self):
        return self.__class__.__name__

    @classmethod
    def all_errors(cls, report_level: int):
        rv = {}
        for _class in LogSelf._classes:
            rv.update(_class.errors(report_level))
        keys = sorted(rv, reverse=True)
        # TODO
        return keys

    @classmethod
    def errors(cls, report_level: int) -> dict:
        rv = {}
        for k in filter(lambda t: t.level >= report_level, cls._errors):
            rv.setdefault(k, set()).update(cls._errors.get(k))
        return rv

    def log(self, msg, *args, what: str = None, why: str = None, level: int = logging.INFO,
            when: datetime = None, who: str = None, **kwargs):
        who = self.__class__.__name__ if who is None else who
        key = ErrorKey(level=level, what=what, why=why, when=when, who=who)
        errors = self._errors.setdefault(key, set())
        errors.add(msg)

        if level == self.ERROR:
            fn = logging.error
        elif level == self.WARN:
            fn = logging.warning
        elif level == self.INFO:
            fn = logging.info
        elif level == self.DEBUG:
            fn = logging.debug
        elif level <= self.EXCEPTION:
            fn = logging.exception
        else:
            fn = logging.log
            kwargs['level'] = level

        fn(msg=msg, *args, **kwargs)

    def error(self, msg, *args, what: str = None, why: str = None,
              when: datetime = None, who: str = None, **kwargs):
        self.log(msg, level=logging.ERROR, *args, what=what, when=when, who=who, why=why, **kwargs)

    def warning(self, msg, *args, what: str = None, why: str = None,
                when: datetime = None, who: str = None, **kwargs):
        self.log(msg, level=logging.WARN, *args, what=what, when=when, who=who, why=why, **kwargs)

