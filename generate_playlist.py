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
        # HTML থেকে b-cdn.net এর বর্তমান অ্যাক্টিভ সাবডোমেইন খুঁজে বের করা
        match = re.search(r"https://([a-z0-9]+)\.b-cdn\.net", response.text)
        if match:
            subdomain = match.group(1)
            print(f"[*] Live CDN Subdomain Found: {subdomain}")
            return subdomain
    except Exception as e:
        print(f"[!] Subdomain fetch failed: {e}")

    # লাইভ সাবডোমেইন না পাওয়া গেলে স্ক্রিপ্ট থামিয়ে দেবে যাতে ভুল প্লেলিস্ট জেনারেট না হয়
    raise SystemExit("[-] Live subdomain could not be detected. Aborting build.")


def update_cdn_domain(text_block, active_subdomain):
    # যেকোনো পুরানো/ভিন্ন b-cdn সাবডোমেইনকে বর্তমান লাইভ সাবডোমেইন দিয়ে প্রতিস্থাপন করা
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

    # ১. সাইট থেকে বর্তমান অ্যাক্টিভ সাবডোমেইন রিড করা
    active_subdomain = get_active_subdomain()

    raw_content = txt_path.read_text(encoding="utf-8").strip()

    # ২. স্মার্ট ব্লকিং: যদি রেডিমেড M3U হয় তবে ফাঁকা লাইন ছাড়াই প্রতিটি #EXTINF কে আলাদা করবে
    if "#EXTINF:" in raw_content:
        raw_blocks = re.split(r"(?=#EXTINF:)", raw_content)
    else:
        # সাধারণ টেক্সটের ক্ষেত্রে আগের মতো ফাঁকা লাইনের নিয়ম বহাল থাকবে
        raw_blocks = re.split(r"\n\s*\n", raw_content)

    formatted_entries = []

    for block in raw_blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue

        # ক্ষেত্র ১: যদি এন্ট্রিটি #EXTINF দিয়ে শুরু হয় (রেডিমেড M3U ফরম্যাট)
        if lines[0].startswith("#EXTINF:"):
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

            rest_lines = "\n".join(lines[1:])
            # সাবডোমেইন লাইভ মান দিয়ে আপডেট করা
            rest_lines = update_cdn_domain(rest_lines, active_subdomain)
            formatted_entries.append(f"{extinf}\n{rest_lines}")

        # ক্ষেত্র ২: সাধারণ টেক্সট ফরম্যাট (লাইন ১: নাম, লাইন ২: লোগো, লাইন ৩: URL, লাইন ৪: রেফারার [ঐচ্ছিক])
        elif len(lines) >= 3:
            name = lines[0]
            logo = lines[1]
            # URL এর সাবডোমেইন আপডেট করা
            url = update_cdn_domain(lines[2], active_subdomain)
            referrer = lines[3] if len(lines) >= 4 else None

            entry_str = f'#EXTINF:-1 tvg-logo="{logo}" group-title="{TARGET_GROUP}", {name}\n'
            if referrer:
                entry_str += f"#EXTVLCOPT:http-referrer={referrer}\n"
            entry_str += url
            formatted_entries.append(entry_str)

    current_time_str = get_current_time()

    # ফাইনাল playlist.m3u ফাইল তৈরি
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        f.write("# ==========================================\n")
        f.write("# Playlist Name : Premium VOD Movies\n")
        f.write(f"# Developer     : {DEVELOPER_NAME}\n")
        f.write(f"# Last Updated  : {current_time_str}\n")
        f.write(f"# Active Subdomain : {active_subdomain}\n")
        f.write(f"# Total Movies  : {len(formatted_entries)}\n")
        f.write("# ==========================================\n\n")

        for entry in formatted_entries:
            f.write(f"{entry}\n\n")

    print(
        f"Success! {len(formatted_entries)} items saved to '{OUTPUT_FILE}' using subdomain '{active_subdomain}' at {current_time_str}."
    )


if __name__ == "__main__":
    generate_playlist()
