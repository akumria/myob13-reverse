# MYOB v13 → ERPNext

Reverse-engineering notes and working tools for migrating a
**MYOB Accounting v13 (Australia, Release 7.0.1C, 2002/2003)** company file
into [ERPNext](https://frappe.io/erpnext).

MYOB v13 is long out of support. There is no export path to a modern
open-source ledger, and the vendor's product was built on a proprietary ISAM
engine that nobody outside the company still has documentation for. This
repository documents what that file format actually is, and ships Python tools
that read it directly — no MYOB installation, no Windows, no vendor drivers.

> **No sample data is included.** No `.dat` company files, no binaries from the
> MYOB installer, no customer records. Every artefact stays local. See
> [Data and licensing](#data-and-licensing).

---

## The short version

| Question | Answer |
|---|---|
| Is the company file encrypted? | **No.** Data is plaintext. |
| Is the file password protecting the data? | **No.** It is an application-level gate on *operations*. |
| What is the storage engine? | **FairCom c-tree Plus VMS**, not a custom format. |
| Is a vendor driver required? | **No.** The format is parseable in pure Python. |
| Can the master password be read? | **Yes**, trivially — it is plaintext behind a 4-byte additive key. |
| Is the schema knowable? | **Yes.** The file is self-describing. |

---

## Why this repository exists

A business needed to move off MYOB v13 onto ERPNext. The blockers were:

1. The file is not self-evidently readable. It is a binary ISAM database
   from 2002 with no public documentation.
2. The company file is password protected and the password was unknown,
   so the owner could not even open it in the MYOB UI to check their own data.
3. Even once open, there is no supported export that ERPNext can consume.

This repository answers all three, and documents the evidence, so the findings
are checkable rather than merely asserted.

---

## What we found

### 1. MYOB v13 is FairCom c-tree Plus, not a custom format

This was the pivotal discovery. MYOB v13 ships a complete c-tree Plus runtime:

- `ctmyob32.dll` — *"MYOB Record Manager"*. Its 208 exports *are* c-tree's
  own API: `ctree`, `ctuseg`, `cttseg`, `InitCtreeGV`, `SetCtreeGV`,
  `ViewCtreeError`, plus the classic record ops (`WRTREC`, `REDREC`, `ADDREC`,
  `NXTREC`, `OPNFIL`, `CREIDX`) and `ctSETENCRYPT`. Internally it carries
  `Copyright (c) 1984-1998 FairCom Corporation` and `c-tree Plus(R)`.
- `MYOBSp32.dll` — MYOB's *Data Manager* layer on top: `DMOpenDataFile`,
  `DMNewRecord`, `DMReadRecord`, `DMBuildKey`, `DMFirstRecord`,
  `DMGetDODANameList`, `DMSetCountryCode`. Every export has a `_Name@N` stdcall
  alias, so argument counts come for free (`_DMBuildKey@20` = 5 arguments).

c-tree's DODA (Data Object Definition Array) is the schema, which is why
`DMGetDODANameList` exists and why FairCom's `ctinfo` utility — whose entire job
is "retrieves IFIL and DODA structures from a FairCom DB file" — does exactly
what we ended up doing.

MYOB does **not** use c-tree's file encryption. `MYOBSp32.dll` imports none of
`ctSETENCRYPT`, `SECURITY`, `SERIALNUM` or `CTUSER`. (For completeness,
`ctSETENCRYPT` decompiles to `FUN_100057de(0x1c6)` — a dispatcher call passing
raw-function index 470, i.e. FairCom's own optional feature, not MYOB code.)

### 2. A company file is a folder of per-table ISAM files

The file begins with a self-describing catalogue listing its own members:

```
C:\PREMIER7\tutorial.prm      <- company preferences
  misc.dat  addr.dat  alpha.dat  auto.dat  cal.dat  cards.dat
  cacc.dat  cmnt.dat  contc.dat  tran.dat  curcy.dat  mtg.dat
  hist.dat  line.dat  inv.dat   cptxt.dat items.dat  jcash.dat
  job.dat   log.dat    memo.dat  disc.dat
```

Newer single-file companies consolidate this into one large `.dat`.

### 3. The schema is embedded in the file

35 record types are recoverable, including the ones an accounting migration
needs: `ChtAcctRec` (chart of accounts, 68 fields), `ItemsRec` (73),
`CTranRec` (transaction header, 41), `CardRec` (customers/suppliers, 32),
`InvRec` (35), `ILRec` (transaction lines, 24), `JobRec` (108).

The encoding took some working out:

- Field names are length-prefixed Pascal strings where the declared length is
  `strlen(name) + 2`.
- The record type follows in a `FE FE` resource record as a fixed-width name
  field ending in c-tree's `Z` name marker — `MiscRecZ`, `CardRecZ`.
- **Field names and their `*RecZ` marker can be ~18 KB apart.** Association is
  therefore *ordinal*: merge-join the k-th field-name run with the k-th marker.
- MYOB's own typo is preserved verbatim (`Foruth_Address` in `CardRec`) — a
  useful authenticity signal that this is the real schema and not a guess.

### 4. Record framing

Records are located by the c-tree `FA FA` mark (`FE FE` = resource):

```
<FA FA> <len1:u32> <len2:u32> <len3:u32> ... per-class header ...
```

with `len1 - len2 == 18`. The payload starts after a per-class header carrying
the index key, whose length varies by record class, so it is auto-tuned per
class (observed 0x18–0x28). Fields inside the payload are NUL-terminated strings
interleaved with fixed binary values — **not** purely NUL-delimited, which was
confirmed by token-count analysis (counts clustered at 37/41/40/31, not at the
schema field counts).

### 5. The master password is plaintext

MYOB v13 uses a master password + sub-passwords system. Per MYOB's own
shipped help:

> *"You can have only one master password in a single company file."*
> *"Click Edit. The Set Up Passwords window appears, **displaying the password**."*

It gates *operations* — delete a sale, print cheques, payroll, Easy Setup — not
data access, which is why the file reads fine without it.

The password is stored **in plaintext**, obfuscated with a fixed 4-byte
additive key:

```
stored[i] = (plaintext[i] + KEY[i % 4]) & 0xFF
KEY       = 8D 96 9D 95
```

The key is a compile-time constant in the two Borland-compiled MYOB modules —
**`myob.exe`** (`.data`, four copies at VA `0x7A8AF0`) and **`myobsbt.dll`**
(`.data`, one copy at VA `0x1005E21C`). It is *not* in `MYOBSp32.dll`. It is
independent of the company name — it recovers the same way from two
differently-named companies. Addition, not XOR.
It is an arbitrary literal, not a crypto constant: it matches no hash of any
MYOB-related string and is not readable text in any 8-bit codepage.

It lives in a class-2, 706-byte `FA FA` record at offset `+0x62`, NUL-terminated.
The same record holds the sub-password list (empty in the file examined, so the
master password grants full access).

MYOB's "Create Backup" does not include this. A real 22 MB backup archive
(382 entries) contained the `.dat` plus the user's template folder — 229 `.xlt`
Excel export templates, 87 `.frm` forms, 8 `.rpt`, images — and **no `.prm` and no
`.ini` at all**.

---

## How we validated

Reproducibility matters more than confidence here, so each claim is tied to
evidence that can be re-checked.

The schema — validated on two independent companies. The MYOB v13 installer
ships two sample companies (`tutorial.dat`, `Clearwtr.dat`). Running the
extractor over both yields *identical* record-type sets and *identical field
lists for every record* — 35 types, zero differences. Two unrelated files
agreeing exactly is strong evidence the parser is reading structure rather than
pattern-matching noise.

The password — validated by controlled differential. The decisive step was
creating the *same* company twice: once with no password, once with a known
master password. Both files are byte-identical in size and differ in only 1,149
bytes across 180 regions. Exactly one region is a 706-byte `FA FA` record that is
pure `ff` (never written) in the unprotected file. The key was read off directly
by subtracting known plaintext from stored bytes, not guessed, and then located in
the binary: a 4-byte literal held as a plain string constant in the `.data`
section of `myob.exe` (VA `0x7A8AF0`, four copies) and `myobsbt.dll` (VA
`0x1005E21C`, one copy), driving Borland-compiled `add`/`sub` loops indexed by
`i mod 4` — two encrypt and two decrypt in the executable, one guarded class method
in the DLL. The tool is then
validated 4/4: it recovers the known password from the protected file, and
correctly reports the unprotected file *and* both shipped sample companies as
having no password.

Decoding traps are documented rather than hidden. Two bugs produced
confident-looking nonsense and are recorded in the code comments so the next
person does not repeat them:

1. The stored form is NUL-terminated, so you must truncate at the first raw
   `0x00` **before** decoding. Decoding a run of NULs wraps into the printable
   string `sjcksjcksjc...` (since `0x00 - 0x8D = 0x73 = 's'`), which floods the
   output with false positives.
2. `len1 == 706 && class == 2` is *not* unique — about 32 unrelated records in
   the real file match that shape — so a minimum password length is required.

Negative results are recorded too. We checked for MD5, SHA-1, SHA-256, DES,
Blowfish and CRC-32 constants across `myob.exe`, `ctmyob32.dll`, `MYOBSp32.dll`
and `myobsbt.dll` and found none. We initially misread c-tree's collating
sequences as an obfuscation alphabet; that was wrong and is corrected in the
notes. Both instances are left in the write-up.

---

## Tools used

| Tool | Version | Role |
|---|---|---|
| [REA](https://rea.tools/) | 6.5.0 | Evidence-oriented RE CLI wrapping Rizin/Ghidra |
| Ghidra | 12.1.4 PUBLIC | Disassembly/decompilation |
| Eclipse Temurin JDK | 21.0.12.1 LTS | Ghidra needs a full JDK (the system JREs had no `javac`) |
| Python | 3.14.8 | All parsing and extraction |
| `pefile` | — | PE section/import/export inspection |
| `msitools` / `7z` | — | Unpacking the MSI installer cabinet |

These are installed **outside the repository** except where noted: REA comes from
`npm i -g rea-agents` (`~/.local/lib/node_modules/rea-agents`), and Ghidra, the
Temurin JDK, the MYOB v13 installer and the Ghidra project live in the gitignored
`tools/` directory. Only their install archives are kept — run
`scripts/extract.sh` to unpack any of them. See
[MYOB-v13-reverse-engineering.md](MYOB-v13-reverse-engineering.md) §7 for exact paths.

The 6.7 MB `myob.exe` is a Borland C++ Builder / Delphi binary — the linker
emits one PE section per unit, and the unit names map straight onto the business
domain:

```
Analysis .text Analysis ARAP1Cod ARAP2Cod ARAP3Cod ARAP4Cod
CardCode ChartCod CheckCod InvCodeS PayrollD PayrollE PayrollE
PayrollW .rdata .data .rsrc
```

`ARAP1-4` are Accounts Receivable/Payable. Borland toolchain output decompiles
considerably better than hand-written C++.

### Working method

REA's evidence-based CLI was the core instrument. Example:

```bash
rea analyze ctmyob32.dll --format json
rea function ctSETENCRYPT --address 0x1000569c --format json
rea decompile --procedure 0x1000569c
```

`snapshot` files made repeated queries cheap against the 6.7 MB binary, and
Ghidra ran headless (`analyzeHeadless`) with a small Python `postScript` for
string cross-reference hunting.

---

## Repository contents

| File | Purpose |
|---|---|
| `MYOB-v13-reverse-engineering.md` | Full technical write-up: architecture, format, schema decoding, record framing, password scheme, validation notes |
| `MYOB-v13-finder.md` | How to obtain an authentic MYOB v13 build, with a byte-verified About-box match |
| `myob13_schema.py` | Extract the 35 record types from a company `.dat` |
| `myob13_schema.json` | The extracted schema (field name lists per record type) |
| `myob13_password.py` | Recover the master password |
| `myob13_extract.py` | Low-level record walker and payload dumper |
| `myob13_to_erpnext.py` | Records → JSON/CSV, plus an ERPNext-tagged import payload |
| `myob13_customers.py` | Build a customer/supplier master from card records |

### Usage

These are plain scripts taking positional arguments — no flags, no dependencies
beyond the standard library.

```bash
# record schema (prints to stdout)
python3 myob13_schema.py company.dat

# master password
python3 myob13_password.py company.dat

# every record -> JSON + CSV, plus the ERPNext-tagged payload
python3 myob13_to_erpnext.py company.dat out [limit_per_class]

# raw record dump grouped by class (useful when reverse-engineering)
python3 myob13_extract.py company.dat out.json [limit_per_class]

# customer/supplier master; writes company_customers.json / .csv
python3 myob13_customers.py company.dat
```

To regenerate the committed schema, use the library function rather than the CLI:

```python
from myob13_schema import to_json
to_json('company.dat', 'schema.json')
```

`myob13_password.py` is the exception — it also exposes `decode()` / `encode()`
and `find_passwords(data)` if you want to use it as a library.

### What ERPNext mapping looks like

The schema maps onto ERPNext with little translation:

| MYOB record | Meaning | ERPNext doctype |
|---|---|---|
| `CardRec` | Customers / suppliers | `Customer`, `Supplier` |
| `CTranRec` | Transaction header (`Amount`, `Card`, `Reference`, `Transaction_Date`, `Status`) | `Sales Invoice`, `Purchase Invoice`, `Payment Entry` |
| `ILRec` | Transaction line (`Quantity`, `Price`, `Discount`, `Parent` FK → `CTranRec`) | Sales/purchase child rows |
| `ChtAcctRec` | Ledger account (`Opening_Balance`, `Current_Balance`, `Activity00-112`) | `Account` |
| `ItemsRec`, `InvRec` | Inventory | `Item`, stock ledger |
| `JobRec` | Jobs | `Project` |

---

## Known limitations

Stated plainly, because a migration tool that oversells itself is worse than one
that does not finish:

- Field-level typing is heuristic. The per-field descriptor table (2×u16 per
  field, immediately before the field names) has been located but not fully
  aligned — one field measures 40 bytes where the table says 59. Numeric and date
  fields are therefore parsed heuristically rather than by declared type.
- Doctype tagging is heuristic. Records are classified by parsing free-text
  memo content. **Review before importing.**
- Addresses are sparse. Only a fraction of customers resolve to an address,
  because address text lives in a different record type that the current offset
  decode does not yet unlock. Customer *names* extract cleanly and completely.
- No write path. These tools read only. Producing a valid MYOB file is a
  separate problem.
- Sub-passwords are read, not validated against. The sub-password list lives
  after the master password in the same record; only the master was confirmed.

The single blocker for the first three is resolving the field-descriptor
alignment. Everything else is downstream of it.

---

## Data and licensing

- No MYOB files, installer payloads, or customer data are included in this
  repository. All analysis artefacts were kept outside version control.
- The recovered master password is redacted from this document. A real
  password recovered from a real company file should be treated as a live
  credential and rotated, not published.
- MYOB Accounting v13 is proprietary, unsupported software owned by MYOB
  Technology Pty Ltd. It is referenced here for interoperability and data
  portability. The analysis was performed on binaries the operator already had,
  to read their own accounting data.
- FairCom c-tree is © FairCom Corporation. The findings here were obtained by
  static analysis of MYOB's own binaries; no FairCom code is redistributed.

---

## How this was produced

This is **AI-assisted reverse engineering**. The analysis, toolchain setup,
scripting and write-up were performed by an AI coding agent — **OpenCode**
running the **`space-bunny-free`** model — driving REA, Ghidra and Python, with
a human supplying the objective, the domain context, the test files and the
judgement calls.

Stated explicitly because it affects how much you should trust it: the agent
generated the hypotheses and did the bytecode reading, which means **some
findings were wrong along the way** and were only caught because the validation
was built to be independent of the agent's own conclusions. The two documented
corrections — the misread collating sequences, and the `sjcksjck` false positive
— are left in place rather than tidied away.

**Verify against your own data before trusting any of it.** Every claim in this
README is tied to a specific, re-runnable check; the reproduction commands are in
`MYOB-v13-reverse-engineering.md`.

## License

Public domain, dedicated under [CC0 1.0 Universal](LICENSE).

To the extent possible under law, the authors have waived all copyright and
related or neighbouring rights to this work. The software is provided as-is,
without warranty of any kind.