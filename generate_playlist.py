import re
from datetime import datetime
from pathlib import Path
import zoneinfo

INPUT_FILE = "movies.txt"
OUTPUT_FILE = "playlist.m3u"
TARGET_GROUP = "VOD"
DEVELOPER_NAME = "SM Network"


def get_current_time():
    try:
        tz = zoneinfo.ZoneInfo("Asia/Dhaka")
        now = datetime.now(tz)
    except Exception:
        now = datetime.now()
    return now.strftime("%d-%b-%Y %I:%M:%S %p (%Z)")


def generate_playlist():
    txt_path = Path(INPUT_FILE)
    if not txt_path.exists():
        print(f"Error: {INPUT_FILE} not found!")
        return

    content = txt_path.read_text(encoding="utf-8")
    lines = content.splitlines()

    processed_lines = []
    item_count = 0

    for line in lines:
        stripped = line.strip()

        # #EXTM3U হেডার থাকলে বাদ দেওয়া (যেহেতু উপরে নতুন হেডার তৈরি হবে)
        if stripped.startswith("#EXTM3U"):
            continue

        # শুধু #EXTINF লাইনের group-title পরিবর্তন করা
        if stripped.startswith("#EXTINF:"):
            item_count += 1
            if "group-title=" in stripped:
                new_line = re.sub(
                    r'group-title="[^"]*"',
                    f'group-title="{TARGET_GROUP}"',
                    stripped,
                )
            else:
                new_line = stripped.replace(
                    "#EXTINF:-1", f'#EXTINF:-1 group-title="{TARGET_GROUP}"'
                )
            processed_lines.append(new_line)
        else:
            # বাকি সব লাইন (যেমন #EXTVLCOPT, URL, ফাঁকা লাইন) হুবহু যেমন আছে তেমন থাকবে
            processed_lines.append(stripped)

    current_time_str = get_current_time()

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        f.write("# ==========================================\n")
        f.write("# Playlist Name : Selected VOD Movies\n")
        f.write(f"# Developer     : {DEVELOPER_NAME}\n")
        f.write(f"# Last Updated  : {current_time_str}\n")
        f.write(f"# Total Items   : {item_count}\n")
        f.write("# ==========================================\n\n")

        # প্রসেস করা লাইনগুলো ফাইলে লেখা
        for line in processed_lines:
            f.write(f"{line}\n")

    print(
        f"Success! {item_count} items processed and saved to '{OUTPUT_FILE}'."
    )


if __name__ == "__main__":
    generate_playlist()
