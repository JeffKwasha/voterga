"""
Top level objects - needs a better name
"""

from db import Name

class Data:
    @classmethod
    def parameters(cls):
        return list(Name(n) for n in cls.__slots__)