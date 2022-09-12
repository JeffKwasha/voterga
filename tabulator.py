import re
from typing import Iterable
from db import Name, Fields
from pathlib import Path
from db.xls import Xlsx
from util import parse_path, pop_pattern, LogSelf
import logging
_SPLIT_RE = re.compile(r'[- ]+')
Name.add('write-in', re.compile(r'write[- ]*in\b]', flags=re.IGNORECASE))
Name.add('total', re.compile(r'total[- ]*votes\b', flags=re.IGNORECASE))
log = LogSelf()


class Tabulator(LogSelf):
    """ A printout of tabulated results that should correspond with precinct results"""
    _all = {}
    _by_location = {}

    def __init__(self, **kwargs):
        """ build a tabulator from kwargs:
         Name, ID, 'Total Scanned', Counter, _file, _column
         Location - split into: locations=tuple( re.split[- ] )
        """
        self.name = pop_pattern(kwargs, r'.*\bName\b.*').strip()
        self.id = pop_pattern(kwargs, r'.*\bID\b.*')
        self.locations = tuple(_SPLIT_RE.split(pop_pattern(kwargs, r'.*\bLocation\b.*').strip()))
        self.total_scanned = pop_pattern(kwargs, r'.*\bTotal Scanned\b.*')
        self.protective_counter = pop_pattern(kwargs, r'.*\bCounter\b.*')
        self.vote_type = Fields['vote_types'].get('election day')
        self.county = pop_pattern(kwargs, r'.*\b(County|Region)\b.*')
        self._year = pop_pattern(kwargs, r'.*\byear\b.*')
        self._file = pop_pattern(kwargs, r'_file')
        self._column = pop_pattern(kwargs, r'_column')
        self._errors = {}

        # Now that all kwargs other than races have been removed, parse the races
        self.races = self.parse_races(kwargs)

        cls = self.__class__
        cls._all[self._key] = self

    @classmethod
    def by_location(cls, li: Iterable['Tabulator']) -> dict:
        """ :returns { location(str): Tabulator,... for each li}"""

        def _add_location(loc, tab):
            rv.setdefault(loc, set()).add(tab)

        rv = {}
        for tab in li:
            if len(tab.locations) > 1:
                _add_location(tab.locations, tab)
            for loc in tab.locations:
                _add_location(loc, tab)
        return rv

    def parse_races(self, kwargs: dict) -> dict:
        """ kwargs is ordered dict of races, candidates and votes from a tally tape:
        {   '4:President of the US': None,
            '5:Hodge': 123,
            '6:Podge': 321,
            '7:Borgensen': 2,
            '8:Write-in': 0,
            '9:Senate Seat 1': None,
            ... }
        The number is the row from the xlsx just to ensure uniqueness
        """
        accept = re.compile(r'\d+:.+')
        races, race_name = {}, ''
        for colA, val in kwargs.items():
            if not accept.fullmatch(colA):
                continue
            row, name = (f.strip() for f in colA.split(':', 1))
            row = int(row)

            # Names of races don't have vote counts
            if val is None or val == '':
                race_name = Fields['contests'].add(key=name)
                races[race_name] = {}
                continue
            # everything else is a candidate: vote_count (but catch formulas)
            try:
                races[race_name][Name.add(name)] = int(val)
            except ValueError:
                self.error(f"Found invalid vote count in {self._file} row: {row} race:{race_name} candidate:{name} = '{val}'", category='bad field')
                continue
        return races

    @property
    def _key(self):
        # it appears that counties name their tabulators, fulton uses generic names like 01A
        return self.county, self.name

    def __hash__(self):
        return hash(self.name)

    def __str__(self):
        return f"{self.name} <{self.id}> {self.races}"

    def __repr__(self):
        return f"{self.name} <{self.id}> {self.races}"

    def _validate_race(self, race_name: str = None, level: int = logging.WARNING) -> dict:
        race = self.races[race_name].copy()
        total = race.pop(Name['total votes'])
        if sum(race.values()) != total:
            self.error(f"Total Mismatch: Race[{race_name}] Total[{total}] != Cast[{sum(race.values())}", category='bad total')
        return self._errors

    def _validate_races(self, level: int = logging.WARNING):
        return {k: self._validate_race(k, level) for k in self.races}

    def validate(self, level: int):
        """ Attempt to find errors in THIS tape """
        return self._validate_races(level)


def load_tabulators(path: Path, **kwargs) -> dict:
    """ :returns {filename: [Tabulator1, Tabulator2, ...], ... }"""
    global log
    xlsx_files = path.glob('*.xlsx')
    kwargs.update(parse_path(path))
    di = {}
    for file in xlsx_files:
        if not file.exists():
            log.error("glob fail?", category='bad file')
            continue
        di[file.name] = Xlsx(filename=file).load_columns(Tabulator, **kwargs)
    return di


def generate_report(tape_path: Path, xml_path: Path):
    # Load the xml, and tapes.
    # for each tape - verify against xml
    # build list of warnings / errors / etc
    # maybe report should be an object

    # render to html/csv/...?
    pass

"""
Notes:
 - 'SS15A-SS15B ICP 2' is missing from scans - the file is just SS15A-SS15B ICP 1 rescanned

"""