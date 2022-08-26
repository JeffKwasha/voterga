
import re
from typing import Iterable
from db import Name
from pathlib import Path
from db.xls import Xlsx
import logging
from datetime import datetime
from pytz import utc


def now():
    return datetime.now(utc).replace(microsecond=0)


class Tabulator:
    """ A printout of tabulated results that should correspond with precinct results"""
    _all = {}

    def __init__(self, **kwargs):
        def pop_pattern(pattern: str, ignore_case=True):
            p = re.compile(pattern, flags=(ignore_case and re.IGNORECASE))
            for key in kwargs:
                if p.match(key):
                    return kwargs.pop(key)
        self.name = pop_pattern(r'.*\bName\b.*').strip()
        self.id = pop_pattern(r'.*\bID\b.*')
        self.location = pop_pattern(r'.*\bLocation\b.*').strip()
        self.total_scanned = pop_pattern(r'.*\bTotal Scanned\b.*')
        self.protective_counter = pop_pattern(r'.*\bCounter\b.*')
        self._file = pop_pattern(r'_file')
        self._column = pop_pattern(r'_column')
        self._errors = {}

        # Now that all kwargs other than races have been removed, parse the races
        self.races = self.parse_races(kwargs)

        self._all[self.key] = self

    def log(self, msg: str, level: int = logging.INFO, **kwargs):
        key = (now(), level)
        self._errors[key] = msg
        if level == logging.ERROR:
            logging.error(msg, **kwargs)
        elif level == logging.WARN:
            logging.warning(msg, **kwargs)
        else:
            logging.log(level=level, msg=msg, **kwargs)

    def error(self, msg, **kwargs):
        self.log(msg, level=logging.ERROR, **kwargs)

    def warning(self, msg, **kwargs):
        self.log(msg, level=logging.WARN, **kwargs)

    @property
    def errors(self) -> Iterable:
        return self._errors.values()

    def parse_races(self, kwargs: dict):
        """ kwargs is ordered dict of races, candidates and votes from a tally tape:
        {   '4:President of the US': None,
            '5:Trump': 123,
            '6:Biden': 321,
            '7:Jorgensen': 2,
            '8:Write-in': 0,
            '9:Senate Seat 1': None,
        ... }
        The number is the row from the xlsx
        """
        accept = re.compile(r'\d+:.+')
        races, race_name = {}, ''
        for colA, val in kwargs.items():
            if not accept.fullmatch(colA):
                continue
            row, name = (f.strip() for f in colA.split(':'))
            row = int(row)

            # Names of races don't have vote counts
            if val is None or val == '':
                race_name = Name.add(name)
                races[race_name] = {}
                continue

            # everything else is a candidate: vote_count (but catch formulas)
            try:
                races[race_name][Name.add(name)] = int(val)
            except ValueError:
                self.error(f"Found invalid vote count in {self._file} row: {row} race:{race_name} candidate:{name} = '{val}'")
                continue
        return races

    @property
    def key(self):
        return f"{self.id}:{self.name}"

    def __str__(self):
        return f"{self.name} <{self.id}> {self.races}"

    def __repr__(self):
        return f"{self.name} <{self.id}> {self.races}"

    def _validate_race(self, race_name: str = None, level: int = logging.WARNING) -> dict:
        race = self.races[race_name].copy()
        total = race.pop(Name['total votes'])
        if sum(race.values()) != total:
            self.error(f"Total Mismatch: Race[{race_name}] Total[{total}] != Cast[{sum(race.values())}")
        return self._errors

    def _validate_races(self, level: int = logging.WARNING):
        return {k: self._validate_race(k, level) for k in self.races}

    def validate(self, level: int):
        """ Attempt to find errors in THIS tape """
        return self._validate_races(level)


def load_tapes_xlsx(path: Path):
    xlsx_files = path.glob('*.xlsx')
    di = {}
    for file in xlsx_files:
        if not file.exists():
            logging.error("glob fail?")
            continue
        di[file.name] = Xlsx(filename=file).load_columns(Tabulator)
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