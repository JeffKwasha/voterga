""" All the various imported data structures need to agree on a results structure for a race
Goals:
 - a way to recognize things like "Ga Senate 1" == "Georgia Senate (Perdue)"
 - a way to find(CANDIDATE_NAME) with or without a race
 - ?? handle 'overvotes' / 'undervotes'
 - how to specify: election day votes, absentee/mail, early, provisional, ...
 - method to return tallied results
"""

from typing import NamedTuple
from db import Fields, Name, SearchResult
#__all__ = ['races', 'Race']

races = Fields(key='Races')


class Race(NamedTuple):
    district: Name              # ga = state-wide, cobb = county-wide
    seat: Name                  # fulton.court.1, state.house.6
    sources: set = set()        # files, url, etc - WHO DO I BLAME for this data
    candidates: Fields = Fields()
    state: Name = Name('Georgia')

    @classmethod
    def add(cls, district: Name, seat: Name, sources: set = None, candidates: Fields = None):
        global races
        try:
            r = races[seat]
            if candidates:
                r.candidates.update(candidates)
            if sources:
                r.sources.union(sources)
        except KeyError:
            r = cls(district, seat, sources, candidates)
            races[seat] = r
        return r

    @property
    def key(self):
        return self.seat

    def __str__(self):
        return f"{self.seat}: {self.candidates}"

    @classmethod
    def __class_getitem__(cls, item):
        return races[item]

    @classmethod
    def find_candidate(cls, candidate: str, race: str = None) -> SearchResult:
        rv = Fields()
        search_races = races.values() if not race else [races.search(race, best_match=True).value]
        for r in search_races:
            found = r.candidates.search(candidate)[0]
            if not found:
                continue
            rv[found] = r.seat
        return rv.search(candidate, best_match=True)
