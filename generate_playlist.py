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

    raw_content = txt_path.read_text(encoding="utf-8").strip()
    blocks = [b.strip() for b in raw_content.split("\n\n") if b.strip()]

    formatted_entries = []

    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue

        # ক্ষেত্র ১: যদি এন্ট্রিটি ইতিমধ্যে #EXTINF দিয়ে শুরু হয় (রেডিমেড M3U ফরম্যাট)
        if lines[0].startswith("#EXTINF:"):
            # group-title পরিবর্তন করে VOD করা
            if "group-title=" in lines[0]:
                extinf = re.sub(
                    r'group-title="[^"]*"',
                    f'group-title="{TARGET_GROUP}"',
                    lines[0],
                )
            else:
                extinf = lines[0].replace(
                    "#EXTINF:-1", f'#EXTINF:-1 group-title="{TARGET_GROUP}"'
                )

            # বাকি লাইনগুলো (যেমন #EXTVLCOPT এবং Video URL) যুক্ত করা
            rest_lines = "\n".join(lines[1:])
            formatted_entries.append(f"{extinf}\n{rest_lines}")

        # ক্ষেত্র ২: যদি এন্ট্রিটি সাধারণ ৩-লাইনের ফরম্যাট হয় (নাম, লোগো, URL)
        elif len(lines) >= 3:
            name = lines[0]
            logo = lines[1]
            url = lines[2]
            referrer = lines[3] if len(lines) >= 4 else None

            entry_str = f'#EXTINF:-1 tvg-logo="{logo}" group-title="{TARGET_GROUP}", {name}\n'
            if referrer:
                entry_str += f"#EXTVLCOPT:http-referrer={referrer}\n"
            entry_str += url
            formatted_entries.append(entry_str)

    current_time_str = get_current_time()

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        f.write("# ==========================================\n")
        f.write("# Playlist Name : Selected VOD Movies\n")
        f.write(f"# Developer     : {DEVELOPER_NAME}\n")
        f.write(f"# Last Updated  : {current_time_str}\n")
        f.write(f"# Total Items   : {len(formatted_entries)}\n")
        f.write("# ==========================================\n\n")

        for entry in formatted_entries:
            f.write(f"{entry}\n\n")

    print(
        f"Success! {len(formatted_entries)} items processed and saved to '{OUTPUT_FILE}'."
    )


if __name__ == "__main__":
    generate_playlist()
