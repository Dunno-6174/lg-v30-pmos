#!/bin/bash
# Build a flashable boot.img from a linux-lg-joan apk (or a bare vmlinuz),
# using the known-good pmOS ramdisk + cmdline stored next to this script.
#
# usage: ./mkboot.sh <linux-lg-joan-*.apk | vmlinuz> <out.img> [extra-cmdline]
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="${1:?usage: mkboot.sh <apk|vmlinuz> <out.img> [extra-cmdline]}"
OUT="${2:?output image path}"
EXTRA="${3:-}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

case "$SRC" in
  *.apk)
    tar xzf "$SRC" -C "$TMP" 2>/dev/null || true
    KERNEL="$TMP/boot/vmlinuz"
    ;;
  *)
    KERNEL="$SRC"
    ;;
esac

CMD="$(cat "$HERE/cmdline.txt")"
[ -n "$EXTRA" ] && CMD="$CMD $EXTRA"

# sanity: the ramdisk must be a gzip'ed cpio
python3 - "$HERE/ramdisk-real.gz" <<'PY'
import sys, zlib
b = open(sys.argv[1], "rb").read()
out = zlib.decompressobj(16 + zlib.MAX_WBITS).decompress(b)
assert b"070701" in out[:100000], "ramdisk is not a cpio archive!"
PY

mkbootimg --kernel "$KERNEL" --ramdisk "$HERE/ramdisk-real.gz" \
  --base 0x00000000 --kernel_offset 0x00008000 --ramdisk_offset 0x01000000 \
  --second_offset 0x00f00000 --tags_offset 0x00000100 --pagesize 4096 \
  --cmdline "$CMD" -o "$OUT"
ls -l "$OUT"
