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
from typing import Iterable, Set
from argparse import ArgumentParser
from ga.contest import ElectionResult, Fields
from tabulator import Tabulator, load_tabulators
from openpyxl import Workbook
from util import LogSelf, first, ErrorKey, dict_sum, dict_diff


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
        self.report_level = args.report_level if type(args.report_level) is int else logging.INFO
        self.dir_results = Path(args.sos_results_xml).expanduser().absolute()
        self.dir_tabulator = Path(args.tabulator_dir).expanduser().absolute() if args.tabulator_dir else self.dir_results
        self.dir_top = min(self.dir_results, self.dir_tabulator, key=lambda p: len(str(p)))
        self.tabulators = {}        # {(county, date, name): Tabulator}
        self.results = {}           # {(county, date):       ElectionResult}
        if load:
            self.load(args=args)

    def load(self, args):
        results = self.results
        field_files = self.dir_results.glob('*.yml') if not args.fields_yml else [Path(args.fields_yml).expanduser()]
        for file in field_files:
            Fields(key=file.stem, filename=file)

        xml_paths: list = self.dir_results.glob('*.xml') if self.dir_results.is_dir() else [self.dir_results]
        for xml_file in xml_paths:
            er = ElectionResult.load_from_xml(filename=xml_file)
            results[(er.Region, er.ElectionDate)] = er
            results[xml_file] = er

        self._tabulators_by_file = load_tabulators(self.dir_tabulator)
        for li in self._tabulators_by_file.values():
            self.tabulators.update({v._key: v for v in li})
        return None

    @property
    def name(self):
        er: ElectionResult = first(self.results.values())
        return f"{er.ElectionDate.date().isoformat()}.{er.ElectionName}.{er.Region}"

    @classmethod
    def get_args(cls, ap: ArgumentParser):
        ap.add_argument('--errors', '-e', help='report errors, but not warnings')
        ap.add_argument('--warnings', '-w', help='report warnings, but not info/debug')
        ap.add_argument('--info', '-i', help='report info, but not debug')
        ap.add_argument('--debug', '-d', help='report everything')
        ap.add_argument('--report_level', '-r', type=int, help='set report level specifically')
        ap.add_argument('--tabulator_dir', '-t', type=str, help='directory of tabulator receipts', default=None)
        ap.add_argument('--sos_results_xml', '-x', type=str, help='Election results xml file/directory', default='.')
        ap.add_argument('--fields_yml', '-f', type=str, help='fields file', default=None)
        ap.add_argument('--output', '-o', type=str, help='Output file path', default='./report.xlsx')

    def save_xlsx(self, filename: Path, report_level=None, **kwargs):
        report_level = report_level if type(report_level) is int else self.report_level
        from openpyxl.worksheet.worksheet import Worksheet
        # save into an excel file with formatting / colors / etc
        wb = Workbook(iso_dates=True)
        wb.remove_sheet(wb.active)

        def add_tab(_name, obj: LogSelf, level=report_level):
            ws: Worksheet = wb.create_sheet(f"{_name}", index=1)
            errors = obj.errors(report_level)
            ws.append(ErrorKey._fields + ('description(s)',))
            for errkey, desc in errors.items():
                ws.append((*errkey, *list(desc)))

        if self not in kwargs.values():
            kwargs[self.name] = self

        for name, v in kwargs.items():
            add_tab(name, v)

        filename = filename if filename.is_absolute() else self.dir_top.joinpath(filename)
        if not filename.parent.exists():
            filename.parent.mkdir(mode=0o770, parents=True, exist_ok=True)
        wb.save(filename=filename)

    def __str__(self):
        # return giant formatted string?... nah
        return f"{self.name}, {len(self.tabulators)}"

    def validate_locations(self, er_precincts, tabulators):
        def get_diff(a, b):
            return set(filter(lambda v: type(v) is not tuple, set(a).difference(b)))
        missing_locations = get_diff(er_precincts, tabulators)
        for loc in missing_locations:
            self.info(msg=f'location: {loc} not found in tabulator receipts',
                      category='missing tabulator(s)', who=f'precinct:{loc}')
        return missing_locations

    def validate_races(self, er_precincts, tabs_by_loc):
        # for loc in er_precincts tab = tabs_by_loc[loc]
        # loc = tab.locations
        # if len(loc) > 1:
        #    tab = tabs_by_loc[loc]
        # results[loc] = sum = {}
        # [dict_sum(sum, t.races) for t in tab]
        tabs: Set[Tabulator] = set()
        for set_of_tabs in tabs_by_loc.values():
            tabs.update(set_of_tabs)

        tab_totals_by_loc = {}
        for tab in tabs:
            loc = tab.locations
            tab_totals_by_loc[loc] = loc_total = {}
            for tab_at_loc in tabs_by_loc[loc]:
                dict_sum(loc_total, tab_at_loc.races)

        for locs in tab_totals_by_loc.keys():
            # sum er_precincts[loc]
            # compare, and report
            pass

    def validate(self, report_level=None) -> Iterable:
        """ Validate all records, and return results as rows
            row = dict: name, report_level, description, records
        """
        report_level = self.report_level if report_level is None else report_level
        tabulator_results = {}  # by location, where a location refer to a set of tabulator_results
        tabulators = Tabulator.by_location(self.tabulators.values())
        er_precincts = first(self.results.values())._precincts

        self.validate_locations(er_precincts, tabulators)
        self.validate_races(er_precincts, tabulators)

        return self.errors(report_level=report_level)


def get_args():
    ap = ArgumentParser(prog=__file__, description='validates an ElectionResult against Tabulator receipts')
    Report.get_args(ap)
    return ap.parse_args()


def main():
    args = get_args()
    report = Report(args=args, load=True)
    result = report.validate()
    report_filename = Path(args.output).expanduser()
    report.save_xlsx(filename=report_filename)
    from pprint import pformat
    logging.info(f"Results:\n{pformat(result)}\n====== End of Results ======")


if __name__ == '__main__':
    main()
