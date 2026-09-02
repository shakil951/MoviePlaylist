from datetime import datetime
from pathlib import Path
import re
import zoneinfo
import requests

INPUT_FILE = "movies.txt"
OUTPUT_FILE = "playlist.m3u"
TARGET_GROUP = "VOD"
DEVELOPER_NAME = "FARABI"
BASE_CHECK_URL = "https://fibwatch.art/"


def get_active_subdomain():
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    try:
        response = requests.get(BASE_CHECK_URL, headers=headers, timeout=10)
        match = re.search(r"https://([a-z0-9]+)\.b-cdn\.net", response.text)
        if match:
            subdomain = match.group(1)
            print(f"[*] Live CDN Subdomain Found: {subdomain}")
            return subdomain
    except Exception as e:
        print(f"[!] Subdomain fetch failed: {e}")

    raise SystemExit("[-] Live subdomain could not be detected. Aborting build.")


def update_cdn_domain(text_block, active_subdomain):
    return re.sub(r"[a-z0-9]+\.b-cdn\.net", f"{active_subdomain}.b-cdn.net", text_block)


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

    active_subdomain = get_active_subdomain()
    raw_lines = txt_path.read_text(encoding="utf-8").splitlines()

    # কমেন্ট ফিল্টারিং
    lines = []
    for line in raw_lines:
        s = line.strip()
        if not s:
            continue
        if s.startswith("##") or (s.startswith("#") and not s.startswith("#EXT")):
            continue
        lines.append(s)

    formatted_entries = []
    i = 0
    total = len(lines)

    while i < total:
        current = lines[i]

        # ১. যদি রেডিমেড #EXTINF হয়
        if current.startswith("#EXTINF:"):
            if "group-title=" in current:
                extinf = re.sub(
                    r'group-title="[^"]*"',
                    f'group-title="{TARGET_GROUP}"',
                    current,
                )
            else:
                extinf = current.replace(
                    "#EXTINF:-1", f'#EXTINF:-1 group-title="{TARGET_GROUP}"'
                )

            entry_parts = [extinf]
            i += 1
            while i < total:
                line = lines[i]
                # পরের যেকোনো নতুন এন্ট্রি বা টেক্সট ব্লক পেলে থামবে
                if line.startswith("#EXTINF:"):
                    break
                # সাধারণ টেক্সটের সূচনা (পরের ২ লাইন যদি লিঙ্ক হয়) চিহ্নিত হলে থামবে
                if i + 2 < total and (lines[i+1].startswith("http://") or lines[i+1].startswith("https://")) and (lines[i+2].startswith("http://") or lines[i+2].startswith("https://")):
                    break

                # ডাবল রেফারার ফিক্স
                if line.startswith("#EXTVLCOPT:http-referrer="):
                    val = line.replace("#EXTVLCOPT:http-referrer=", "").replace("http-referrer=", "").strip()
                    entry_parts.append(f"#EXTVLCOPT:http-referrer={val}")
                else:
                    entry_parts.append(update_cdn_domain(line, active_subdomain))
                i += 1

            formatted_entries.append("\n".join(entry_parts))

        # ২. সাধারণ ৪/৩ লাইনের র' টেক্সট ব্লক (নাম -> ইমেজ -> ভিডিও URL -> রেফারার)
        elif i + 2 < total and (lines[i+1].startswith("http://") or lines[i+1].startswith("https://")) and (lines[i+2].startswith("http://") or lines[i+2].startswith("https://")):
            name = lines[i]
            logo = lines[i+1]
            url = update_cdn_domain(lines[i+2], active_subdomain)
            i += 3

            referrer = None
            if i < total and "http-referrer=" in lines[i]:
                referrer = lines[i].replace("http-referrer=", "").replace("#EXTVLCOPT:", "").strip()
                i += 1

            entry_str = f'#EXTINF:-1 tvg-logo="{logo}" group-title="{TARGET_GROUP}", {name}\n'
            if referrer:
                entry_str += f"#EXTVLCOPT:http-referrer={referrer}\n"
            entry_str += url
            formatted_entries.append(entry_str)

        else:
            i += 1

    current_time_str = get_current_time()

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        f.write("# ==========================================\n")
        f.write("# Playlist Name    : Premium VOD Movies\n")
        f.write(f"# Developer        : {DEVELOPER_NAME}\n")
        f.write(f"# Last Updated     : {current_time_str}\n")
        f.write(f"# Active Subdomain : {active_subdomain}\n")
        f.write(f"# Total Movies     : {len(formatted_entries)}\n")
        f.write("# ==========================================\n\n")

        for entry in formatted_entries:
            f.write(f"{entry}\n\n")

    print(f"Success! {len(formatted_entries)} items cleanly formatted.")


if __name__ == "__main__":
    generate_playlist()
