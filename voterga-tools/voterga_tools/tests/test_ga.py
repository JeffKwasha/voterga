import unittest
from pathlib import Path

from ga.county import County


class TestCounty(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        County.load(file=Path('data/GA 2020 County.csv'))

    def test_load(self):
        # 159 counties, both by name and by number
        self.assertEqual(159 * 2, len(County.all()))

    def test_order(self):
        self.assertEqual('Cobb', County[33])
        self.assertEqual('Fulton', County[60])

    def test_muni_search(self):
        self.assertSetEqual({'Fulton'}, County.find_muni('union city'))
        self.assertSetEqual({'Fulton', 'Dekalb'}, County.find_muni('atlanta'))
        self.assertSetEqual({'Fulton', 'Dekalb'}, County.find_muni('aTLANTA'))

    def test_lookup(self):
        self.assertEqual('cobb', County['cobb'])
        self.assertEqual('cobb', County[33])
        cobb = County[33]
        self.assertSetEqual({'Smyrna', 'Acworth', 'Austell', 'Kennesaw', 'Marietta', 'Powder Springs'}, set(cobb.munis))
