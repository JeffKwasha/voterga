from race import Race
from util import deep_set
from common import Name, Fields
from pathlib import Path
import unittest
import duckdb as ddb

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

class Test_DucksaLot(unittest.TestCase):
    def test_duck_load(self):
        from common.sesame import tar_zst_readAll
        dir = Path('data')
        duck = ddb.connect(str(dir.joinpath('duck.db')), read_only=False)

        def _duck_load(data, name=None, date=None, **kwargs):
            if _rv := duck.read_csv(data, normalize_names=True):
                pass
            else:
                print(f"Problems loading?")
            pass

        tar_zst_readAll(dir, _duck_load, )
        pass

    def test_duck_save(self):
        pass

    def test_duck_query(self):
        pass




if __name__ == '__main__':
    unittest.main()
