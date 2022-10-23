from db import Name, Fields
import unittest


class TestFields(unittest.TestCase):
    def test_basic(self):
        data = {'a': 1,
                'B': 2,
                ('c', 3): 3,
                'D': (1, 2, 3, 4),
                Name('kyle', pattern=r'.*\bkyle\b.*'): 'KYLE!',
                Name('timmy', pattern=r'.*\btimmy\b.*'): 'TIMMY!',
                Name('jimmy', pattern=r'jimmy\b.*'): 'JIMMY!',
                }
        f = Fields(key=None, fields=data)

        self.assertEqual(len(f), len(data))     # nothing skipped, nothing collides
        self.assertEqual(1, f['a'])             # Simple dict
        self.assertEqual(2, f['b'])             # case ignored
        self.assertEqual(2, f[' B '])           # white space stripped
        self.assertEqual(1, f['a xyz'])         # search: anything after a
        self.assertEqual(1, f['a B'])           # search: anything after a
        self.assertEqual(1, f['B a'])           # search: anything before a (*a* before *b*)
        self.assertEqual(2, f['B D'])           # search: anything after b (*B* before *D*)
        self.assertEqual(2, f['b d'])           # search: anything after b case ignored
        self.assertEqual(3, f[('c', 3)], 3)     # key is a tuple match
        self.assertEqual((1, 2, 3, 4), f['d'])  # value can be anything

        self.assertRaises(KeyError, f.__getitem__, 'KEY_NOT_FOUND')     # getitem throws
        self.assertRaises(KeyError, f.__getitem__, ('c xyz', 3))        # req exact tuple

        self.assertEqual('TIMMY!', f['!TIMMY!'])        # punctuation is fine

        self.assertEqual('KYLE!', f['kyle timmy'])              # getitem first beats longest
        self.assertEqual('TIMMY!', f.search('kyle timmy')[1])   # search best_match uses length

        self.assertEqual('TIMMY!', f['jimmy timmy'])            # getitem first match
        self.assertEqual('TIMMY!', f.search('jimmy timmy')[1])  # equal len therefore dict order

    def test_collisions(self):
        data = {'a': 0,
                'a b': 1,
                'ab': 2,
                Name('cheat', pattern=r'.*\bcheat\b.*'): 'cheat!',
                Name('cheat collision', pattern=r'.*\bcollision\b.*'): 'collide!',
                Name('cheat2', pattern=r'.*\bcheat2\b.*'): 'CHEAT2!',
                }
        f = Fields(key=None, fields=data)

        self.assertLess(len(f), len(data))      # collisions reduced f
        self.assertEqual(1, f['a'])             # collision overwrote 0
        self.assertEqual(2, f['ab'])

        self.assertEqual('collide!', f['cheat'])
        self.assertEqual('collide!', f['cheat cheat'])

        self.assertEqual('CHEAT2!', f.search('cheat2')[1])
        self.assertRaises(KeyError, f.__getitem__, 'cheat1')     # getitem throws
        self.assertRaises(KeyError, f.__getitem__, 'cheat21')    # getitem throws


class TestName(unittest.TestCase):
    pass


if __name__ == '__main__':
    unittest.main()
