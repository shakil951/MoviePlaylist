from datetime import datetime
from pathlib import Path
import zoneinfo

INPUT_FILE = "movies.txt"
OUTPUT_FILE = "playlist.m3u"
GROUP_TITLE = "VOD"
DEVELOPER_NAME = "FARABI AHMED SHAKIL"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


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

    # প্রতিটি মুভি ব্লককে আলাদা করা (ফাঁকা লাইন দিয়ে আলাদা করা ব্লক)
    raw_content = txt_path.read_text(encoding="utf-8").strip()
    movie_blocks = [
        block.strip() for block in raw_content.split("\n\n") if block.strip()
    ]

    entries = []

    for block in movie_blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) < 3:
            continue

        name = lines[0]
        logo = lines[1]
        url = lines[2]

        # যদি ৪র্থ লাইনে কোনো রেফারার দেওয়া থাকে
        referrer = lines[3] if len(lines) >= 4 else None

        if url.startswith(("http://", "https://")):
            entries.append((name, logo, url, referrer))

    current_time_str = get_current_time()

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        f.write("# ==========================================\n")
        f.write("# Playlist Name : Selected VOD Movies\n")
        f.write(f"# Developer     : {DEVELOPER_NAME}\n")
        f.write(f"# Last Updated  : {current_time_str}\n")
        f.write(f"# Total Movies  : {len(entries)}\n")
        f.write("# ==========================================\n\n")

        for name, logo, url, referrer in entries:
            f.write(
                f'#EXTINF:-1 tvg-logo="{logo}" group-title="{GROUP_TITLE}", {name}\n'
            )
            if referrer:
                f.write(f"#EXTVLCOPT:http-referrer={referrer}\n")
                f.write(f"#EXTVLCOPT:http-user-agent={USER_AGENT}\n")
                f.write(f"{url}|Referer={referrer}&User-Agent={USER_AGENT}\n\n")
            else:
                f.write(f"{url}\n\n")

    print(f"Success! {len(entries)} movies generated in '{OUTPUT_FILE}'.")


if __name__ == "__main__":
    generate_playlist()
