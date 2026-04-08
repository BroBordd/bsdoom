"""
pack_bsdoom.py

Encodes libdoomgeneric.so and a DOOM WAD file as base-85 and appends them
to bsdoom.py, replacing the two placeholder variables at the bottom of the
file.  The result is written to a new file so the original is never modified
in place.

Usage:
    python3 pack_bsdoom.py <libdoomgeneric.so> <DOOM1.WAD> [bsdoom.py] [output.py]

Arguments:
    libdoomgeneric.so   Path to the compiled shared library.
    DOOM1.WAD           Path to the WAD file (DOOM1.WAD, doom.wad, etc.).
    bsdoom.py           Source plugin file to pack into. Defaults to bsdoom.py.
    output.py           Destination file. Defaults to bsdoom_packed.py.
"""

import base64
import os
import sys


SENTINEL_SO  = "_ASSET_SO  = None"
SENTINEL_WAD = "_ASSET_WAD = None"


def encode_file(path: str) -> bytes:
    """Read a binary file and return its base-85 encoded representation."""
    with open(path, "rb") as fh:
        return base64.b85encode(fh.read())


def pack(so_path: str, wad_path: str, src_path: str, dst_path: str) -> None:
    for label, path in [("shared library", so_path), ("WAD", wad_path), ("source", src_path)]:
        if not os.path.exists(path):
            print(f"[pack_bsdoom] ERROR: {label} not found: {path}")
            sys.exit(1)

    print(f"[pack_bsdoom] Encoding {so_path} ...")
    so_b85 = encode_file(so_path)
    print(f"[pack_bsdoom]   {os.path.getsize(so_path):,} bytes -> {len(so_b85):,} base-85 chars")

    print(f"[pack_bsdoom] Encoding {wad_path} ...")
    wad_b85 = encode_file(wad_path)
    print(f"[pack_bsdoom]   {os.path.getsize(wad_path):,} bytes -> {len(wad_b85):,} base-85 chars")

    with open(src_path, "r", encoding="utf-8") as fh:
        source = fh.read()

    if SENTINEL_SO not in source or SENTINEL_WAD not in source:
        print(
            "[pack_bsdoom] ERROR: Could not find asset sentinel variables in source file.\n"
            f"  Expected: '{SENTINEL_SO}' and '{SENTINEL_WAD}'"
        )
        sys.exit(1)

    source = source.replace(
        SENTINEL_SO,
        f"_ASSET_SO  = {so_b85!r}",
    )
    source = source.replace(
        SENTINEL_WAD,
        f"_ASSET_WAD = {wad_b85!r}",
    )

    with open(dst_path, "w", encoding="utf-8") as fh:
        fh.write(source)

    print(f"[pack_bsdoom] Written to {dst_path}  ({os.path.getsize(dst_path):,} bytes)")


if __name__ == "__main__":
    args = sys.argv[1:]

    if len(args) < 2:
        print(__doc__)
        sys.exit(1)

    so_path  = args[0]
    wad_path = args[1]
    src_path = args[2] if len(args) > 2 else "bsdoom.py"
    dst_path = args[3] if len(args) > 3 else "bsdoom_packed.py"

    pack(so_path, wad_path, src_path, dst_path)
