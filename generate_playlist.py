import re
import urllib.request
from pathlib import Path

INPUT_FILE = "movies.txt"
OUTPUT_FILE = "playlist.m3u"
M3U_URL = "https://raw.githubusercontent.com/sm-monirulislam/SM-Movie-Hup-Auto-Update/main/latest_movies.m3u"
GROUP_TITLE = "VOD"


def generate_playlist():
    entries = []
    seen_urls = set()  # ডুপ্লিকেট মুভি/লিঙ্ক আটকানোর জন্য

    # ১. প্রথমে লোকাল movies.txt ফাইল থেকে কাস্টম মুভিগুলো রিড করা
    txt_path = Path(INPUT_FILE)
    if txt_path.exists():
        print(f"Reading custom movies from {INPUT_FILE}...")
        lines = [line.strip() for line in txt_path.read_text(encoding="utf-8").splitlines() if line.strip()]

        # ৩ লাইন করে পার্স করা (Name, Logo, URL)
        for i in range(0, len(lines), 3):
            if i + 2 >= len(lines):
                print(f"Skipping incomplete entry in {INPUT_FILE} starting at line {i + 1}")
                continue

            name = lines[i]
            logo = lines[i + 1]
            url = lines[i + 2]

            if not url.startswith(("http://", "https://")):
                print(f"Invalid URL in {INPUT_FILE}: {url}")
                continue

            if url not in seen_urls:
                entries.append((name, logo, url))
                seen_urls.add(url)
        print(f"Added {len(entries)} movies from {INPUT_FILE}.")
    else:
        print(f"{INPUT_FILE} not found. Skipping local entries.")

    custom_count = len(entries)

    # ২. এরপর GitHub থেকে অনলাইন M3U প্লেলিস্ট আনা
    print("Fetching online movies from GitHub...")
    req = urllib.request.Request(M3U_URL, headers={"User-Agent": "Mozilla/5.0"})

    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            content = response.read().decode("utf-8")

        lines = content.splitlines()
        current_extinf = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            if line.startswith("#EXTINF:"):
                logo_match = re.search(r'tvg-logo="([^"]*)"', line)
                logo = logo_match.group(1) if logo_match else ""
                name = line.split(",")[-1].strip()
                current_extinf = (name, logo)

            elif line.startswith(("http://", "https://")) and current_extinf:
                name, logo = current_extinf
                # যদি লিঙ্ক আগে অ্যাড না হয়ে থাকে
                if line not in seen_urls:
                    entries.append((name, logo, line))
                    seen_urls.add(line)
                current_extinf = None

        print(f"Added {len(entries) - custom_count} movies from GitHub.")

    except Exception as e:
        print(f"Warning: Could not fetch from GitHub ({e}). Only local movies will be saved.")

    # ৩. সব মুভি নিয়ে ফাইনাল playlist.m3u ফাইল তৈরি করা
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n\n")
        for name, logo, url in entries:
            f.write(f'#EXTINF:-1 tvg-logo="{logo}" group-title="{GROUP_TITLE}",{name}\n')
            f.write(f"{url}\n\n")

    print(f"\nSuccess! '{OUTPUT_FILE}' has been generated.")
    print(f"Total entries: {len(entries)} (Custom: {custom_count}, GitHub: {len(entries) - custom_count})")


if __name__ == "__main__":
    generate_playlist()
