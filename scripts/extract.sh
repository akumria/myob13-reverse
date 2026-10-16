#!/usr/bin/env bash
#
# Restore the extracted trees under tools/ from their preserved archives.
#
# Why this exists: tools/ is gitignored and local-only, and we keep the archives
# rather than their extracted contents to save disk. Everything here is
# idempotent -- each step is skipped if its target is already present.
#
# Usage (from the repository root):
#   scripts/extract.sh                  # restore everything that is missing
#   scripts/extract.sh myob13           # restore only the MYOB binaries
#   scripts/extract.sh --check          # report what is missing and the space needed
#   scripts/extract.sh ghidra jdk
#
# Components: ghidra, jdk, myob13
#
# Sizes when fully unpacked: ghidra 864M, jdk 344M, myob13 110M.
#
set -euo pipefail

TOOLS="$(cd "$(dirname "${BASH_SOURCE[0]}")/../tools" && pwd)"

# --check: report only, extract nothing
CHECK=0
if [ "${1:-}" = "--check" ]; then CHECK=1; shift; fi

# no component named -> restore all of them
if [ $# -eq 0 ]; then set -- ghidra jdk myob13; fi

# reject unknown components up front, before anything is unpacked
for c in "$@"; do
  case "$c" in ghidra|jdk|myob13) ;; *)
    echo "extract.sh: unknown component '$c' (ghidra|jdk|myob13)" >&2; exit 2 ;;
  esac
done

restore_ghidra() {
  local zip="$TOOLS/ghidra/ghidra.zip" dir="$TOOLS/ghidra/ghidra_12.1.4_PUBLIC"
  [ -f "$zip" ] || { echo "ghidra: missing $zip" >&2; return 1; }
  if [ -d "$dir" ]; then echo "ghidra: already extracted"; return 0; fi
  echo "ghidra: unpacking $(du -h "$zip" | cut -f1) -> 864M ..."
  unzip -q "$zip" -d "$TOOLS/ghidra"
  echo "ghidra: $dir"
}

restore_jdk() {
  local tar="$TOOLS/jdk21.tar.gz" dir="$TOOLS/jdk21"
  [ -f "$tar" ] || { echo "jdk: missing $tar" >&2; return 1; }
  if [ -x "$dir/bin/java" ]; then echo "jdk: already extracted"; return 0; fi
  echo "jdk: unpacking $(du -h "$tar" | cut -f1) -> 344M ..."
  mkdir -p "$dir"
  # the tarball's top level is jdk-21.0.12.1+1/; strip it so bin/ sits at $dir/bin
  tar xzf "$tar" -C "$dir" --strip-components=1
  echo "jdk: $dir  ($("$dir/bin/java" -version 2>&1 | head -1))"
}

restore_myob13() {
  local cab="$TOOLS/myob13-installer/Data1.cab" dir="$TOOLS/myob13-installer/cab"
  [ -f "$cab" ] || { echo "myob13: missing $cab" >&2; return 1; }
  if [ -f "$dir/myob.exe" ]; then echo "myob13: already extracted"; return 0; fi
  echo "myob13: unpacking $(du -h "$cab" | cut -f1) -> 110M (6,361 files) ..."
  7z x -y -o"$dir" "$cab" >/dev/null
  echo "myob13: $dir/myob.exe  sha256 $(sha256sum "$dir/myob.exe" | cut -c1-16)…"
}

# how many bytes will this run need on top of what is already unpacked?
# NOTE: must loop over the whole selection, not just $1 -- checking only the
# first argument under-reports and lets an over-large run start.
need=0
for c in "$@"; do
  case "$c" in
    ghidra) [ -d "$TOOLS/ghidra/ghidra_12.1.4_PUBLIC" ]        || need=$((need + 864 * 1024 * 1024)) ;;
    jdk)    [ -x "$TOOLS/jdk21/bin/java" ]                     || need=$((need + 344 * 1024 * 1024)) ;;
    myob13) [ -f "$TOOLS/myob13-installer/cab/myob.exe" ]      || need=$((need + 110 * 1024 * 1024)) ;;
  esac
done

avail=$(df -B1 --output=avail "$(dirname "$TOOLS")" | tail -1 | tr -d ' ')
if [ "$CHECK" -eq 1 ]; then
  echo "would unpack ~$((need / 1024 / 1024))M; free now $((avail / 1024 / 1024))M"
  exit 0
fi
if [ "$avail" -lt "$need" ]; then
  echo "extract.sh: not enough free space -- need ~$((need / 1024 / 1024))M, have $((avail / 1024 / 1024))M" >&2
  echo "extract.sh: free space first, or extract fewer components" >&2
  exit 1
fi

for c in "$@"; do
  case "$c" in
    ghidra) restore_ghidra ;;
    jdk)    restore_jdk ;;
    myob13) restore_myob13 ;;
  esac
done

cat <<'EOF'

To use Ghidra / REA afterwards:

  export GHIDRA_INSTALL_DIR="$PWD/tools/ghidra/ghidra_12.1.4_PUBLIC"
  export JAVA_HOME="$PWD/tools/jdk21"
EOF
