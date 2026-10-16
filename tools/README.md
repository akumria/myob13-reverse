# `tools/` — the local reverse-engineering workspace

**This directory is gitignored.** It holds roughly 810 MB of downloaded tooling,
MYOB's own binaries, and the raw output of the analysis runs. None of it is in
git, and none of it should be: it is large, it is redownloadable, and some of it
is third-party software you should fetch yourself rather than inherit from a
stranger's repository.

This README *is* tracked, so there is always a description of what belongs here.

---

## Why it exists

The work in [`MYOB-v13-reverse-engineering.md`](../MYOB-v13-reverse-engineering.md)
started in `/tmp`, which wiped the work on every reboot. It was moved here so it
survives. The scripts that operate on it are tracked in [`scripts/`](../scripts).

## The one rule: archives in, extracted trees out

The machine this was built on has a full disk, so only the **install archives**
are kept on disk. Their unpacked contents are not. `scripts/extract.sh` unpacks
whatever you need and is safe to re-run:

```sh
scripts/extract.sh --check          # what would it do, and how much space
scripts/extract.sh                  # unpack all three
scripts/extract.sh myob13           # just the MYOB binaries (110 MB)
scripts/extract.sh ghidra jdk myob13
```

It checks free space first and refuses to start a run that would fill the disk.
When it does run, it also prints the environment Ghidra needs:

```sh
export GHIDRA_INSTALL_DIR="$PWD/tools/ghidra/ghidra_12.1.4_PUBLIC"
export JAVA_HOME="$PWD/tools/jdk21"
```

---

## What lives here

| Path | Size | What it is | Unpacked to |
|---|---|---|---|
| `ghidra/ghidra.zip` | 544 M | Ghidra 12.1.4 PUBLIC | `ghidra/ghidra_12.1.4_PUBLIC/` (864 M) |
| `jdk21.tar.gz` | 198 M | Eclipse Temurin JDK 21.0.12.1 LTS | `jdk21/` (344 M) |
| `myob13-installer/Data1.cab` | 53 M | The MYOB Accounting v13 installer cabinet — 6,361 files | `myob13-installer/cab/` (110 M) |
| `myob13-installer/` | +8 M | The rest of the installer: `MYOB Accounting Plus v13.msi`, `setup.exe`, `install_guide.pdf`, `update/` | — |
| `rea/` | 1.9 M | Raw analysis output: `gh-*.log`, `*-analyze.json`, schema dumps, `help_myob.txt` | — |
| `misc/` | 5.7 M | Deliberately untracked; see below | — |

### `myob13-installer/cab/` — the binaries under analysis

Unpacking `Data1.cab` yields the whole MYOB v13 program. The four files that
matter here:

| File | Role |
|---|---|
| `myob.exe` | Main UI application. Borland C++ Builder, 6.7 MB. **Holds the password key** — four copies at VA `0x7A8AF0` — and the encrypt/decrypt loops. sha256 `f53e2190…f539c35` |
| `myobsbt.dll` | MYOB business-tools DLL. **Holds the same key** once, at VA `0x1005E21C`, driving one guarded decrypt method at VA `0x1000E6D0` |
| `ctmyob32.dll` | FairCom c-tree Plus VMS storage engine — the actual ISAM database |
| `MYOBSp32.dll` | MYOB Data Manager (`DM*` record API) layer on top of c-tree |

Check an unpacked copy is the right one with:

```sh
sha256sum tools/myob13-installer/cab/myob.exe
# f53e2190872c3d2f8046b7384139a80002939bf0e71e137d7eaf68d7cf539c35
```

### `rea/` — analysis output

Not reproducible without redoing the analysis, but also not needed to read the
documentation. Kept because it is the evidence behind the write-up.

- `gh-pw*.log`, `gh-headless.log` — Ghidra headless runs against `myob.exe`
- `*-analyze.json`, `*.snap` — REA function/analysis snapshots
- `clearwtr_schema.json`, `ctsetenc.json` — schemas decoded from c-tree tables
- `help_myob.txt`, `myob_cdx_*.txt` — MYOB's built-in help and collating sequences

### `misc/` — kept local on purpose

Two files here must **never** be committed, because they contain the personal
identifiers that were redacted from this repository's history:

- **`scrub.sh`** — the one-shot `git filter-branch --tree-filter` filter used to
  redact the publisher's name, email, address and customer names. Re-running it
  would also re-damage the already-clean text.
- **`myob-prefilter.bundle`** — a git bundle of the pre-redaction history, up to
  commit `337efaf`. Its earlier commits still contain those identifiers.

Also here: `magic-context/`, a scratch log from another tool.

---

## `rea` itself is not in here

The REA CLI is a normal npm global install, not a local workspace:

```sh
npm i -g rea-agents      # -> ~/.local/lib/node_modules/rea-agents (120 MB)
rea --version            # 6.5.0
```

---

## Disk notes

This workspace was assembled on a disk that was at 100% capacity, so a few things
are worth knowing:

- Unpacking **all three** components needs 1,318 MB. Check you have it first.
- You can only afford **one big extraction at a time** in practice — Ghidra alone
  is 864 MB.
- Everything here is regenerable from the archives except `rea/`. The Ghidra
  project that used to live at `tools/ghidra-project/` was deleted for the same
  reason: a fresh `analyzeHeadless` import of `myob.exe` rebuilds it in about
  five minutes.

## Related

- [`scripts/extract.sh`](../scripts/extract.sh) — unpack the archives
- [`scripts/find_xref.py`](../scripts/find_xref.py), [`scripts/FindXref.java`](../scripts/FindXref.java) — Ghidra post-scripts: find a string, list its references, decompile the callers
- [`README.md`](../README.md) — what this project does
- [`MYOB-v13-reverse-engineering.md`](../MYOB-v13-reverse-engineering.md) — the full write-up