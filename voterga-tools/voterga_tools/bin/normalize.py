#!/bin/env python3
""" Normalize input data files and save in [parquet, tar, ...] format

"""

from typing import Dict, ClassVar, Callable, NamedTuple, Iterable, Union
from argparse import ArgumentParser
from pathlib import Path
from collections import namedtuple
import tarfile
import zipfile
from subprocess import run
import os
from distutils.spawn import find_executable
from dataclasses import dataclass
import logging
from tempfile import TemporaryDirectory
from pprint import pprint
from datetime import datetime

import xlsxwriter
from dateutil.parser import parse as date_parse

from db.xls import Xlsx

import polars as pl
from polars import DataFrame

from common.patterns import *

# command line tool
_COMMANDS = {
    '7z_x': '/usr/bin/7z x -bd -aou'.split(),
    'tar_cz': '/usr/bin/tar --zstd -cf'.split(),
}
LOG = logging.root
CWD = Path('.').expanduser().resolve()
_TYPE_MAP = {
    'str': pl.Utf8,
    'utf8': pl.Utf8,
    'int': pl.Int32,
    'int32': pl.Int32,
    'int64': pl.Int64,
    'int16': pl.Int16,
    'int8': pl.Int8,

    'uint': pl.UInt32,
    'uint32': pl.UInt32,
    'uint64': pl.UInt64,
    'uint16': pl.UInt16,
    'uint8': pl.UInt8,

    'float': pl.Float32,
    'float64': pl.Float64,
    'num': pl.Float32,
}


def get_args():
    ap = ArgumentParser()
    ap.add_argument('-d', '--data_dir', type=Path)
    ap.add_argument('-o', '--output', type=Path, default=None, help="output here instead of data_dir")
    ap.add_argument('-K', '--keep', action='store_true', default=False, help="don't delete extracted [intermediate] files")
    ap.add_argument('-S', '--shell', action='store_true', default=False, help='Use shell commands when available')
    ap.add_argument('files', nargs='+', help='Files to normalize', type=str)
    rv = ap.parse_args()
    if not rv.data_dir:
        rv.data_dir = Path('.').expanduser().resolve()
    return rv


def guess_separator(data_str: str) -> str | None:
    """ Scan a line of a csv/tab file for the correct separator
    :param data_str: a string starting with at least one line of the csv/tab file
    :return: a one character string (the separator) or None
    """
    guesses = '\t,|;:'
    counts = [0] * len(guesses)
    max_count = 0
    # Just one line
    assert data_str
    if (eol := data_str.index('\n')) and eol > 0:
        data_str = data_str[:eol]

    for i, c in enumerate(guesses):
        counts[i] = data_str.count(c)
        if counts[i] > counts[max_count]:
            max_count = i
    if counts[max_count] < 3:
        LOG.error(f"no separator in >{data_str}< - only {max_count} (min 3) columns detected")
        return None
    return guesses[max_count]


@dataclass
class ColumnInfo:
    """ allow column info to be easily read from xlsx
    // FILE_COLUMNS - the columns we care about in the fields file, first column must be name
    ColumnInfoT - a namedtuple of those FILE_COLUMNS
    fields.xlsx - a multi-sheet spreadsheet, each sheet has columns of a version of the exported data (2017 vs 2020 vs 2023)
        name	        map_to                          type	        ignore	        Red
        Column_name     Normalized_name or Pattern      str/int/utf8    ignore | null   red | null
    """
    ColumnInfoT: ClassVar[NamedTuple] = namedtuple('ColumnInfoT', ['map_to', 'ignore', 'type'], defaults=[None])

    # -- Each ColumnInfo is a worksheet in a fields file
    name: str                       # Name of the sheet
    columns: dict[str, ColumnInfoT]  # |tuple[pl.DataType]]       # { Column_Name: ColumnInfoT(...) }

    _all: ClassVar[dict[str | tuple, 'ColumnInfo']] = {}       # keep a dict to get the columnInfo based on sheet-name (date) or tuple of columns
    fields_path: ClassVar[Path] = Path('~/src/sospicious/data/voter/fields.xlsx').expanduser().resolve()

    @classmethod
    def load_fields(cls, file: Path | None = None):
        file = file or ColumnInfo.fields_path
        sheets: dict[str, DataFrame] = pl.read_excel(file, sheet_id=0)
        for name, sheet in sheets.items():
            fields: dict[str, NamedTuple | tuple] = {}
            df: DataFrame = sheet.select(pl.col(['name', *cls.ColumnInfoT._fields]).str.strip_chars(' \t\r"[]').str.to_lowercase())
            for row in df.iter_rows():
                row = {df.columns[n]: v for n, v in enumerate(row)}
                field_name = row.pop('name')
                assert field_name not in fields
                fields[field_name] = cls.ColumnInfoT(**row)
            cls(name=name, columns=fields)

    @classmethod
    def save_fields(cls, path: Path | None = None, skip_existing=True) -> int:
        """ Write all the fields to xlsx at path """
        from xlsxwriter import Workbook
        path = path or cls.fields_path
        saved = 0
        with (Workbook(filename=path) as wb):
            existing = [w.get_name() for w in wb.worksheets()]
            for name, ci in cls._all.items():
                if skip_existing and name in existing:
                    continue
                di = {'name': list(ci.columns.keys())}
                for field in cls.ColumnInfoT._fields:
                    di[field] = [getattr(v, field, None) for v in ci.columns.values()]
                DataFrame(data=di).write_excel(workbook=wb, worksheet=name, autofit=True)
                saved += 1
        return saved

    @staticmethod
    def to_pl_type(_type: str | pl.DataType, default=pl.Utf8):
        global _TYPE_MAP
        if isinstance(_type, str):
            _type = _TYPE_MAP.get(_type.lower(), default)
        elif isinstance(_type, pl.DataType):
            pass
        else:
            _type = default
        return _type

    def __post_init__(self):
        cls = self.__class__
        cls._all[self.name] = self
        cls._all[tuple(self.columns.keys())] = self
        for k, v in self.columns.items():
            if not v:
                continue
            self.columns[k] = v._replace(type=self.to_pl_type(v.type))

    @classmethod
    def from_columns(cls, name: str, cols: Iterable[str]) -> 'ColumnInfo':
        return cls(name=name, columns={n: None for n in cols})

    @classmethod
    def __class_getitem__(cls, item):
        return cls._all[item]

    @classmethod
    def from_file(cls, path: Path):
        """ Given a table file, return the appropriate ColumnInfo obj """
        match path.suffix:
            case '.parquet':
                return cls[tuple(pl.read_parquet_schema(path).keys())]
            case '.csv' | '.txt' | '.tab':
                with open(path, 'r') as f:
                    sep = guess_separator(f.readline())
                df = pl.read_csv(source=path, skip_rows_after_header=True, separator=sep)
                return cls[tuple(df.columns)]
        return

    @classmethod
    def get(cls, item):
        return cls._all.get(item, item)

    @property
    def dropped_columns(self) -> list[str]:
        drops = []
        for name, ci_t in self.columns.items():
            if (to := ci_t.map_to) and to not in ('ignore', '-', None, ''):
                pass    # Keep this
            else:
                drops.append(name)
        return drops


@dataclass
class TableFile:
    """ Figure out what/when columns, etc for a file
    """
    path: Path
    table_name: str
    born: datetime | str
    county: str = 'all'
    columns: ColumnInfo | tuple[str] = None
    separator: str = None
    REX: ClassVar[Dict[Callable, re.Pattern]] = {
        lambda p: p.is_file() and p.stem:
            re.compile(r"[_ .-]+".join([RE_COUNTY, RE_TABLENAME, RE_BORN])),

        lambda p: p.is_file() and p.stem:
            re.compile(r"[_ .-]+".join([RE_COUNTY, RE_BORN, RE_TABLENAME])),

        lambda p: p.is_file() and p.stem:
            re.compile(r"[_ .-]+".join([RE_COUNTY, RE_BORN, RE_TABLENAME])),

        lambda p: p.is_file() and '/'.join(p.parts[-2:]):
            re.compile(rf"{RE_TABLENAME}/{RE_BORN}{RE_EXT}"),

        lambda p: p.is_file() and '/'.join(p.parts[-2:]):
            re.compile(rf"{RE_BORN}/({RE_COUNTY}[_ .-])?{RE_TABLENAME}([_ .-].*)?{RE_EXT}"),

        lambda p: p.is_file() and '/'.join(p.parts[-3:]):
            re.compile(rf"{RE_TABLENAME}/{RE_BORN}/(.*){RE_EXT}"),

        lambda p: p.is_dir() and '/'.join(p.parts[-2:]):
            re.compile(rf"{RE_TABLENAME}/{RE_YEAR}/{RE_BORN}"),

        lambda p: p.is_dir() and '/'.join(p.parts[-2:]):
            re.compile(rf"{RE_TABLENAME}/{RE_BORN}"),
    }

    @classmethod
    def from_file(cls, file: Path | str) -> Union[None, 'TableFile']:
        """ instantiate TableFile from a path """
        path = Path(file) if isinstance(file, str) else file
        path = path.expanduser().resolve()

        if not path.is_file():
            print(f"{path} no such file")
            return None
        if path.suffix not in ('.parquet', '.csv', '.txt', '.tab'):
            print(f"{path} unsupported file")
            return None

        kwargs = {}
        # prep Defaults
        _stats = path.stat()
        kwargs['born'] = datetime.fromtimestamp(min(_stats.st_ctime, _stats.st_mtime))

        # grab info from path
        for fn, pattern in cls.REX.items():
            if s := fn(path):
                if m := pattern.fullmatch(s):
                    kwargs.update(m.groupdict())
                    break

        # instantiate
        return cls(path=path, **kwargs)

    def __post_init__(self):
        if type(self.born) == str:
            self.born = date_parse(self.born)
        self.load_columns()

    def load_columns(self) -> None:
        if self.path.suffix in ('.parquet',):
            self.columns = ColumnInfo.get(tuple(pl.read_parquet_schema(self.path).keys()))
            return
        with open(self.path, 'r') as f:
            data_str = f.readline()
        try:
            self.separator = guess_separator(data_str=data_str)
            self.columns = tuple(data_str.split(sep=self.separator))
            self.columns = ColumnInfo.get(self.columns)
        except Exception:
            LOG.error(f"Unable to find a separator in >{data_str}<")
        if type(self.columns) == tuple:
            self.columns = ColumnInfo.from_columns(name=self.born_str, cols=self.columns)

    @property
    def born_str(self) -> str:
        if self.born.hour or self.born.minute or self.born.second:
            return self.born.isoformat(sep=' ')
        else:
            return self.born.strftime("%Y-%m-%d")

    def output_path(self, root: Path | None = None):
        path = Path(f"{self.table_name}/{self.born_str}")
        if root:
            return root.joinpath(path)
        return path

    def parquet_path(self, root: Path | None = None):
        return self.output_path(root).parent.joinpath(f"{self.born_str}.parquet")

    @staticmethod
    def remap_NOOP(row, **kwargs):
        return row

    def normalize(self, remap: Callable = remap_NOOP, root: Path = None):
        """ Read a file, normalize it's rows, write it to parquet_path """
        kwargs={}
        load_fn = pl.read_csv
        match self.path.suffix:
            case ".parquet":
                load_fn = pl.read_parquet
            case ".csv" | ".tab" | ".txt":
                kwargs['separator'] = self.separator
            case _:
                kwargs['separator'] = self.separator

        (load_fn(self.path, **kwargs)
         .drop(self.columns.dropped_columns)
         .map_rows(function=remap)
         .write_parquet(file=self.parquet_path(root)))


def extract(in_file: Path, out_dir: Path, data_dir: Path = None) -> bool:
    global CWD
    data_dir = data_dir or CWD
    assert(in_file.exists())
    del_to_dir = not out_dir.exists()
    out_dir.mkdir(exist_ok=True)
    moved = []

    with TemporaryDirectory(dir=data_dir) as tmp:
        cmd_l = _COMMANDS['7z_x'] + [f'-o{tmp}', f'{in_file.absolute()}']
        LOG.info(f"{in_file.relative_to(CWD)} -unzip-> {tmp}")
        rv = run(cmd_l, check=True, capture_output=True)
        if rv.returncode != 0:
            raise (RuntimeError(rv.stderr))
        LOG.info(f"{in_file.relative_to(CWD)} -> {out_dir.relative_to(CWD)}")
        texts = list(Path(tmp).glob('**/*.txt')) or list(Path(tmp).glob('**/*.csv'))
        LOG.info(f"moving {len(texts)}... {texts[:4]}...")
        for in_file in texts:
            if 'MAP' in in_file.parts:
                continue
            moveP = out_dir.joinpath(in_file.name)
            assert moveP.exists() is False
            LOG.info(f"Move: {in_file.relative_to(CWD)} -> {moveP.relative_to(CWD)}")
            in_file.rename(moveP)
            moved.append(moveP.name)

    LOG.info(f"Moved: {len(moved)} ======\n{moved[:4]}...")
    return del_to_dir


def main():
    args = get_args()
    for input in args.files:
        output = args.output or args.data_dir
        tf = TableFile.from_file(input)
        out_path = tf.output_path(output)
        tf.normalize(remap=lambda t: t, root=out_path)
        pass


if __name__ == "__main__":
    main()
