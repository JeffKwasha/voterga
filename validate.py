import logging
from typing import Iterable
from argparse import ArgumentParser
from pathlib import Path
from contest import ElectionResult
from tabulator import Tabulator, load_tabulators
from openpyxl import Workbook
from util import first

class Report:
    """ printable data holder """
    def __init__(self, args):
        if args.errors:
            args.report_level = logging.ERROR
        elif args.warnings:
            args.report_level = logging.WARN
        elif args.info:
            args.report_level = logging.INFO
        self.report_level = args.report_level
        self.dir_tabulator = Path(args.tabulator_dir).expanduser()
        self.dir_election_results = Path(args.election_results_xml).expanduser()
        self.election_results = {}
        self.tabulators = {}
        self.results = {}

    def load(self, args):
        results = self.results
        xml_paths: list = args.results_xml.glob('*.xml') if args.results_xml.is_dir() else [args.results_xml]
        for xml_file in xml_paths:
            er = ElectionResult.load_from_xml(filename=xml_file)
            results[(er.Region, er.ElectionDate)] = er
            results[xml_file] = er

        load_tabulators(self.dir_tabulator)
        self.tabulators = Tabulator._all

    @property
    def name(self):
        er: ElectionResult = self.election_results.values()[0]
        return f"{er.ElectionDate.date().isoformat()}:{er.ElectionName}:{er.Region}"

    @classmethod
    def get_args(cls, ap: ArgumentParser):
        ap.add_argument('--errors -e', description='report errors, but not warnings')
        ap.add_argument('--warnings -w', description='report warnings, but not info/debug')
        ap.add_argument('--info -i', description='report info, but not debug')
        ap.add_argument('--debug -d', description='report everything')
        ap.add_argument('--report_level -r', type=int, description='set report level specifically')
        ap.add_argument('--tabulator_dir -t', type=str, description='directory of tabulator receipts', default='.')
        ap.add_argument('--election_results_xml -x', type=str, description='Election results xml file/directory', default='.')

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
        # return giant formatted string?
        return f"{self.name}, {len(self.tabulators)}"

    def validate(self) -> Iterable:
        """ Validate all records, and return results as rows
            row = dict: name, report_level, description, records
        """
        tabulator_results = {}  # by location, where a location refer to a set of tabulator_results
        precincts = Tabulator.by_location(self.tabulators.values())
        for tabulator in self.tabulators.values():
            precinct = tabulator.location
            # Each tabulator has a location - a precinct

        return {}


def get_args():
    ap = ArgumentParser(prog=__file__, description='validates an ElectionResult against Tabulator receipts')
    Report.get_args(ap)
    return ap.parse_args()


def main():
    args = get_args()

    # do validation
    # for each tabulator location, find


if __name__ == '__main__':
    main()