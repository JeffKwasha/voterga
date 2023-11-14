import re

RE_EXT = re.compile(r'(?P<ext>\.(txt|csv|zip|tar|tgz|txz|tar\.[a-z]+))$').pattern
RE_YEAR = re.compile(r'(?P<year>\d{4}\b)').pattern
RE_BORN = re.compile(r'(?P<born>\d{4}[_.-]\d{2}[_.-]\d{2}\b)').pattern
RE_COUNTY = re.compile(r'(?P<county>\d{3}|ALL|Statewide)').pattern
RE_TABLENAME = re.compile(r'(?P<table_name>\w+)(?: File)?').pattern

