""" Sesame as in "open sesame"
intelligently handles compressed tarfiles and whatnot
"""
from pathlib import Path
import tarfile, zipfile
from io import BytesIO
from typing import Any, AnyStr, List, Callable
from dataclasses import dataclass
from datetime import datetime
import logging
import re
from tempfile import TemporaryDirectory
from subprocess import run as subp_run

import magic
import zstandard
import requests

LOG = logging.root
SevenZipEx = '/usr/bin/7z x -bd -aou'.split()
TarZstd = '/usr/bin/tar --zstd -cf'.split()
COMPRESS = 'zstd'
COMPRESS_LVL = 12
DataDir = Path('.').resolve()

if not LOG.hasHandlers():
    logging.basicConfig(level=logging.INFO)


def tar_zst_readAll(filePath: Path, data_fn: Callable, just_files=True, **kwargs):
    with zstandard.open(filePath, 'rb') as zf:
        buf = BytesIO(initial_bytes=zf.read())
        mime = magic.from_buffer(buf.read(2048), mime=True)
        buf.seek(0)
        if mime != 'application/x-tar':
            data_fn(zf, name=filePath.absolute(),
                    date=datetime.utcfromtimestamp(filePath.stat().st_mtime), **kwargs)
            return
        with tarfile.open(mode='r|', fileobj=BytesIO(initial_bytes=buf.read())) as tf:
            while m:= tf.next():
                if m.isfile():
                    ef = BytesIO(initial_bytes=tf.extractfile(m).read())
                elif just_files:
                    ef = None
                    continue
                data_fn(data=ef, name=m.name, date=datetime.utcfromtimestamp(m.mtime), **kwargs)


def download_file(url: str, to: Path, timeout=200) -> Path | None:
    rsp = requests.get(url, timeout=600, stream=True)
    rsp.raise_for_status()
    with open(to, 'wb') as f:
        total = 0
        LOG.info(f"downloading: {to.parts[-1]} {total}M")
        for data in rsp.iter_content(chunk_size=None, decode_unicode=False):
            f.write(data)
            total += len(data)
            LOG.info(f"downloading: {to.parts[-1]} {total/1024**2}M")
    return to


RE_EXT = re.compile(r'(?P<ext>\.(txt|csv|zip|tar|tgz|txz|tar\.[a-z]+))$').pattern
RE_YEAR = re.compile(r'(?P<year>\d{4}\b)').pattern
RE_BORN = re.compile(r'(?P<born>\d{4}[_.-]\d{2}[_.-]\d{2}\b)').pattern
RE_COUNTY = re.compile(r'(?P<county>\d{3}|ALL|Statewide)').pattern
RE_TABLENAME = re.compile(r'(?P<table_name>\w+)(?: File)?').pattern

REX = {
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


def path_info(filepath: Path) -> Info | None:
    """ Given a path to a file or directory, describe what's in it """
    county: int | str
    table: TableName
    born: datetime

    table_map: dict[re.Pattern, TableName] = {
        re.compile('\bcancel', re.I): TableName.cancelled,
        re.compile('\bNCOA\b'): TableName.address,
        **{re.compile(rf'\b{t.name}\b', re.I): t for t in TableName},
    }

    for fn, pattern in REX.items():
        if not (m_str := fn(filepath)):
            continue
        if m := pattern.match(m_str):
            gd = m.groupdict()
            county = gd.get('county', '') or ''
            county = int(county) if county and county.isdigit() else 0
            table_name = gd.get('table_name')
            if tables := list(filter(lambda p: p[0].search(table_name), table_map.items())):
                table = tables[0][1]
            else:
                continue
            born = parser.parse(re.sub(r'[_.-]', '-', gd.get('born', '')))
            return Info(table.name, born, county)
    raise ValueError(f"{str(filepath)} didn't match anything")

def repack(f: Path, data_dir: Path, do_del: bool = True):
    nfo = path_info(f)
    LOG.info(f"{f.relative_to(Data_Dir)} - {nfo}")
    if to := get_hierarchy(f, nfo):
        print(f"{f.relative_to(Data_Dir)} -> {to.relative_to(Data_Dir)}")
        del_to = extract(f, to, data_dir)
        try:
            pack(to, nfo=nfo)
            parquet(to, nfo=nfo)
        except Exception as e:
            raise e
        finally:
            if del_to and do_del:
                rm_temp_files(del_dir=to)
    else:
        raise RuntimeError(f"failed to get_heirarchy for {f}")


def extract_7z(f: Path, to: Path, data_dir: Path = None) -> bool:
    data_dir = data_dir or Data_Dir
    assert(f.exists())
    del_to_dir = not to.exists()
    to.mkdir(exist_ok=True)
    moved = []

    with TemporaryDirectory(dir=data_dir) as tmp:
        cmd_l = SevenZipEx + [f'-o{tmp}', f'{f.absolute()}']
        LOG.info(f"{f.relative_to(Data_Dir)} -unzip-> {tmp}")
        rv = subp_run(cmd_l, check=True, capture_output=True)
        if rv.returncode != 0:
            raise (RuntimeError(rv.stderr))
        LOG.info(f"{f.relative_to(Data_Dir)} -> {to.relative_to(Data_Dir)}")
        texts = list(Path(tmp).glob('**/*.txt')) or list(Path(tmp).glob('**/*.csv'))
        LOG.info(f"moving {len(texts)}... {texts[:4]}...")
        for f in texts:
            if 'MAP' in f.parts:
                continue
            moveP = to.joinpath(f.name)
            assert(moveP.exists() is False)
            LOG.info(f"Move: {f.relative_to(Data_Dir)} -> {moveP.relative_to(Data_Dir)}")
            f.rename(moveP)
            moved.append(moveP.name)

    pprint(f"Moved: {len(moved)} ======\n{moved[:4]}...")
    return del_to_dir

'''
@dataclass(slots=True)
class IOStack:
    fileobj: IOBase | None
    name: str | Path
    date: datetime | None
    mime: str | None
    alive: bool


class Sesame:
    def __init__(self, path: Path):
        self.stack: List[IOStack] = [IOStack(fileobj=None, name=path, date=datetime(path.stat().st_mtime), mime=None, alive=False]

    def open(self, mode='r'):
        pass

    def _open(self, stack: IOStack):
        """ Attempt to open the next inactive """
        if not self.magic:
            self.magic = magic.from_file(self.filepath, mime=True)

        match self.mime:
            case 'application/zstd':
                # consider zstandard.multi_decompress_to_buffer()
                zf = self.stack[0].fileobj = zstandard.open(filename=self.filepath, mode='rb')
                self.stack[0].mime = magic.from_buffer(buffer=zf, mime=True)
                zf.seek(0)

            case 'application/x-tar':
                with tarfile.open(fileobj=stack.fileobj, mode='r|') as tar:
                    while mbr := tar.next():
                        strBuf = StringIO(initial_value=tar.extractfile(mbr).read().decode())
                        fn(strBuf, **fn_args)

            case 'application/zip':
                pass

            case 'tar':
                pass
        return True

        with open()
'''