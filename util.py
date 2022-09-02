from typing import Iterable
import logging


def first(di: dict, default=None):
    try:
        return next(iter(di.items()))
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


