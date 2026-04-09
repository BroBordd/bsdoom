#!/usr/bin/env python3
import sys
import base64
import re

if len(sys.argv) < 6:
    print("Usage: python3 pack_bsdoom.py <so_file> <wad_file> <sounds_file> <src_file> <out_file>")
    sys.exit(1)

so_file = sys.argv[1]
wad_file = sys.argv[2]
snd_file = sys.argv[3]
src_file = sys.argv[4]
out_file = sys.argv[5]

def process_asset(filename):
    print(f"[pack_bsdoom] Encoding {filename} ...")
    with open(filename, 'rb') as f:
        data = f.read()
    # b85encode matches the exact 5:4 compression ratio seen in your logs
    encoded = base64.b85encode(data).decode('ascii')
    print(f"[pack_bsdoom]   {len(data):,} bytes -> {len(encoded):,} base-85 chars")
    return encoded

# 1. Encode all three files
so_b85 = process_asset(so_file)
wad_b85 = process_asset(wad_file)
snd_b85 = process_asset(snd_file)

# 2. Read the source code
with open(src_file, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 3. Trim out any existing _ASSET_ definitions
clean_lines = []
for line in lines:
    # Ignores lines that start with _ASSET_SO, _ASSET_WAD, or _ASSET_SOUNDS
    if not re.match(r'^_ASSET_(SO|WAD|SOUNDS)\s*=', line):
        clean_lines.append(line)

clean_src = "".join(clean_lines).rstrip() + "\n\n"

# 4. Append the variables at the tail
print(f"[pack_bsdoom] Writing assets to tail of {out_file} ...")
with open(out_file, 'w', encoding='utf-8') as f:
    f.write(clean_src)
    f.write(f"_ASSET_SO = b'{so_b85}'\n")
    f.write(f"_ASSET_WAD = b'{wad_b85}'\n")
    f.write(f"_ASSET_SOUNDS = b'{snd_b85}'\n")

print("[pack_bsdoom] Success!")
