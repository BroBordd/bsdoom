# make_sounds.py
import os
import struct
import subprocess
import zipfile

WAD_FILE = "DOOM1.WAD"
ZIP_NAME = "sounds.zip"

def extract_and_convert():
    if not os.path.exists(WAD_FILE):
        print(f"Error: {WAD_FILE} not found!")
        return

    print(f"Reading {WAD_FILE}...")
    with open(WAD_FILE, "rb") as f:
        header = f.read(12)
        wad_type, num_lumps, dir_offset = struct.unpack("<4sII", header)

        f.seek(dir_offset)
        directory = []
        for _ in range(num_lumps):
            lump_offset, lump_size, lump_name_raw = struct.unpack("<II8s", f.read(16))
            name = lump_name_raw.split(b'\x00')[0].decode('ascii', errors='ignore')
            directory.append((name, lump_offset, lump_size))

    oggs = []
    for name, offset, size in directory:
        # DOOM sound lumps start with "DS"
        if name.startswith("DS") and size > 8:
            with open(WAD_FILE, "rb") as f:
                f.seek(offset)
                data = f.read(size)

            # DOOM DMX Sound Header:
            # Bytes 0-1: Format (always 3)
            # Bytes 2-3: Sample rate (uint16)
            # Bytes 4-7: Number of samples (uint32)
            magic, samplerate, numsamples = struct.unpack("<HHI", data[:8])

            # Sanity check to make sure it's actually an audio lump
            if magic != 3:
                continue

            # Strip the header and grab just the raw audio payload
            raw_audio = data[8: 8 + numsamples]

            raw_filename = f"{name}.raw"
            # Format to match our Python plugin (e.g. bsdoom_dspistol.ogg)
            ogg_filename = f"bsdoom_{name.lower()}.ogg"

            with open(raw_filename, "wb") as f:
                f.write(raw_audio)

            # Convert 8-bit unsigned PCM to OGG Vorbis using FFmpeg
            cmd = [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-f", "u8", "-ar", str(samplerate), "-ac", "1",
                "-i", raw_filename,
                "-c:a", "libvorbis", "-q:a", "4",
                ogg_filename
            ]
            
            try:
                subprocess.run(cmd, check=True)
                os.remove(raw_filename)
                oggs.append(ogg_filename)
                print(f"Converted: {name} ({samplerate} Hz) -> {ogg_filename}")
            except Exception as e:
                print(f"Failed to convert {name}: {e}")

    print(f"\nZipping {len(oggs)} sounds into {ZIP_NAME}...")
    with zipfile.ZipFile(ZIP_NAME, "w", zipfile.ZIP_DEFLATED) as zf:
        for ogg in oggs:
            zf.write(ogg)
            os.remove(ogg)  # Clean up the ogg file after zipping

    print("Done! You can now pack sounds.zip into your script.")

if __name__ == "__main__":
    extract_and_convert()
