import re
import urllib.request
from datetime import datetime
from pathlib import Path
import zoneinfo  # বাংলাদেশ টাইমজোনের জন্য

INPUT_FILE = "movies.txt"
OUTPUT_FILE = "playlist.m3u"
M3U_URL = "https://raw.githubusercontent.com/sm-monirulislam/SM-Movie-Hup-Auto-Update/main/latest_movies.m3u"
GROUP_TITLE = "VOD"
DEVELOPER_NAME = "FARABI AHMED / SM Network"  # আপনার নাম বা ব্র্যান্ড নাম দিন
DEFAULT_REFERRER = "https://fibwatch.art/"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
)


def get_current_time():
    try:
        tz = zoneinfo.ZoneInfo("Asia/Dhaka")
        now = datetime.now(tz)
    except Exception:
        now = datetime.now()
    return now.strftime("%d-%b-%Y %I:%M:%S %p (%Z)")


def generate_playlist():
    entries = []
    seen_urls = set()

    # ১. movies.txt ফাইল থেকে কাস্টম এন্ট্রি রিড করা
    txt_path = Path(INPUT_FILE)
    if txt_path.exists():
        print(f"Reading custom movies from {INPUT_FILE}...")
        lines = [
            line.strip()
            for line in txt_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

        for i in range(0, len(lines), 3):
            if i + 2 >= len(lines):
                continue

            name = lines[i]
            logo = lines[i + 1]
            url = lines[i + 2]

            if url.startswith(("http://", "https://")) and url not in seen_urls:
                referrer = (
                    DEFAULT_REFERRER
                    if ("b-cdn.net" in url or "fibwatch" in url)
                    else ""
                )
                entries.append((name, logo, url, referrer))
                seen_urls.add(url)

    custom_count = len(entries)

    # ২. GitHub থেকে M3U প্লেলিস্ট আনা এবং হেডার সংরক্ষণ করা
    print("Fetching online movies from GitHub...")
    req = urllib.request.Request(
        M3U_URL, headers={"User-Agent": DEFAULT_USER_AGENT}
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            content = response.read().decode("utf-8")

        lines = content.splitlines()
        current_name = None
        current_logo = ""
        current_referrer = DEFAULT_REFERRER

        for line in lines:
            line = line.strip()
            if not line:
                continue

            if line.startswith("#EXTINF:"):
                logo_match = re.search(r'tvg-logo="([^"]*)"', line)
                current_logo = logo_match.group(1) if logo_match else ""
                current_name = line.split(",")[-1].strip()
                current_referrer = DEFAULT_REFERRER

            elif line.startswith("#EXTVLCOPT:http-referrer="):
                current_referrer = line.split("=", 1)[1].strip()

            elif line.startswith(("http://", "https://")) and current_name:
                if line not in seen_urls:
                    entries.append(
                        (current_name, current_logo, line, current_referrer)
                    )
                    seen_urls.add(line)
                current_name = None
                current_logo = ""

    except Exception as e:
        print(f"Warning: Could not fetch from GitHub ({e})")

    # ৩. হেডার ও টাইমস্ট্যাম্পসহ playlist.m3u ফাইল তৈরি করা
    current_time_str = get_current_time()

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        # প্রফেশনাল হেডার ব্লক
        f.write("#EXTM3U\n")
        f.write(f"# ==========================================\n")
        f.write(f"# Playlist Name : Premium VOD Movies\n")
        f.write(f"# Developer     : {DEVELOPER_NAME}\n")
        f.write(f"# Last Updated  : {current_time_str}\n")
        f.write(f"# Total Movies  : {len(entries)}\n")
        f.write(f"# ==========================================\n\n")

        for name, logo, url, referrer in entries:
            f.write(
                f'#EXTINF:-1 tvg-logo="{logo}" group-title="{GROUP_TITLE}",{name}\n'
            )
            if referrer:
                f.write(f"#EXTVLCOPT:http-referrer={referrer}\n")
                f.write(f"#EXTVLCOPT:http-user-agent={DEFAULT_USER_AGENT}\n")
            f.write(f"{url}\n\n")

    print(f"\nSuccess! '{OUTPUT_FILE}' has been generated.")
    print(f"Updated At: {current_time_str}")
    print(
        f"Total entries: {len(entries)} (Custom: {custom_count}, GitHub: {len(entries) - custom_count})"
    )


if __name__ == "__main__":
    generate_playlist()
