#!/usr/bin/env python3
"""Extract the MYOB v13 company-file schema from the c-tree VMS catalogue.

The v13 .dat file embeds a self-describing catalogue. For each per-table data
file it stores a set of length-prefixed identifier strings (Pascal strings),
terminated by a record-type name whose c-tree name marker is a trailing 'Z',
e.g. the fields of MiscRec followed by "MiscRecZ".
"""
import re
import sys
from collections import OrderedDict

PATH_RE = re.compile(rb'[A-Za-z]:\\[ -~]{0,240}?\.(?:prm|dat)(?:\x00|!)')
NAME_RE = re.compile(rb'^[A-Za-z][A-Za-z0-9_]{1,39}$')
RECTYPE_RE = re.compile(rb'([A-Z][A-Za-z0-9]{1,20}Rec)Z')   # c-tree name marker 'Z'
RECORD_MARK = b'\xfe\xfe'                                 # c-tree record start
GAP = 4096      # max bytes between two strings of the same logical field list
LOOKAHEAD = 8192   # how far past a field-name run to look for its record type


def pascal_strings(data):
    """Yield (offset, value) for every length-prefixed identifier in data.

    c-tree stores DODA field names as a length byte followed by the name, but
    the declared length counts 2 extra bytes for the field's type marker, so
    the real name length is ``declared - 2``.
    """
    i, n = 0, len(data)
    while i < n:
        declared = data[i]
        ln = declared - 2
        if 1 <= ln <= 40 and i + 1 + ln <= n and NAME_RE.match(data[i + 1:i + 1 + ln]):
            yield i, data[i + 1:i + 1 + ln].decode('ascii')
            i += 1 + ln
        else:
            i += 1


def runs(items):
    """Group (offset, value) items into runs separated by > GAP bytes."""
    out, cur = [], []
    for off, val in items:
        if cur and off - cur[-1][0] > GAP:
            out.append(cur)
            cur = []
        cur.append((off, val))
    if cur:
        out.append(cur)
    return out


def parse(path, verbose=True):
    data = open(path, 'rb').read()
    anchors = [(m.start(), m.group()[:-1].decode('ascii', 'replace'))
               for m in PATH_RE.finditer(data)]
    table_at = {}
    for off, a in anchors:
        table_at.setdefault(off, a.rsplit('\\', 1)[-1])

    # Layout is ordinal, not proximate: the length-prefixed field names for a
    # table appear first, and its FE FE record carrying the *RecZ name can be
    # tens of KB later. The two sequences are in matching order, so merge-join
    # the k-th field-name run with the k-th record-type name.
    runs_ = [r for r in runs(list(pascal_strings(data))) if len(r) >= 2]
    types = [(m.start(), m.group(1).decode('ascii'))
             for m in RECTYPE_RE.finditer(data)]

    schema = OrderedDict()
    for run, (toff, rectype) in zip(runs_, types):
        fields = [v for _, v in run]
        start = run[0][0]
        table = next((a.rsplit('\\', 1)[-1].rsplit('!', 1)[-1]
                      for off, a in sorted(table_at.items(), reverse=True) if off <= start),
                     '?')
        prev = schema.get(rectype)
        if prev and len(prev[1]) >= len(fields):
            continue
        schema[rectype] = (table, fields)

    if verbose:
        print(f'{path}: {len(data):,} bytes, {len(anchors)} path anchors, '
              f'{len(runs_)} field runs, {len(types)} record types, '
              f'{len(schema)} matched\n')

    if verbose:
        print(f'{path}: {len(data):,} bytes, {len(anchors)} path anchors, '
              f'{len(schema)} record types\n')
        for rectype, (table, fields) in schema.items():
            print(f'--- {rectype}  ({table})  {len(fields)} fields')
            for i in range(0, len(fields), 6):
                print('      ' + ', '.join(fields[i:i + 6]))
            print()
    return schema


if __name__ == '__main__':
    parse(sys.argv[1] if len(sys.argv) > 1 else 'tutorial.dat')


def to_json(path, out):
    import json
    sch = parse(path, verbose=False)
    doc = {rt: {'source_file': t, 'fields': f} for rt, (t, f) in sch.items()}
    with open(out, 'w') as fh:
        json.dump(doc, fh, indent=2)
    print(f'wrote {out}: {len(doc)} record types')
