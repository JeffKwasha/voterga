import unittest
from datetime import datetime
from pathlib import Path
from common.sesame import tar_zst_readAll


columns = '''
COUNTY_CODE
REGISTRATION_NUMBER
VOTER_STATUS
LAST_NAME
FIRST_NAME
MIDDLE_MAIDEN_NAME
NAME_SUFFIX
NAME_TITLE
RESIDENCE_HOUSE_NUMBER
RESIDENCE_STREET_NAME
RESIDENCE_STREET_SUFFIX
RESIDENCE_APT_UNIT_NBR
RESIDENCE_CITY
RESIDENCE_ZIPCODE
BIRTHDATE
REGISTRATION_DATE
RACE
GENDER
LAND_DISTRICT
LAND_LOT
STATUS_REASON
COUNTY_PRECINCT_ID
CITY_PRECINCT_ID
CONGRESSIONAL_DISTRICT
SENATE_DISTRICT
HOUSE_DISTRICT
JUDICIAL_DISTRICT
COMMISSION_DISTRICT
SCHOOL_DISTRICT
COUNTY_DISTRICTA_NAME
COUNTY_DISTRICTA_VALUE
COUNTY_DISTRICTB_NAME
COUNTY_DISTRICTB_VALUE
MUNICIPAL_NAME
MUNICIPAL_CODE
WARD_CITY_COUNCIL_NAME
WARD_CITY_COUNCIL_CODE
CITY_SCHOOL_DISTRICT_NAME
CITY_SCHOOL_DISTRICT_VALUE
CITY_DISTA_NAME
CITY_DISTA_VALUE
CITY_DISTB_NAME
CITY_DISTB_VALUE
CITY_DISTC_NAME
CITY_DISTC_VALUE
CITY_DISTD_NAME
CITY_DISTD_VALUE
DATE_LAST_VOTED
PARTY_LAST_VOTED
DATE_ADDED
DATE_CHANGED
DISTRICT_COMBO
RACE_DESC
LAST_CONTACT_DATE
MAIL_HOUSE_NBR
MAIL_STREET_NAME
MAIL_APT_UNIT_NBR
MAIL_CITY
MAIL_STATE
MAIL_ZIPCODE
MAIL_ADDRESS_2
MAIL_ADDRESS_3
MAIL_COUNTRY'''.split("\t")


class TestSesame(unittest.TestCase):
    def test_tar(self):
        p = Path('data/test.tar.zst')

        def check_nfo(data, name, date:datetime, foo, bar):
            self.assertEqual('2017/001 voter 2017-05-01.txt', name)
            self.assertEqual('2023-10-12 04:47', date.strftime('%Y-%m-%d %H:%M'))
            self.assertEqual('foo', foo)
            self.assertEqual('bar', bar)
            self.assertEqual(columns, data[1:data.index('\n')].split('\t'))

        tar_zst_readAll(p, check_nfo, foo='foo', bar='bar')
