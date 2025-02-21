#!/usr/bin/python3

import pickle, csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path


PICKLE_FILENAME = "index.pickle"
OA_COMM_LICENSES = ['CC0', 'CC BY', 'CC BY-SA', 'CC BY-ND']
OA_NONCOMM_LICENSES = ['CC BY-NC', 'CC BY-NC-SA', 'CC BY-NC-ND']


@dataclass
class Entry:
    pmcid: int
    journal_id: str
    updated: date
    license: str


class FastIndex:
    def __init__(self, pmc: Path) -> list[Entry]:
        self.pmc = Path(pmc)
        with open(pmc / PICKLE_FILENAME , 'rb') as f:
            self.entries: list[Entry] = pickle.load(f)

    def path(self, e: Entry) -> Path:
        if e.license in OA_COMM_LICENSES:
            return self.pmc / f"oa_comm/xml/all/PMC{e.pmcid}.xml"
        return self.pmc / f"oa_noncomm/xml/all/PMC{e.pmcid}.xml"

    def load_strs(self, filename: str) -> list[str]:
        p = self.pmc / filename
        if p.exists():
            with open(p) as f:
                return [s.strip() for s in f.readlines()]
        return []

    def save_strs(self, filename: str, ss: set[str]) -> None:
        p = self.pmc / filename
        with open(p, 'w') as f:
            lines = sorted(ss)
            for l in lines:
                print(l, file=f)

    def journal_list_paths(self, filename: str) -> list[str]:
        ret = list()
        journals = self.load_strs(filename)
        for e in self.entries:
            if e.journal_id in journals:
                ret.append(self.path(e))
        return ret


def read_pmc_txt_filelist(p: Path, date_range) -> list[Entry]:
    ret = []
    with open(p) as f:
        reader = csv.DictReader(f, delimiter='\t')
        tot = 0
        for row in reader:
            if row['Retracted'] != "no":
                continue
            (key, updated) = list(row.items())[4]
            assert key.startswith('Last Updated')
            lic = row['License']
            if lic in OA_COMM_LICENSES + OA_NONCOMM_LICENSES:
                entry = Entry(
                    int(row['AccessionID'][3:]),
                    row['Article Citation'].split(sep='.', maxsplit=1)[0],
                    date.fromisoformat(updated[:10]),
                    lic,
                )
            if entry.updated >= date_range[0] and entry.updated < date_range[1]:
                ret.append(entry)
            tot += 1
        print(tot, "lines read.")
    return ret


def make_index(pmc: Path, begin: date, end: date):
    pickle_path = pmc / PICKLE_FILENAME
    assert not pickle_path.exists(), f"{pickle_path} already exists"
    entries = []
    oa_comm = pmc / "oa_comm/xml/metadata/txt/oa_comm.filelist.txt"
    if oa_comm.exists():
        entries += read_pmc_txt_filelist(oa_comm, (begin, end))
    oa_noncomm = pmc / "oa_noncomm/xml/metadata/txt/oa_noncomm.filelist.txt"
    if oa_noncomm.exists():
        entries += read_pmc_txt_filelist(oa_noncomm, (begin, end))
    with open(pickle_path, 'wb') as f:
        pickle.dump(entries, f)
