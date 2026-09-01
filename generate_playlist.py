import re
import urllib.request
from datetime import datetime
from pathlib import Path
import zoneinfo

INPUT_FILE = "movies.txt"
OUTPUT_FILE = "playlist.m3u"
M3U_URL = "https://raw.githubusercontent.com/sm-monirulislam/SM-Movie-Hup-Auto-Update/main/latest_movies.m3u"
GROUP_TITLE = "VOD"
DEVELOPER_NAME = "SM Network"


def get_current_time():
    try:
        tz = zoneinfo.ZoneInfo("Asia/Dhaka")
        now = datetime.now(tz)
    except Exception:
        now = datetime.now()
    return now.strftime("%d-%b-%Y %I:%M:%S %p (%Z)")


def generate_playlist():
    raw_blocks = []
    seen_urls = set()

    # ১. movies.txt পার্স করা
    txt_path = Path(INPUT_FILE)
    if txt_path.exists():
        lines = [
            line.strip()
            for line in txt_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        for i in range(0, len(lines), 3):
            if i + 2 >= len(lines):
                continue
            name, logo, url = lines[i], lines[i + 1], lines[i + 2]
            if url.startswith(("http://", "https://")) and url not in seen_urls:
                seen_urls.add(url)
                # b-cdn হলে রেফারার পাইপ যুক্ত করা
                if "b-cdn.net" in url or "fibwatch" in url:
                    stream_url = f"{url}|Referer=https://fibwatch.art/&User-Agent=Mozilla/5.0"
                    opt_line = "#EXTVLCOPT:http-referrer=https://fibwatch.art/"
                else:
                    stream_url = url
                    opt_line = ""

                extinf = f'#EXTINF:-1 tvg-logo="{logo}" group-title="{GROUP_TITLE}", {name}'
                raw_blocks.append((extinf, opt_line, stream_url))

    # ২. অনলাইন M3U ফেচ করা এবং হুবহু স্ট্রাকচার রেখে group-title পরিবর্তন করা
    try:
        req = urllib.request.Request(
            M3U_URL, headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            content = response.read().decode("utf-8")

        lines = content.splitlines()
        current_extinf = None
        current_opt = ""

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#EXTM3U"):
                continue

            if line.startswith("#EXTINF:"):
                # মূল লাইনের group-title="XYZ" অংশকে পরিবর্তন করে group-title="VOD" করা
                if "group-title=" in line:
                    fixed_extinf = re.sub(
                        r'group-title="[^"]*"',
                        f'group-title="{GROUP_TITLE}"',
                        line,
                    )
                else:
                    fixed_extinf = line.replace(
                        "#EXTINF:-1",
                        f'#EXTINF:-1 group-title="{GROUP_TITLE}"',
                    )
                current_extinf = fixed_extinf
                current_opt = ""

            elif line.startswith("#EXTVLCOPT:"):
                current_opt = line

            elif line.startswith(("http://", "https://")) and current_extinf:
                base_url = line.split("|")[0]
                if base_url not in seen_urls:
                    seen_urls.add(base_url)

                    # টিভি অ্যাপ ও স্ট্যান্ডার্ড প্লেয়ার উভয়ের জন্য ডাবল-হ্যান্ডলিং
                    if "b-cdn.net" in line and "|" not in line:
                        final_url = f"{line}|Referer=https://fibwatch.art/&User-Agent=Mozilla/5.0"
                    else:
                        final_url = line

                    if not current_opt and (
                        "b-cdn.net" in line or "fibwatch" in line
                    ):
                        current_opt = (
                            "#EXTVLCOPT:http-referrer=https://fibwatch.art/"
                        )

                    raw_blocks.append((current_extinf, current_opt, final_url))
                current_extinf = None
                current_opt = ""

    except Exception as e:
        print(f"Fetch Error: {e}")

    # ৩. ফাইনাল playlist.m3u তৈরি
    current_time_str = get_current_time()
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        f.write(f"# ==========================================\n")
        f.write(f"# Playlist Name : Premium VOD Movies\n")
        f.write(f"# Developer     : {DEVELOPER_NAME}\n")
        f.write(f"# Last Updated  : {current_time_str}\n")
        f.write(f"# Total Items   : {len(raw_blocks)}\n")
        f.write(f"# ==========================================\n\n")

        for extinf, opt, url in raw_blocks:
            f.write(f"{extinf}\n")
            if opt:
                f.write(f"{opt}\n")
            f.write(f"{url}\n\n")

    print(
        f"Playlist generated successfully with {len(raw_blocks)} items at {current_time_str}!"
    )


if __name__ == "__main__":
    generate_playlist()
