# old / abandoned code

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

