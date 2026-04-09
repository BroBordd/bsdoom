"""
pack_bsdoom.py

Encodes libdoomgeneric.so, a DOOM WAD file, and sounds.zip as base-85 blobs
and appends them to bsdoom_src.py, replacing the placeholder variables at
the bottom of the file. The result is written to a new file so the source
is never modified in place.

Usage:
    python3 pack_bsdoom.py <libdoomgeneric.so> <DOOM1.WAD> <sounds.zip> [src.py] [out.py]

Arguments:
    libdoomgeneric.so   Path to the compiled shared library.
    DOOM1.WAD           Path to the WAD file (DOOM1.WAD, doom.wad, etc.).
    sounds.zip          Path to the converted OGG audio zip.
    src.py              Source file to pack. Defaults to bsdoom_src.py.
    out.py              Output file. Defaults to src.py with _src removed,
                        e.g. bsdoom_src.py -> bsdoom.py.
"""

import base64
import os
import sys

SENTINEL_SO     = "_ASSET_SO  = None"
SENTINEL_WAD    = "_ASSET_WAD = None"
SENTINEL_SOUNDS = "_ASSET_SOUNDS = None"


def encode_file(path: str) -> bytes:
    """Read a binary file and return its base-85 encoded representation."""
    with open(path, "rb") as fh:
        return base64.b85encode(fh.read())


def pack(so_path: str, wad_path: str, sounds_path: str, src_path: str, dst_path: str) -> None:
    # Verify all input files exist
    files_to_check = [
        ("Shared library", so_path),
        ("WAD file", wad_path),
        ("Sounds ZIP", sounds_path),
        ("Source file", src_path)
    ]
    
    for label, path in files_to_check:
        if not os.path.exists(path):
            print(f"[pack_bsdoom] ERROR: {label} not found: {path}")
            sys.exit(1)

    # Encode Assets
    print(f"[pack_bsdoom] Encoding {so_path} ...")
    so_b85 = encode_file(so_path)
    print(f"[pack_bsdoom]   {os.path.getsize(so_path):,} bytes -> {len(so_b85):,} base-85 chars")

    print(f"[pack_bsdoom] Encoding {wad_path} ...")
    wad_b85 = encode_file(wad_path)
    print(f"[pack_bsdoom]   {os.path.getsize(wad_path):,} bytes -> {len(wad_b85):,} base-85 chars")

    print(f"[pack_bsdoom] Encoding {sounds_path} ...")
    sounds_b85 = encode_file(sounds_path)
    print(f"[pack_bsdoom]   {os.path.getsize(sounds_path):,} bytes -> {len(sounds_b85):,} base-85 chars")

    # Read Source
    with open(src_path, "r", encoding="utf-8") as fh:
        source = fh.read()

    # Check Sentinels
    for sentinel in (SENTINEL_SO, SENTINEL_WAD, SENTINEL_SOUNDS):
        if sentinel not in source:
            print(f"[pack_bsdoom] ERROR: Could not find asset sentinel variable '{sentinel}' in source file.")
            sys.exit(1)

    # Inject Assets
    source = source.replace(SENTINEL_SO, f"_ASSET_SO = {so_b85!r}")
    source = source.replace(SENTINEL_WAD, f"_ASSET_WAD = {wad_b85!r}")
    source = source.replace(SENTINEL_SOUNDS, f"_ASSET_SOUNDS = {sounds_b85!r}")

    # Write Output
    with open(dst_path, "w", encoding="utf-8") as fh:
        fh.write(source)

    print(f"[pack_bsdoom] Successfully written to {dst_path} ({os.path.getsize(dst_path):,} bytes)")


if __name__ == "__main__":
    args = sys.argv[1:]

    if len(args) < 3:
        print(__doc__)
        sys.exit(1)

    _so_path     = args[0]
    _wad_path    = args[1]
    _sounds_path = args[2]
    _src_path    = args[3] if len(args) > 3 else "bsdoom_src.py"
    _dst_path    = args[4] if len(args) > 4 else os.path.basename(_src_path).replace("_src", "")

    pack(_so_path, _wad_path, _sounds_path, _src_path, _dst_path)
