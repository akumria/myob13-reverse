#!/usr/bin/env python3
"""Recover the MYOB v13 master password from a company .dat file.

MYOB Accounting v13 stores the master password in plaintext inside a
single c-tree data record, obfuscated with a fixed 4-byte additive key.
The key is a compile-time constant in MYOBSp32.dll -- it is NOT derived
from the company name or any file property (verified against two
differently-named companies).

Record layout (found at offset +0x00 of a class-2, 706-byte record):

    +0x00  fa fa              c-tree data record mark
    +0x02  u32 len1           706  (total record length)
    +0x06  u32 len2           688  (payload length)
    +0x0a  u32 class          2
    +0x62  ...password bytes...   additive key applied from phase 0 here

Obfuscation is addition modulo 256, NOT xor:

    stored[i] = (plaintext[i] + KEY[i % 4]) & 0xFF

Usage:
    myob13_password.py company.dat
"""

from __future__ import annotations

import re
import sys

KEY = (0x8D, 0x96, 0x9D, 0x95)
PASSWORD_OFFSET = 0x62
RECORD_LEN = 706
RECORD_CLASS = 2


def decode(blob: bytes) -> bytes:
    """Remove the MYOB additive key from a stored password blob."""
    return bytes((b - KEY[i % 4]) & 0xFF for i, b in enumerate(blob))


def encode(plain: bytes) -> bytes:
    """Apply the MYOB additive key."""
    return bytes((p + KEY[i % 4]) & 0xFF for i, p in enumerate(plain))


def iter_records(data: bytes):
    """Yield the offset of every c-tree data record of interest."""
    for m in re.finditer(b"\xfa\xfa", data):
        off = m.start()
        if off + 0x0E > len(data):
            return
        length = int.from_bytes(data[off + 2 : off + 6], "little")
        payload = int.from_bytes(data[off + 6 : off + 10], "little")
        klass = int.from_bytes(data[off + 10 : off + 14], "little")
        if length == RECORD_LEN and klass == RECORD_CLASS:
            yield off


def find_passwords(data: bytes, min_length: int = 4) -> list[tuple[int, str]]:
    """Return (record offset, password) for every master password found.

    Records that merely happen to carry a single non-NUL byte at the
    password offset produce one-character junk, so results shorter than
    `min_length` are rejected as coincidental.
    """
    found = []
    for off in iter_records(data):
        raw = data[off + PASSWORD_OFFSET : off + PASSWORD_OFFSET + 64]
        # The stored form is NUL terminated. Truncate BEFORE decoding --
        # decoding a run of NULs would produce the spurious string
        # "sjcksjcksjc..." because 0x00 - KEY wraps into printable bytes.
        end = raw.find(b"\x00")
        stored = raw if end < 0 else raw[:end]
        if not stored:
            continue
        plain = decode(stored)
        if len(plain) < min_length:
            continue
        if all(0x20 <= c < 0x7F for c in plain):
            found.append((off, plain.decode("ascii")))
    return found


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    path = argv[1]
    with open(path, "rb") as fh:
        data = fh.read()

    results = find_passwords(data)
    if not results:
        print(f"{path}: no master password found (file is not password protected)")
        return 1
    for off, password in results:
        print(f"{path}: master password @ {off:#x} -> {password!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))