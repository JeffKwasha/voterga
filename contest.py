# define a race - a single seat in an election
from typing import List
from pathlib import Path
from dateutil.parser import parse as parse_date
from datetime import datetime
from db import Name, Fields, first
from sos import property_dict
import logging
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

class Contest:
    """ a contest within a county.  Note: statewide results include counties but not county results """
    _all = {}

    def __init__(self, election_result, text: Name, key, precinctsReported,
                 voteFor=1, isQuestion=False, **kwargs):
        self._election_result = election_result
        self.name = Name.add(text)
        self._key = int(key)
        self.precinctsReported = precinctsReported
        self.vote_type = {}
        self.totals = Fields()
        if self.name in Contest._all:
            logging.error(f"Collision Contest[{self.name}]")
        Contest._all[self.name] = self
        kwargs = {k.lower(): v for k, v in kwargs.items()}

        def do_votetype(vote_type: str, choice: Name, votes, precincts: List[dict]):
            if type(precincts) is not list:
                precincts = [precincts]
            vote_type = vote_type if type(vote_type) is Name else Name.add(vote_type.lower())
            self.vote_type[(choice, vote_type)] = int(votes)
            for precinct in precincts:
                name = Name.add(precinct['@name'])
                votes = int(precinct['@votes'])
                Precinct.add_votes(precinct=name, contest=self, votes=votes, choice=choice, vote_type=vote_type)

        if 'votetype' in kwargs:
            for vt in kwargs['votetype']:
                do_votetype(vote_type=vt['@name'], choice=Name[None], votes=vt['@votes'], precincts=vt['Precinct'])
        if 'choices' in kwargs:
            choices = kwargs['choices']
            if type(choices) is not list:
                choices = [choices]
            for choice in choices:
                name = Name.add(choice['@text'])
                # party = Name.add(choice['@party'])
                self.totals[name] = int(choice['@totalVotes'])
                for vt in choice['VoteType']:
                    do_votetype(vote_type=vt['@name'], choice=name, votes=vt['@votes'], precincts=vt['Precinct'])

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


class VoteType:
    """ does this need to be a thing ... or just a function ?"""
    def __init__(self, contest: Contest, choice: Name, name: Name, votes: int, precinct_data: List[dict]):
        self.name = name
        self.votes = int(votes)

        for pd in precinct_data:
            name = Name.add(pd['@name'])
            votes = int(pd['@votes'])
            #    def add_votes(self, contest: Name, vote_type: Name, choice: Name, votes: int):
            Precinct.add_votes(precinct=name, contest=contest.name, vote_type=self.name, choice=choice, votes=votes)


class Precinct:
    _all = Fields()

    def __init__(self, name: Name, county: Name, election_date: datetime, timestamp: datetime,
                 totalVoters, ballotsCast, voterTurnout, percentReporting,
                 number: int = 1,
                 **_):
        self.name = name = Name.add(name)
        self.election_date = election_date
        self.timestamp = timestamp
        self.county = county
        self.number = number
        self.totalVoters = int(totalVoters)
        self.ballotsCast = int(ballotsCast)
        self.voterTurnout = float(voterTurnout)
        self.percentReporting =float(percentReporting)
        self.contests = {}
        if name in self._all:
            logging.error(f"Precinct collision: {self._all[name]}")
        self._all[self.name] = self

    def __hash__(self):
        return hash((self.county, self.name, self.number))

    @classmethod
    def add_votes(cls, precinct: Name, contest: Contest, vote_type: Name, choice: Name, votes: int):
        p = cls._all[precinct]
        if not p:
            raise ValueError(f"precinct: {precinct} not found")
        vt = p.contests.setdefault(contest.name, {}).setdefault(vote_type, {})
        vt[choice] = votes

    def __class_getitem__(cls, item):
        return cls._all.search(item)


class ElectionResult:
    def __init__(self, xml_dict):
        self.Timestamp = parse_date(xml_dict['Timestamp'])
        self.ElectionName = Name(xml_dict['ElectionName'])
        self.ElectionDate = parse_date(xml_dict['ElectionDate'])
        self.Region = xml_dict['Region']

        # do VoterTurnout to init Precincts
        self._precincts = Fields()
        _precinct_list = xml_dict['VoterTurnout']['Precincts']
        if len(_precinct_list) == 1 and 'Precinct' in _precinct_list:
            _precinct_list = _precinct_list['Precinct']
        for precinct in _precinct_list:
            p = Precinct(county=self.Region, election_date=self.ElectionDate, timestamp=self.Timestamp,
                         **property_dict(**precinct))
            self._precincts[p.name] = p

        # do Contests to fill Precincts with votes
        self._contests = Fields()
        for contest in xml_dict['Contest']:
            c = Contest(election_result=self, **property_dict(**contest), choices=contest['Choice'], voteType=contest['VoteType'])
            self._contests[c.name] = c

    def precinct(self, name: Name):
        return self._precincts[name]

    def contest(self, name: Name):
        return self._contests[name]

    @classmethod
    def load_from_xml(cls, filename: Path):
        from xmltodict import parse as xml_parse
        with open(filename, 'rb') as f:
            xml_dict = xml_parse(f)
        return ElectionResult(xml_dict['ElectionResult'])
