"""
Parse the site dump spreadsheet from Mallard and get nice stuff from it.

Requires:
    - programme.csv from programme
    - dump.csv from SitesDump
    - pfsa.csv from PFSA Expiry Dates
    - psa.csv from PSA Meetings
    - psa_aid.csv from Port and PSA_Scheduling_Aid
"""
import csv
import datetime
import re
from dataclasses import dataclass
from datetime import date
from typing import List

from dateutil.relativedelta import *

inspections_in_programme = []
presentable_inspections = []
LIST_OF_PORTS = []
INITIALS = ["KS", "PN", "SP", "ML", "SC", "DS", "WW", "GE", "TL", "PD", "AO"]
WEEKS = []
DATE_PATTERN = re.compile("^\d{1,2}\/\d{1,2}\/\d{2,4}$")


def parse_programme_date(date_string):
    dstring = date_string.split("/")
    return date.fromisoformat(
        "-".join([_convert_year_str(dstring[2]), dstring[1], dstring[0]])
    )


def _convert_year_str(year_str):
    if len(year_str) == 2:
        return f"20{year_str}"
    elif len(year_str) == 4:
        return year_str
    else:
        return year_str


class Inspection:
    def __init__(self, week_begining, inspection_data):
        self._inspection_data = inspection_data
        self.week_begining = parse_programme_date(week_begining)

    def __repr__(self):
        return [item[1] for item in self._inspection_data if item[0] == "Facility"][0]

    @property
    def facility(self):
        return [item[1] for item in self._inspection_data if item[0] == "Facility"][0]

    @property
    def location(self):
        return [item[1] for item in self._inspection_data if item[0] == "Location"][0]

    @property
    def inspectors(self):
        return [
            item[0]
            for item in self._inspection_data
            if item[1] == "X" and item[0] in INITIALS
        ]

    @property
    def comments(self):
        return [
            item[1] for item in self._inspection_data if item[0] == "Comments/Date"
        ][0]




def _get_header_key_from_csv(opened_csv):
    reader = csv.reader(opened_csv)
    for row in reader:
        if row[0] == "Week Comm":
            return row


@dataclass
class PresentableInspection:
    week_begining: str
    location: str
    facility: str
    inspectors: str
    comments: str
    pfsa_expiry: datetime.date
    pfsa_approval: datetime.date


@dataclass
class PSAMeeting:
    psa: str
    date: datetime.datetime
    pso: str
    comments: str
    comments_from_meeting: str
    inspectors: str
    psp_reviewed: bool
    psra_reviewed: bool
    minutes_held: bool


def _convert_str_to_bool(bstr):
    if bstr in ["TRUE", "True", "true", "YES", "yes", "Yes"]:
        return True
    elif bstr in ["FALSE", "False", "false", "No", "NO", "no"]:
        return False
    else:
        raise ValueError("Cannot recognise {bstr}".format(bst))


def _convert_datetime_str_to_datetime(dstr):
    "Must be of the form 14-05-2014 11:00"
    if not dstr:
        return ""
    year = int(dstr.split()[0].split("-")[2])
    month = int(dstr.split()[0].split("-")[1])
    day = int(dstr.split()[0].split("-")[0])
    hour = int(dstr.split()[1].split(":")[0])
    minute = int(dstr.split()[1].split(":")[1])
    return datetime.datetime(year, month, day, hour, minute)


def psa_meetings(csv_file) -> List[PSAMeeting]:
    psa_meetings_lst = []
    with open(csv_file, "r", encoding="ISO-8859-1") as csvfile:
        csv_reader = csv.DictReader(csvfile)
        for row in csv_reader:
            psa_meeting = PSAMeeting(
                row["PSA_Name"],
                _convert_datetime_str_to_datetime(row["MeetingDate"]),
                row["PSO"],
                row["Comments"],
                row["CommentsFromMeeting"],
                row["Inspectors"],
                _convert_str_to_bool(row["PSPReviewed"]),
                _convert_str_to_bool(row["PSRAReviewed"]),
                _convert_str_to_bool(row["MinutesHeld"])
            )
            psa_meetings_lst.append(psa_meeting)
    return psa_meetings_lst


def parse_programme(csv_file):
    """
    Parses the current programme spreadsheet.
    """
    current_week = ""

    pfsa_expiry_data_lst = list(parse_pfsa_csv("pfsa.csv"))

    with open(csv_file, "r", encoding="ISO-8859-1") as csvfile:
        csv_reader = csv.reader(csvfile)
        key = _get_header_key_from_csv(csvfile)
        for row in csv_reader:
            if re.match(DATE_PATTERN, row[0]):
                WEEKS.append(parse_programme_date(row[0]))
                inspection = Inspection(row[0], list(zip(key, row)))
                current_week = row[0]
                inspections_in_programme.append(inspection)
            elif row[0] == "":
                inspection = Inspection(current_week, list(zip(key, row)))
                inspections_in_programme.append(inspection)

        for inspection in inspections_in_programme:
            try:
                pfsa_expiry_entry = [x for x in pfsa_expiry_data_lst if x.site_name == inspection.facility.rstrip()][0]
                _pfsa_exp = pfsa_expiry_entry.pfsa_expiry_date
                _pfsa_apr = pfsa_expiry_entry.pfsa_approval_date
            except IndexError:
                _pfsa_exp = "NO PFSA EXPIRY DATA"
            pi = PresentableInspection(
                inspection.week_begining,
                inspection.location,
                inspection.facility,
                '|'.join(inspection.inspectors),
                inspection.comments.rstrip(),
                _pfsa_exp,
                _pfsa_apr
            )
            presentable_inspections.append(pi)
        for inspection in presentable_inspections:
            print(
                inspection.week_begining,
                f"{inspection.location:<10}",
                f"{inspection.facility:<50}",
                f"{inspection.inspectors:<10}",
                f"{inspection.comments:<40}",
                f"{inspection.pfsa_approval}",
                f"{inspection.pfsa_expiry}"
            )


class PortFromPFSARow:
    def __init__(self, row):
        self.site_name = row["SiteName"].strip()
        self.pfsa_approval_date = self.parse_date_string(row["PFSA Approval"])
        self.pfsa_expiry_date = self.parse_date_string(row["PFSA Expiry"])

    def parse_date_string(self, date_string):
        try:
            dstring = date_string.split()[0]
        except IndexError:
            return date(1900, 1, 1)
        year = dstring.split("-")[2]
        month = dstring.split("-")[1]
        day = dstring.split("-")[0]
        return date.fromisoformat("-".join([year, month, day]))


def parse_pfsa_csv(csv_file):
    "Parses the csv containing PFSA expiry data."
    list_of_ports = []
    try:
        with open(csv_file, "r", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                port = PortFromPFSARow(row)
                list_of_ports.append(port)
    except UnicodeDecodeError:
        # the file was made on Windoze
        with open(csv_file, "r", encoding="ISO-8859-1") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                port = PortFromPFSARow(row)
                list_of_ports.append(port)
    return sorted(list_of_ports, key=lambda x: x.pfsa_expiry_date)



class PortFromCSVRow:
    def __init__(self, row):
        self.site_name = row["SiteName"].strip()
        try:
            self.county = row["County"].strip()
        except KeyError:
            pass
        self.last_inspection_date = self.parse_date_string(row["DateOfLastInspection"])
        self.frequency_target = (
            row["FrequencyTarget"].strip() if row["FrequencyTarget"] else "XXXXX"
        )
        self.pfsi_category = row["SubCategoryDesc"].strip()
        self.site_category = row["SiteCategoryDesc"].strip()

    def parse_date_string(self, date_string):
        try:
            dstring = date_string.split()[0]
        except IndexError:
            return date(1900, 1, 1)
        year = dstring.split("-")[2]
        month = dstring.split("-")[1]
        day = dstring.split("-")[0]
        return date.fromisoformat("-".join([year, month, day]))

    def __repr__(self):
        return f"{self.site_name}: {self.pfsi_category}"



def parse_csv(csv_file):
    """
    Parses the csv file.
    """
    try:
        with open(csv_file, "r", encoding="utf-8") as csvfile:
            csv_reader = csv.DictReader(csvfile)
            for row in csv_reader:
                port = PortFromCSVRow(row)
                if row["SiteTypeDesc"] == "Port":
                    LIST_OF_PORTS.append(port)
    except UnicodeDecodeError:
        # the file was made on Windoze
        with open(csv_file, "r", encoding="ISO-8859-1") as csvfile:
            csv_reader = csv.DictReader(csvfile)
            for row in csv_reader:
                port = PortFromCSVRow(row)
                if row["SiteTypeDesc"] == "Port":
                    LIST_OF_PORTS.append(port)


def print_site_data_to_terminal(filename):
    parse_csv(filename)
    sorted_list = sorted(LIST_OF_PORTS, key=lambda port: port.last_inspection_date)
    for port in sorted_list:
        print(
            f"{port.site_name:<60} --- {port.county:<20} {port.pfsi_category:<10} {port.site_category:<10} {port.frequency_target:<5} {port.last_inspection_date}"
        )


# TODO check this
def week_port_is_in_programme(port):
    for p in LIST_OF_PORTS:
        if p.site_name == port:
            for inspection in inspections_in_programme:
                if port == inspection.facility:
                    print(port, inspection.week_begining)


def count_inspections_for_inspector(initials):
    count = 0
    for inspection in inspections_in_programme:
        if initials in inspection.inspectors:
            count += 1
    return count


def calculate_port_within_allowed_period(port):
    ft = int(port.frequency_target)
    last_insp = port.last_inspection_date
    calc = last_insp + relativedelta(months=+ft)
    in_prog = in_current_programme(port)
    print(f"{port.site_name:<60} -- Next inspection due: {calc} - {in_prog}.")


def in_current_programme(port):
    for p in inspections_in_programme:
        if p.facility == port.site_name:
            return (True, p.week_begining)
        else:
            continue
    return False


def print_port_inspection_expiry():
    for port in LIST_OF_PORTS:
        calculate_port_within_allowed_period(port)


def print_psa_meetings_from_date(date: datetime.date, comments=False):
    meetings = psa_meetings("psa_meetings.csv")
#   today = datetime.datetime.today()
    after_date = sorted([m for m in meetings if m.date > date], key=lambda x: x.date)
    for m in after_date:
        if comments:
            print(m.date, f"{m.psa:<20}", m.comments)
        else:
            print(m.date, f"{m.psa:<20}", m.inspectors)


@dataclass
class PSAData:
    psa: str
    pso: str
    psa_approval_date: datetime.datetime
    date_of_last_inspection: datetime.datetime
    due_inspection: datetime.datetime


def get_psa_assessment_data(csv_file):
    output = []
    with open(csv_file, "r", encoding="ISO-8859-1") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["SiteTypeDesc"] == "PSA":
                psa = PSAData(
                    row["SiteName"],
                    row["PSO"],
                    _convert_datetime_str_to_datetime(row["PortSecurityAssessmentApprovalDate"]),
                    _convert_datetime_str_to_datetime(row["DateOfLastInspection"]),
                    _convert_datetime_str_to_datetime(row["DateInspectionDue"])
                )
                output.append(psa)
    return output



def print_psa_assessment_data():
    psa_assessment_data = sorted(get_psa_assessment_data("psa_aid.csv"), key=lambda x: x.due_inspection)
    for psa in psa_assessment_data:
        print(
            f"{psa.psa:<32}",
            f"{psa.pso:<30}",
            f"due: {psa.due_inspection}"
        )



def main():
    """
    Main function.
    """
    print_psa_assessment_data()
#   print_psa_meetings_from_date(datetime.datetime(2019, 1, 1, 0, 0), comments=False)
#   parse_programme("programme.csv")
#   print_site_data_to_terminal("dump.csv")
#   print_port_inspection_expiry()
#   print("ML: ", count_inspections_for_inspector("ML"))
#   print("WW: ", count_inspections_for_inspector("WW"))
#   print("TL: ", count_inspections_for_inspector("TL"))
#   print("GE: ", count_inspections_for_inspector("GE"))
#   print("KS: ", count_inspections_for_inspector("KS"))
#   print("PN: ", count_inspections_for_inspector("PN"))
#   print("SC: ", count_inspections_for_inspector("SC"))
#   print("SP: ", count_inspections_for_inspector("SP"))


if __name__ == "__main__":
    main()
