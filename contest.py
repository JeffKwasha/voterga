# define a race - a single seat in an election
import re
from typing import List
from pathlib import Path
from dateutil.parser import parse as parse_date
from datetime import datetime
from db import Name, Fields, first
from sos import property_dict
from pprint import pformat
from util import LogSelf, first, dict_sum, dict_diff, longest
"""
ElectionResult:
- VoterTurnout:
- Contest:
  - { race_name, ..., 
      VoteType:
      - {Undervotes, ..., Precinct:{name, votes} }
      - {Overvotes, ...}
      Choice:
      - {text: candidate_name, party: NP, totalVotes, 
          VoteType: 
          - {name: Election Day Votes, votes: 1234,
             Precinct:
             - {name: 01A, votes: 123}
             ...
          ... ['Election Day Votes', 'Advanced Voting Votes', 'Absentee by Mail Votes', 'Provisional Votes']
"""


class Contest(LogSelf):
    """ a contest within a county.  Note: statewide results include counties but not county results
    """
    _all = Fields(name='Contest')     # all Contests
    _vote_types = Fields(name='vote_types', fields={
        'day_of': r'(election.)?day.*',
        'advanced': r'advanced.voting.*',
        'absentee': r'absentee.*',
        'provisional': r'provisional.*',
        'under': r'under.*',
        'over': r'over.*'})

    def __init__(self, election_result, text: Name, key, precinctsReported,
                 voteFor=1, isQuestion=False, **kwargs):
        name = text
        self._election_result = election_result
        self._key = int(key)
        self.precinctsReported = precinctsReported
        self.vote_totals = {}
        self.totals = Fields()
        self.candidates = Fields()
        self.precincts = Fields()
        if name in Contest._all:
            self.error(f"Collision [{name}]", category='collision')
        self.name = self._all.add(name, value=self)
        kwargs = {k.lower(): v for k, v in kwargs.items()}

        def do_votetype(vote_type: str, candidate: Name or None, votes, precincts: List[dict]):
            if type(precincts) is dict:
                precincts = [precincts]
            vote_type = self._vote_types[vote_type]
            self.vote_totals[(candidate, vote_type)] = int(votes)
            for precinct in precincts:
                name = self.precincts.add(precinct['@name'])
                votes = int(precinct['@votes'])
                p = Precinct.add_votes(county=self.county, precinct=name, contest=self, votes=votes, candidate=candidate, vote_type=vote_type)
                self.precincts[name] = p

        if 'votetype' in kwargs:
            for vt in kwargs['votetype']:
                do_votetype(vote_type=vt['@name'], candidate=None, votes=vt['@votes'], precincts=vt['Precinct'])
        if 'choices' in kwargs:
            choices = kwargs['choices']
            if type(choices) is not list:
                choices = [choices]
            for choice in choices:
                name = self.candidates.add(choice['@text'])
                # party = Name.add(choice['@party'])
                self.totals[name] = int(choice['@totalVotes'])
                for vt in choice['VoteType']:
                    do_votetype(vote_type=vt['@name'], candidate=name, votes=vt['@votes'], precincts=vt['Precinct'])

    @property
    def timestamp(self):
        return self._election_result.Timestamp

    @property
    def election_name(self):
        return self._election_result.ElectionName

    @property
    def election_date(self):
        return self._election_result.ElectionDate

    @property
    def county(self):
        return self.region

    @property
    def region(self):
        return self._election_result.Region

    @classmethod
    def candidate(cls, name: str, contest: str = None) -> (str, dict):
        if contest is None:
            contests = cls._all.values()
        else:
            contests = [cls._all[contest]]
        results = {}
        for c in contests:
            rv = c.candidates.search(name, best_match=True)[0]
            if rv:
                results[rv] = c
        return longest(results), results

    @classmethod
    def race(cls, name: str):
        return cls[name]

    @classmethod
    def __class_getitem__(cls, item):
        return cls._all[item]



class VoteType:
    """ does this need to be a thing ... or just a function ?"""
    # TODO ...?
    def __init__(self, contest: Contest, choice: Name, name: Name, votes: int, precinct_data: List[dict]):
        self.name = name
        self.votes = int(votes)

        for pd in precinct_data:
            name = Name.add(pd['@name'])
            votes = int(pd['@votes'])
            #    def add_votes(self, contest: Name, vote_type: Name, choice: Name, votes: int):
            Precinct.add_votes(county=None, precinct=name, contest=contest.name, vote_type=self.name, candidate=choice, votes=votes)


class Precinct(LogSelf):
    _all = Fields(name="Precinct")
    _county = Fields(name="Precinct")

    def __init__(self, name: Name or tuple[Name], county: str, election_date: datetime, timestamp: datetime or set,
                 totalVoters, ballotsCast, voterTurnout, percentReporting,
                 number: int = 1,
                 **_):
        self.election_date = election_date
        self.timestamp = timestamp
        self.county = county        # county comes straight from ElectionResult.Region, only other place is website...
        self.number = number
        self.totalVoters = int(totalVoters)
        self.ballotsCast = int(ballotsCast)
        self.voterTurnout = float(voterTurnout)
        self.percentReporting =float(percentReporting)
        self.contests = {}
        if self.key in self._all:
            self.error(f"Collision: [{self}]:[{self._all[self.key]}]")
        self.name = self._all.add(name, value=self)

    @property
    def key(self):
        return self.county, self.name, self.number

    def __hash__(self):
        return hash(self.key)

    def _combine_timestamp(self, other: 'Precinct'):
        timestamp = set()
        for t in [self.timestamp, other.timestamp]:
            if type(t) is datetime:
                timestamp.add(t)
            else:
                timestamp.update(t)
        return timestamp

    def __add__(self, other: 'Precinct'):
        if not self.election_date == other.election_date:
            raise ValueError(f"Won't add precincts from ")
        county = self.county if self.county == other.county else f"{self.county},{other.county}"
        return Precinct(name=(self.name, other.name), county=county,
                        election_date=self.election_date, timestamp=self._combine_timestamp(other),
                        totalVoters=self.totalVoters+other.totalVoters,
                        ballotsCast=self.ballotsCast+other.ballotsCast,
                        voterTurnout=None, percentReporting=None)

    def diff(self, other: 'Precinct') -> dict:
        rv = {k:None for k in ['county', 'totalVoters', 'ballotsCast', 'election_date', 'timestamp']}
        for attr in rv.keys():
            pass
        return rv

    @classmethod
    def add_votes(cls, county: Name, precinct: Name, contest: Contest, vote_type: Name, candidate: Name, votes: int):\
        # TODO - precints aren't globally unique.  They must be within a county
        p = cls._all[precinct]
        if not p:
            raise ValueError(f"precinct: {precinct} not found")
        vt = p.contests.setdefault(contest.name, {}).setdefault(vote_type, {})
        vt[candidate] = votes
        return p

    def __class_getitem__(cls, item):
        return cls._all.search(item)[1]

    def __str__(self):
        return f"{self.county}:{self.name}[{self.ballotsCast}]"


class ElectionResult(LogSelf):
    def __init__(self, xml_dict):
        self.Timestamp = parse_date(xml_dict['Timestamp'])
        self.ElectionName = Name(xml_dict['ElectionName'])
        self.ElectionDate = parse_date(xml_dict['ElectionDate'])
        self.Region = xml_dict['Region']
        self._errors = {}

        # do VoterTurnout to init Precincts
        self._precincts = Fields()
        self._read_voter_turnout(xml_dict['VoterTurnout'])

        # do Contests to fill Precincts with votes
        self._contests = Fields(f"{self.Region}:contests")
        for contest in xml_dict['Contest']:
            c = Contest(election_result=self, **property_dict(**contest), choices=contest['Choice'], voteType=contest['VoteType'])
            self._contests[c.name] = c

    def precinct(self, name: Name):
        return self._precincts[name]

    def contest(self, name: Name):
        return self._contests[name]

    def _read_voter_turnout(self, voter_turnout: dict):
        _precinct_list = voter_turnout['Precincts']
        if len(_precinct_list) == 1 and 'Precinct' in _precinct_list:
            _precinct_list = _precinct_list['Precinct']
        # create precincts
        for precinct in _precinct_list:
            p = Precinct(county=self.Region, election_date=self.ElectionDate, timestamp=self.Timestamp,
                         **property_dict(**precinct))
            if p.name in self._precincts:
                _exist = self._precincts[p.name]
                self._errors.setdefault('duplicate precinct', set()).update({p, _exist})
                if _exist != p:
                    diffs = p.diff(_exist)
                    self.error(f"Precinct [{p.name}] already present: {pformat(diffs)}")
            self._precincts[p.name] = p

    @classmethod
    def load_from_xml(cls, filename: Path):
        from xmltodict import parse as xml_parse
        with open(filename, 'rb') as f:
            xml_dict = xml_parse(f)
        return ElectionResult(xml_dict['ElectionResult'])
