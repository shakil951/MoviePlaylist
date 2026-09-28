import concurrent.futures
from datetime import datetime
from pathlib import Path
import re
import zoneinfo
import requests

INPUT_FILE = "movies.txt"
OUTPUT_FILE = "playlist.m3u"
DEVELOPER_NAME = "FARABI"
BASE_CHECK_URL = "https://fibwatch.art/"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://fibwatch.art/",
}


def get_active_subdomain():
    headers = {"User-Agent": DEFAULT_HEADERS["User-Agent"]}
    try:
        response = requests.get(BASE_CHECK_URL, headers=headers, timeout=10)
        match = re.search(r"https://([a-z0-9]+)\.b-cdn\.net", response.text)
        if match:
            subdomain = match.group(1)
            print(f"[*] Live CDN Subdomain: {subdomain}")
            return subdomain
    except Exception as e:
        print(f"[!] CDN check warning: {e}")
    return "krtyh"


def update_cdn_domain(text_block, active_subdomain):
    if not text_block:
        return text_block
    return re.sub(
        r"[a-z0-9]+\.b-cdn\.net", f"{active_subdomain}.b-cdn.net", text_block
    )


def get_current_time():
    try:
        tz = zoneinfo.ZoneInfo("Asia/Dhaka")
        now = datetime.now(tz)
    except Exception:
        now = datetime.now()
    return now.strftime("%d-%b-%Y %I:%M:%S %p (%Z)")


def check_single_movie(raw_item, active_subdomain):
    name = raw_item["name"]
    
    updated_logo = update_cdn_domain(raw_item["logo"], active_subdomain)
    updated_url = update_cdn_domain(raw_item["url"], active_subdomain)
    referrer = raw_item.get("referrer")

    req_headers = DEFAULT_HEADERS.copy()
    if referrer:
        req_headers["Referer"] = referrer
    elif "r2.dev" in updated_url:
        req_headers.pop("Referer", None)

    req_headers["Range"] = "bytes=0-1024"

    try:
        res = requests.get(
            updated_url, headers=req_headers, stream=True, timeout=8, allow_redirects=True
        )
        if res.status_code in [200, 206, 302]:
            print(f"[ACTIVE] -> {name[:40]}")
            return {
                "name": name,
                "logo": updated_logo,
                "raw_logo": raw_item.get("raw_logo", raw_item["logo"]),
                "url": updated_url,
                "raw_url": raw_item.get("raw_url", raw_item["url"]),
                "referrer": referrer,
                "category": raw_item.get("category", "My Collection")
            }
        else:
            print(f"[DEAD - HTTP {res.status_code}] -> Removed: {name[:40]}")
            return None
    except Exception:
        print(f"[DEAD - Timeout/Error] -> Removed: {name[:40]}")
        return None


def parse_m3u_text(text_content):
    """যেকোনো মথ্রিইউ (M3U) টেক্সট পার্স করে আইটেমের লিস্ট তৈরি করে"""
    lines = [line.strip() for line in text_content.splitlines() if line.strip()]
    parsed_items = []
    i = 0
    total = len(lines)

    while i < total:
        current = lines[i]
        if current.startswith("#EXTINF:"):
            logo_match = re.search(r'tvg-logo="([^"]*)"', current)
            logo = logo_match.group(1) if logo_match else ""
            
            # ক্যাটাগরি বা গ্রুপ বের করা
            category = "Others"
            match_quotes = re.search(r'(?i)\bgroup-title\s*=\s*(["\'])(.*?)\1', current)
            if match_quotes:
                category = match_quotes.group(2).strip()
            else:
                match_no_quotes = re.search(r'(?i)\bgroup-title\s*=\s*([^\s,]+)', current)
                if match_no_quotes:
                    category = match_no_quotes.group(1).strip()

            name = current.split(",")[-1].strip()

            i += 1
            ref = None
            url = None
            while i < total and not lines[i].startswith("#EXTINF:"):
                if "http-referrer=" in lines[i]:
                    ref = lines[i].replace("#EXTVLCOPT:http-referrer=", "").replace("http-referrer=", "").strip()
                elif lines[i].startswith("http://") or lines[i].startswith("https://"):
                    url = lines[i]
                    i += 1
                    break
                i += 1

            if url:
                parsed_items.append({
                    "name": name,
                    "logo": logo,
                    "url": url,
                    "referrer": ref,
                    "category": category
                })
        else:
            i += 1
    return parsed_items


def generate_playlist():
    txt_path = Path(INPUT_FILE)
    if not txt_path.exists():
        print(f"Error: {INPUT_FILE} not found!")
        return

    active_subdomain = get_active_subdomain()
    raw_lines = txt_path.read_text(encoding="utf-8").splitlines()

    lines = []
    for line in raw_lines:
        s = line.strip()
        if not s or s.startswith("##") or (s.startswith("#") and not s.startswith("#EXT")):
            continue
        lines.append(s)

    # ১. লোকাল movies.txt পার্স করা
    local_parsed_items = []
    i = 0
    total = len(lines)
    while i < total:
        current = lines[i]
        if current.startswith("#EXTINF:"):
            logo_match = re.search(r'tvg-logo="([^"]*)"', current)
            logo = logo_match.group(1) if logo_match else ""
            name = current.split(",")[-1].strip()
            i += 1
            ref, url = None, None
            while i < total and not lines[i].startswith("#EXTINF:"):
                if "http-referrer=" in lines[i]:
                    ref = lines[i].replace("#EXTVLCOPT:http-referrer=", "").replace("http-referrer=", "").strip()
                elif lines[i].startswith("http://") or lines[i].startswith("https://"):
                    url = lines[i]
                    i += 1
                    break
                i += 1
            if url:
                local_parsed_items.append({"name": name, "logo": logo, "url": url, "referrer": ref})
        elif i + 2 < total and (lines[i + 1].startswith("http://") or lines[i + 1].startswith("https://")) and (lines[i + 2].startswith("http://") or lines[i + 2].startswith("https://")):
            name = lines[i]
            logo = lines[i + 1]
            url = lines[i + 2]
            i += 3
            ref = None
            if i < total and "http-referrer=" in lines[i]:
                ref = lines[i].replace("http-referrer=", "").replace("#EXTVLCOPT:", "").strip()
                i += 1
            local_parsed_items.append({"name": name, "logo": logo, "url": url, "referrer": ref})
        else:
            i += 1

    # লোকাল মুভির ক্যাটাগরি সেট করা (| পাইপ চেক করে)
    processed_local_items = []
    for item in local_parsed_items:
        raw_name = item["name"]
        if "|" in raw_name:
            parts = raw_name.split("|", 1)
            clean_name = parts[0].strip()
            cat = parts[1].strip()
        else:
            clean_name = raw_name.strip()
            cat = "My Collection"
        
        processed_local_items.append({
            "name": clean_name,
            "logo": item["logo"],
            "raw_logo": item["logo"],
            "url": item["url"],
            "raw_url": item["url"],
            "referrer": item["referrer"],
            "category": cat
        })

    print(f"[*] Total local items in {INPUT_FILE}: {len(processed_local_items)}")

    # ২. এক্সটার্নাল প্লেলিস্ট ফেচ ও পার্স করা
    external_url = "https://raw.githubusercontent.com/sm-monirulislam/SM-Movie-Hup-Auto-Update/refs/heads/main/sm_movie2.m3u"
    print(f"[*] Fetching external playlist: {external_url}")
    
    external_parsed_items = []
    try:
        ext_res = requests.get(external_url, timeout=15)
        if ext_res.status_code == 200:
            external_parsed_items = parse_m3u_text(ext_res.text)
            print(f"[*] Total items found in external playlist: {len(external_parsed_items)}")
        else:
            print(f"[!] Failed to fetch external playlist. HTTP {ext_res.status_code}")
    except Exception as e:
        print(f"[!] Error fetching external playlist: {e}")

    # সব আইটেম (লোকাল + এক্সটার্নাল) একত্রে ভ্যালিডেশনের জন্য প্রস্তুত করা
    all_items_to_check = processed_local_items + external_parsed_items
    print(f"[*] Total items to validate (Live/Dead check): {len(all_items_to_check)}")

    # ৩. সব লিংক একসাথে কনকারেন্টলি টেস্ট করা
    active_movies = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
        futures = [
            executor.submit(check_single_movie, item, active_subdomain)
            for item in all_items_to_check
        ]
        for f in futures:
            result = f.result()
            if result:
                active_movies.append(result)

    dead_count = len(all_items_to_check) - len(active_movies)

    # ৪. movies.txt ফাইলটি শুধুমাত্র সচল লোকাল মুভিগুলো দিয়ে আপডেট করা
    with open(INPUT_FILE, "w", encoding="utf-8") as f:
        for m in active_movies:
            if m.get("raw_url"): # শুধু লোকাল মুভিগুলোই movies.txt এ সেভ হবে
                f.write(f"{m['name']}\n")
                f.write(f"{m['raw_logo']}\n")
                f.write(f"{m['raw_url']}\n")
                if m.get("referrer"):
                    f.write(f"http-referrer={m['referrer']}\n")
                f.write("\n")

    # ৫. ফাইনাল playlist.m3u ফাইল তৈরি করা (ডুয়াল টাইটেল VOD;Category সহ)
    current_time_str = get_current_time()
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        f.write("# ==========================================\n")
        f.write("# Playlist Name    : Farabi VOD Collection\n")
        f.write(f"# Developer        : {DEVELOPER_NAME}\n")
        f.write(f"# Last Updated     : {current_time_str}\n")
        f.write(f"# Active Subdomain : {active_subdomain}\n")
        f.write(f"# Total Active VOD : {len(active_movies)}\n")
        f.write(f"# Dead Purged      : {dead_count}\n")
        f.write("# ==========================================\n\n")

        for m in active_movies:
            category = m.get("category", "Others")
            entry_str = (
                f'#EXTINF:-1 tvg-logo="{m["logo"]}" group-title="VOD;{category}",'
                f' {m["name"]}\n'
            )
            if m.get("referrer"):
                entry_str += f"#EXTVLCOPT:http-referrer={m['referrer']}\n"
            entry_str += f"{m['url']}\n\n"
            f.write(entry_str)

    print("\n" + "=" * 40)
    print(f"[✓] Total Active Movies Kept : {len(active_movies)}")
    print(f"[✗] Total Dead Movies Purged : {dead_count}")
    print(f"[✓] Updated: {INPUT_FILE} and {OUTPUT_FILE}")
    print("=" * 40)


if __name__ == "__main__":
    generate_playlist()
