""" County - a class that handles looking up counties and municipalities and...

County[ID] - flexible names or pre-2023 numbers (Enumerated in alphabetical order)
County.from_muni("atlanta") -> {"Fulton", "Dekalb"}

"""

import re
from typing import Iterable
from pathlib import Path
from os import getcwd
from db.tab import guess_separator
from common import Fields
import polars as pl
import logging

from common import Name
CWD = Path(getcwd()).expanduser().resolve()
LOG = logging.root


class County:
    _counties = Fields(key='GA_Counties')
    _municipalities = Fields(key='GA_municipalities')
    _need_reindex = True
    PATH = Path('./GA 2020 county.csv')

    def __init__(self, name: str, municipalities: list | str, population: dict[int, int] = None):
        self.name = Name(name.strip().title(), pattern=re.compile(rf"{name}[ \t]*(county)?", re.I)) if not isinstance(name, Name) else name
        self.index = None
        self.munis = []
        self.population = {}

        self.add_munis(municipalities)
        self.add_pop(population)

        County.add_county(self)

    @classmethod
    def add_county(cls, county: 'County', reindex=False) -> bool:
        if county.name in cls._counties:
            return False
        cls._counties[county.name] = county
        cls._need_reindex = True
        if reindex:
            cls.reindex()

    @classmethod
    def reindex(cls):
        if not cls._need_reindex:
            return
        tmp = set(cls._counties.values())
        tmp = sorted(tmp)
        cls._counties.clear()
        for n, c in enumerate(tmp, 1):
            c.index = n
            cls._counties[c.name] = c
            cls._counties[c.index] = c
        cls._need_reindex = False

    @classmethod
    def load(cls, file: Path = PATH):
        if not file.is_absolute():
            file = CWD.joinpath(file)
        df = pl.read_csv(file, separator=guess_separator(file))

        # RE_CLEAN = re.compile(r'[A-Za-z 0-9]*', re.I)
        RE_SPLIT = re.compile(r',\s*')
        def add_counties(t) -> None:
            muni = t[0]
            county = t[1]
            for name in RE_SPLIT.split(county):
                if cls.has(name):
                    c = cls[name]
                    c.add_munis([muni])
                    continue
                cls(name, [muni])
            return 0    # it will built a df out of these return vals, so they have to exist :/

        df.map_rows(add_counties)
        cls.reindex()

    def __hash__(self):
        return hash(self.name)

    def __lt__(self, other):
        if type(other) is int:
            return self.index < other
        if type(other) is str:
            return self.name < other.lower()
        return self.name < other

    def __le__(self, other):
        if type(other) is int:
            return self.index <= other
        if type(other) is str:
            return self.name <= other.lower()
        return self.name <= other

    def __eq__(self, other):
        if type(other) is int:
            return self.index == other
        if type(other) is str:
            return self.name == other.lower()
        return self.name == other

    def __gt__(self, other):
        if type(other) is int:
            return self.index > other
        if type(other) is str:
            return self.name > other.lower()
        return self.name > other

    def __ge__(self, other):
        if type(other) is int:
            return self.index >= other
        if type(other) is str:
            return self.name >= other.lower()
        return self.name >= other

    def __repr__(self):
        return f"{self.index}:{self.name} {self.munis}"

    def __str__(self):
        return self.name

    def __del__(self):
        for m in self.munis:
            if counties := County._municipalities.get(m, set()):
                if self in counties:
                    counties.remove(self)

    def add_munis(self, munis: list | str) -> int:
        if not munis:
            return 0
        if isinstance(munis, str):
            sep = guess_separator(munis)
            munis = munis.split(sep)
        if isinstance(munis, Iterable):
            for name in munis:
                if not isinstance(name, Name):
                    name = Name(name.strip().title(), pattern=re.compile(rf"{name}[ \t]*(city)?", re.I))
                if name not in self.munis:
                    self.munis.append(name)

        for n, m in enumerate(self.munis):
            counties_for_m = self.__class__._municipalities.setdefault(m, set())
            # clean out any_old_county == self
            if self in counties_for_m:
                LOG.info(f'removing {self}')
                counties_for_m.remove(self)
            # add self to County muni dict
            counties_for_m.add(self)
        return len(self.munis)

    def add_pop(self, population: dict[int, int]):
        if population:
            self.population.update(population)

    @classmethod
    def all(cls):
        return cls._counties

    @classmethod
    def find_muni(cls, item: str) -> set | None:
        try:
            return cls._municipalities[item]
        except KeyError:
            pass

    @classmethod
    def has(cls, item) -> bool:
        if item in cls._counties:
            return True
        return False

    @classmethod
    def __class_getitem__(cls, item):
        return cls._counties[item]

