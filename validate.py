"""
Reporting:
- load all the data
- validate each
- search for incongruities
- output errors, warnings, etc based on report_level

Problems:
- Race name matching...
    - an ElectionResult contains races = Fields({raceName: Race})

Race:
    _races: Fields()
  name: Name
  candidates
  vote_types ?
  precincts ?


- Candidate name matching: Candidate.race[name] should hold/match names
    - but Candidate needs to match Tabulator results as well... hmmm
    - Need a Race:{candidates, counties, etc?}


"""
import logging
from pathlib import Path
from typing import Iterable
from argparse import ArgumentParser
from sos.contest import ElectionResult, Fields
from tabulator import Tabulator, load_tabulators
from openpyxl import Workbook
from util import LogSelf


class Report(LogSelf):
    """ printable data holder
    Validate:
    - tabulators are valid (? time, reasonable counts, )
    - SOS (ElectionResult) precinct votes must match tabulators
    - ??
    """
    def __init__(self, args, load=True):
        if args.errors:
            args.report_level = logging.ERROR
        elif args.warnings:
            args.report_level = logging.WARN
        elif args.info:
            args.report_level = logging.INFO
        self.report_level = args.report_level
        self.dir_results = Path(args.sos_results_xml).expanduser().absolute()
        self.dir_tabulator = Path(args.tabulator_dir).expanduser().absolute() if args.tabulator_dir else self.dir_results
        self.dir_top = min(self.dir_results, self.dir_tabulator, key=lambda p: len(str(p)))
        self.election_result: ElectionResult = None
        self.tabulators = {}        # {(county, date, name): Tabulator}
        self.results = {}           # {(county, date):       ElectionResult}
        if load:
            self.load(args=args)

    def load(self, args):
        results = self.results
        field_files = args.results_xml.glob('*.yml') if not args.fields_yml else [Path(args.fields_yml).expanduser()]
        for file in field_files:
            Fields(name=file.stem, filename=file)

        xml_paths: list = args.results_xml.glob('*.xml') if args.results_xml.is_dir() else [args.results_xml]
        for xml_file in xml_paths:
            er = ElectionResult.load_from_xml(filename=xml_file)
            results[(er.Region, er.ElectionDate)] = er
            results[xml_file] = er

        self._tabulators_by_file = load_tabulators(self.dir_tabulator)
        for li in self._tabulators_by_file.values():
            self.tabulators.update(li)

    @property
    def name(self):
        er: ElectionResult = self.election_result
        return f"{er.ElectionDate.date().isoformat()}:{er.ElectionName}:{er.Region}"

    @classmethod
    def get_args(cls, ap: ArgumentParser):
        ap.add_argument('--errors -e', description='report errors, but not warnings')
        ap.add_argument('--warnings -w', description='report warnings, but not info/debug')
        ap.add_argument('--info -i', description='report info, but not debug')
        ap.add_argument('--debug -d', description='report everything')
        ap.add_argument('--report_level -r', type=int, description='set report level specifically')
        ap.add_argument('--tabulator_dir -t', type=str, description='directory of tabulator receipts', default=None)
        ap.add_argument('--sos_results_xml -x', type=str, description='Election results xml file/directory', default='.')
        ap.add_argument('--fields_yml -f', type=str, description='fields file', default=None)
        ap.add_argument('--output -o', type=str, description='Output file path', default='./report.xlsx')

    @property
    def _rows(self) -> Iterable:
        return filter(lambda r: r.level > self.report_level, self.validate())

    def save_xlsx(self, filename: str = 'tabulator_report.xlsx'):
        from openpyxl.worksheet.worksheet import Worksheet
        # save into an excel file with formatting / colors / etc
        wb = Workbook(iso_dates=True)
        ws: Worksheet = wb.create_sheet(f"{self.name}", index=1)
        ws.append(self._rows)
        wb.save(filename=filename)

    def __str__(self):
        # return giant formatted string?... nah
        return f"{self.name}, {len(self.tabulators)}"

    def validate(self) -> Iterable:
        """ Validate all records, and return results as rows
            row = dict: name, report_level, description, records
        """
        tabulator_results = {}  # by location, where a location refer to a set of tabulator_results
        precincts = Tabulator.by_location(self.tabulators)
        set(precincts.keys()).difference(self.election_result._precincts)
        #for tabulator in self.tabulators.values():
        #    precinct = tabulator.location
            # Each tabulator has a location - a precinct

        #_all_precincts = self.election_result._precincts
        ## TODO - check location differences between sources
        tab: Tabulator = None
        for tab in self.tabulators:
            for loc in tab.locations:
                if loc not in self.election_result._precincts:
                    self.error(msg=f'Precinct {loc} Not Found in ElectionResult', category='missing')

        return self.errors(report_level=self.report_level)


def get_args():
    ap = ArgumentParser(prog=__file__, description='validates an ElectionResult against Tabulator receipts')
    Report.get_args(ap)
    return ap.parse_args()


def main():
    args = get_args()
    report = Report(args=args, load=True)
    report.validate()
    report_filename = Path(args.output).expanduser()
    if report_filename.is_absolute() and not report_filename.parent.exists():
        report_filename.parent.mkdir(mode=0o770, parents=True, exist_ok=True)
    report.save_xlsx(filename=args.output)


if __name__ == '__main__':
    main()
