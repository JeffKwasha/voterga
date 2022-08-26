# handle importing precinct data from the sos website
from db import Name
from top import Data


class Tabulation(Data):
    """ precinct is a tally?
    """
    fields = {
        "Tabulator ID",
        "Voting Location",
        "Protective Counter",
        "Total Scanned",
        "President of the US",
        "Trump",
        "Biden",
        "Jorgensen"
        "Write-In",
        "Total Votes",

        "U.S Senate (Perdue)",
        "Perdue",
        "Ossoff",
        "Hazel",
        "Write-in",
        "Total Votes",

        "U.S. Senate Loeffler",
        "Bartell",
        "Buckley",
        "Collins",
        "Fortune",
        "Grayson",
        "Greene",
        "Annette",
        "Jackson",
        "Deborah",
        "Jackson",
        "Jease",
        "Johnson",
        "Johnson - Shealey",
        "Lieberman",
        "Loeffler",
        "Slade",
        "Slowinski",
        "Stowall",
        "Tarver",
        "Taylor",
        "Warnock",
        "Winfield",
        "Write-in",
        "Total Votes",
    }

    def __init__(self, name: Name, fields: dict, desc: str = None):
        self.name = name
        self.desc = desc
        self.printed_date = None










