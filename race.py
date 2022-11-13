""" All the various imported data structures need to agree on a results structure for a race
Goals:
 - a way to recognize things like "Ga Senate 1" == "Georgia Senate (Perdue)"
 - a way to find(CANDIDATE_NAME) with or without a race
 - ?? handle 'overvotes' / 'undervotes'
 - how to specify: election day votes, absentee/mail, early, provisional, ...
 - method to return tallied results
"""

from typing import NamedTuple, Hashable, Iterable
from db import Fields, Name, SearchResult
from util import deep_set
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
    def __class_getitem__(cls, item) -> 'Race':
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

    @classmethod
    def add_votes(cls, seat: str, candidate: str, count: int, source: str, precinct: Hashable,
                  vote_type: str = 'election day'):
        race = cls[seat]
        race.set_votes(candidate=candidate, count=count, source=source, precinct=precinct, vote_type=vote_type)
        return race.candidates[candidate][source][precinct]

    def set_votes(self, candidate: str, count: int, source: str, precinct: tuple or str,
                  vote_type: str = 'election day'):
        deep_set(self.candidates, (candidate, source, precinct, vote_type), count)
        if isinstance(precinct, tuple):
            precinct_dict = self.candidates[candidate][source][precinct]
            for p in precinct:
                self.candidates[candidate][source][p] = precinct_dict

    def tally(self, source: str, candidate: str = None, precinct: tuple or str = None, vote_type: str = None):
        def deep_tally(di: dict, keys: tuple):
            if not isinstance(di, dict):
                return di
            for n, k in enumerate(keys):
                if k is None:
                    return sum([deep_tally(di[_key], keys[n+1:]) for _key in di])
                if n == len(keys) - 1:
                    di = di[k]
                    return di if not isinstance(di, dict) else deep_tally(di, (None,))
                if k not in di:
                    return 0
                di = di[k]
            return 0
        return deep_tally(self.candidates, (candidate, source, precinct, vote_type))

    def get_precinct(self, source: str, precinct: Hashable):
        """ build a precinct dict from a race and source"""
        rv = {}
        for candidate in self.candidates:
            rv[candidate] = self.candidates[candidate][source][precinct]
        return rv
