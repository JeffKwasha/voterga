""" Read delimited text data files and call a callback on each row

if the callback returns true, do not accumulate the rows (free memory) into the DB
"""

import tarfile
import csv
from io import StringIO, BytesIO, IOBase
from pathlib import Path
from typing import TextIO, TypeAlias
from collections.abc import Callable
from datetime import datetime

from magic import Magic
import zstandard
from zipfile import ZipFile
import polars as pl


magic = Magic(uncompress=True, mime=True)


def guess_separator(data: str | Path | TextIO) -> str:
    if type(data) is str and len(data) < 250 and '/' in data:
        data = Path(data)
    if isinstance(data, Path):
        assert data.exists()
        assert data.is_file()
        with open(data, 'r') as f:
            return guess_separator(f.readline())
    if isinstance(data, TextIO) and data.seekable():
        file = data
        pos = file.tell()
        file.seek(0)
        data = file.readline()
        file.seek(pos)

    guesses = '\t,|;:'
    counts = [0] * len(guesses)
    max_count = 0
    try:
        eol = data.index('\n')
    except ValueError:
        eol = len(data)
    for i, c in enumerate(guesses):
        counts[i] = data[:eol].count(c)
        if counts[i] > counts[max_count]:
            max_count = i
    return guesses[max_count]


def db_insert_copy(table, conn, keys, data_iter):
    """
    Execute SQL statement inserting data

    Parameters
    ----------
    table : pandas.io.sql.SQLTable
    conn : sqlalchemy.engine.Engine or sqlalchemy.engine.Connection
    keys : list of str
        Column names
    data_iter : Iterable that iterates the values to be inserted
    """
    # gets a DBAPI connection that can provide a cursor
    dbapi_conn = conn.connection
    with (dbapi_conn.cursor() as cur):
        s_buf = StringIO()
        writer = csv.writer(s_buf)
        writer.writerows(data_iter)
        s_buf.seek(0)

        columns = ', '.join(['"{}"'.format(k) for k in keys])
        if table.schema:
            table_name = '{}.{}'.format(table.schema, table.name)
        else:
            table_name = table.name

        sql = f'COPY {table_name} ({columns}) FROM STDIN WITH CSV'
        cur.copy_expert(sql=sql, file=s_buf)


def get_mime(file: str | Path | IOBase) -> str:
    if isinstance(file, Path):
        if not file.exists():
            return '_NO_FILE_:path'
        if file.is_dir():
            return '_DIR_:path'
        assert file.is_file()
        return ':'.join([magic.from_file(file), file.suffix])
    if type(file) in (bytes, str):
        if type(file) is str and len(file) < 500 and (p := Path(file)):
            return get_mime(p)
        return ':'.join([magic.from_buffer(file), 'buf'])
    if isinstance(file, IOBase):
        assert file.seekable()
        buf = file.read(4096)
        file.seek(0)
        return ':'.join([magic.from_buffer(buf), 'io'])
    return '_?_:'


def process_data_stub(data: str | bytes, name: str, date: datetime, mime: str = None, **kwargs) -> bool | int:
    raise NotImplementedError


def read_file(file: str | Path | BytesIO,
              fn: Callable[process_data_stub],
              just_files=True,
              mime: str = '',
              **fn_args) -> int:
    """ given a file's path, call fn() with the file's data

    :param file: Path to a data file or a BytesIO containing data
    :param fn: data processing function[data: str, name: str, date: datetime, mime: str, ...]
    :param mime: don't bother checking for mime - we know it.
    :param just_files: don't call fn for non-file archive contents (directories)
    :param fn_args: caller specified kwargs for fn()
    :return:
    """
    mime = mime or get_mime(file)
    count = 0
    match mime.split(':'):
        case ('application/zstd', y):
            assert y[0] == '.'      # file is a path, y is a suffix, zstd compressed files shouldn't be nested
            # consider zstandard.multi_decompress_to_buffer()
            with zstandard.open(filename=file) as ft:
                return read_file(BytesIO(ft.read()), fn=fn, just_files=just_files, name=file, **fn_args)

        case ('application/zip', y):
            assert y[0] == '.'      # file is a path, y is a suffix, zipfiles shouldn't be nested
            zf = ZipFile(file, mode='r')
            for f in zf.namelist():
                buf = zf.extract(member=f)
                count += fn(buf, name=file, date=datetime(*zf.getinfo(f).date_time), mime=mime, **fn_args)

        case ('application/x-tar', y):
            open_args={'mode': 'r'}
            if isinstance(file, (IOBase, BytesIO)):
                open_args['fileobj'] = file
            else:
                open_args['name'] = fn_args['name'] = file
            with tarfile.open(**open_args) as tar:
                while mbr := tar.next():
                    if mbr.isfile():
                        ef = BytesIO(initial_bytes=tar.extractfile(mbr).read())
                    elif just_files:
                        ef = None
                        continue
                    data = ef.read().decode() if ef else None
                    count += fn(data, date=datetime.utcfromtimestamp(mbr.mtime), **fn_args)

        case ('text/plain', 'buf'):
            # Caller should've put name, date in the fn_args for us
            return fn(file, mime=mime, **fn_args)

        case ('application/octet-stream', 'buf'):
            # Caller should've put name, date in the fn_args for us
            return fn(file, mime=mime, **fn_args)

        case ('_DIR_', 'path'):
            for file in Path(file).glob('*'):
                count += read_file(file=file, fn=fn, just_files=just_files, **fn_args)
            return count

        case ('_NO_FILE_', 'path'):
            pass

        case _:
            print(f"Mime: >{mime}<")
    return False


def test_read_files():
    file = Path('/home/jk/src/sospicious/data/voter/2022/2022-01-04.tar.zst')
