from race import Race, races
from util import deep_tally, deep_set
from db import Name, Fields
import unittest
candidates_senate = Fields(fields=['Perduped', 'Fluffler', 'Warmschlock', 'Ossofied'], key='senate')
candidates_pres = Fields(fields=['Frump', 'Puppet', 'Morguenson'], key='pres')
candidates_court = Fields(fields=['Eddie', 'Spongeslob', 'Ed', 'Edd'], key='court')


def build_races():
    return [
        Race.add(district=Name('d1'), seat=Name('Ga Senate 1'), candidates=candidates_senate),
        Race.add(district=Name('d2'), seat=Name('el presidente'), candidates=candidates_pres),
        Race.add(district=Name('d3'), seat=Name('court of public opinion'), candidates=candidates_court),
    ]


class TestRace(unittest.TestCase):
    def test_candidate_search(self):
        _races = build_races()

        self.assertEqual(candidates_senate.search('Perduped')[0], Race.find_candidate('Perduped')[0])
        self.assertEqual(candidates_pres.search('Frump')[0], Race.find_candidate('Frump')[0])
        self.assertEqual(Race['EL PRESIDENTE'].district, 'd2')


class TestDicts(unittest.TestCase):
    def test_deep_set(self):
        a = {}
        values = {
            'a.b.c': 'abc',
            'a.a.a': 'aaa',
            'x.y.z': 'xyz',
            '1.2.3': 123,
        }
        for k, v in values.items():
            deep_set(a, tuple(k.split('.')), v)

        for t, v in values.items():
            x, y, z = t.split('.')
            self.assertEqual(a[x][y][z], v)


if __name__ == '__main__':
    unittest.main()
