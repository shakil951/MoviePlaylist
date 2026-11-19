import concurrent.futures
from datetime import datetime
import os
from pathlib import Path
import re
import zoneinfo
import cloudscraper
import requests

INPUT_FILE = "movies.txt"
OUTPUT_FILE = "playlist.m3u"
DEVELOPER_NAME = "FARABI"
BASE_CHECK_URL = "https://fibwatch.art/"
LAST_DOMAIN_FILE = "last_domain.txt"
DEFAULT_FALLBACK_SUBDOMAIN = "krtyh"

# সঠিক এক্সটার্নাল প্লেলিস্ট লিংক
EXTERNAL_PLAYLIST_URL = "https://raw.githubusercontent.com/sm-monirulislam/SM-Movie-Hup-Auto-Update/refs/heads/main/All_movie.m3u"

# আপনার নতুন ইমেজ প্রক্সি ওয়ার্কার লিংক
IMAGE_PROXY_BASE = "https://image-proxy.usergamil15.workers.dev/?url="

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://fibwatch.art/",
}


def get_proxied_logo(logo_url):
    """লোগোর লিংকে ওয়ার্কার প্রক্সি অ্যাড করবে এবং ডাবল প্রক্সি ঠেকাবে"""
    if not logo_url:
        return ""
    if "?url=" in logo_url:
        logo_url = logo_url.split("?url=")[-1]
    return f"{IMAGE_PROXY_BASE}{logo_url}"


def save_last_domain(subdomain):
    try:
        Path(LAST_DOMAIN_FILE).write_text(subdomain, encoding="utf-8")
    except Exception as ex:
        print(f"[!] Could not save last domain: {ex}")


def get_active_subdomain():
    secret_sub = os.environ.get("LIVE_SUBDOMAIN", "").strip()
    if secret_sub:
        print(f"[*] Using LIVE_SUBDOMAIN from environment/secret: {secret_sub}")
        save_last_domain(secret_sub)
        return secret_sub

    subdomain = None

    # ১ম চেষ্টা: Playwright Headless Browser দিয়ে লাইভ সাবডোমেইন আনা
    try:
        from playwright.sync_api import sync_playwright

        print("[*] Trying Playwright browser to fetch live subdomain...")
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"],
            )
            context = browser.new_context(
                user_agent=DEFAULT_HEADERS["User-Agent"]
            )
            page = context.new_page()
            page.goto(BASE_CHECK_URL, wait_until="domcontentloaded", timeout=25000)
            # Cloudflare JS challenge শেষ হওয়ার জন্য সামান্য অপেক্ষা
            page.wait_for_timeout(7000)
            html = page.content()
            browser.close()

            match = re.search(r"https://([a-z0-9]+)\.b-cdn\.net", html)
            if match:
                subdomain = match.group(1)
                print(f"[*] Live CDN Subdomain (Playwright): {subdomain}")
            else:
                print("[!] Playwright loaded page, but subdomain regex not found.")
    except Exception as e:
        print(f"[!] Playwright check exception: {e}")

    # ২য় চেষ্টা: Playwright না পেলে cloudscraper দিয়ে চেষ্টা
    if not subdomain:
        scraper = cloudscraper.create_scraper()
        headers = {
            "User-Agent": DEFAULT_HEADERS["User-Agent"],
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
        try:
            response = scraper.get(BASE_CHECK_URL, headers=headers, timeout=15)
            print(f"[*] CDN Check Status Code (cloudscraper): {response.status_code}")

            match = re.search(r"https://([a-z0-9]+)\.b-cdn\.net", response.text)
            if match:
                subdomain = match.group(1)
                print(f"[*] Live CDN Subdomain (cloudscraper): {subdomain}")
            else:
                print(
                    f"[!] Warning: Subdomain regex not found in response. Preview: {response.text[:150]}..."
                )
        except Exception as e:
            print(f"[!] Cloudscraper check exception: {e}")

    # যদি নতুন সাবডোমেইন সফলভাবে পাওয়া যায়, তবে তা ফাইলে সেভ করে রাখব
    if subdomain:
        save_last_domain(subdomain)
        return subdomain

    # যদি স্ক্যাপ করতে ফেইল করে, তবে last_domain.txt ফাইল থেকে সর্বশেষ সফল ডোমেনটি পড়ার চেষ্টা করবে
    last_domain_path = Path(LAST_DOMAIN_FILE)
    if last_domain_path.exists():
        saved_domain = last_domain_path.read_text(encoding="utf-8").strip()
        if saved_domain:
            print(f"[*] Using last working saved subdomain from file: {saved_domain}")
            return saved_domain

    # ফাইলও না থাকলে একদম আল্টিমেট ফলব্যাক
    print(f"[!] Falling back to default subdomain: {DEFAULT_FALLBACK_SUBDOMAIN}")
    return DEFAULT_FALLBACK_SUBDOMAIN


def update_cdn_domain(text_block, active_subdomain):
    if not text_block:
        return text_block
    return re.sub(
        r"https://[a-z0-9]+\.b-cdn\.net",
        f"https://{active_subdomain}.b-cdn.net",
        text_block,
    )


def get_current_time():
    try:
        tz = zoneinfo.ZoneInfo("Asia/Dhaka")
        now = datetime.now(tz)
    except Exception:
        now = datetime.now()
    return now.strftime("%d-%b-%Y %I:%M:%S %p (%Z)")


def get_resolution_score(name):
    name_lower = name.lower()
    if "4k" in name_lower or "2160p" in name_lower:
        return 4
    elif "1080p" in name_lower or "fhd" in name_lower:
        return 3
    elif "720p" in name_lower or "hd" in name_lower:
        return 2
    elif "480p" in name_lower or "360p" in name_lower:
        return 1
    return 0


def get_base_movie_name(name):
    cleaned = re.sub(
        r"(?i)\b(4k|2160p|1080p|720p|480p|360p|fhd|hd|sd|web-dl|bluray|rip|hdrip|hdts)\b",
        "",
        name,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip().lower()
    return cleaned


def check_single_movie(raw_item, active_subdomain):
    name = raw_item["name"]
    updated_logo = update_cdn_domain(raw_item.get("logo", ""), active_subdomain)
    updated_url = update_cdn_domain(raw_item.get("url", ""), active_subdomain)
    referrer = raw_item.get("referrer")

    req_headers = DEFAULT_HEADERS.copy()
    if referrer:
        req_headers["Referer"] = referrer
    elif "r2.dev" in updated_url:
        req_headers.pop("Referer", None)

    req_headers["Range"] = "bytes=0-1024"

    try:
        res = requests.get(
            updated_url,
            headers=req_headers,
            stream=True,
            timeout=15,
            allow_redirects=True,
        )
        valid_codes = [200, 206, 301, 302, 307, 308, 416]

        if res.status_code in valid_codes:
            print(f"[ACTIVE] -> {name[:40]}")
            return {
                "name": name,
                "logo": updated_logo,
                "raw_logo": raw_item.get("raw_logo", raw_item.get("logo", "")),
                "url": updated_url,
                "raw_url": raw_item.get("raw_url", raw_item.get("url", "")),
                "referrer": referrer,
                "category": raw_item.get("category", "My Collection"),
                "res_score": get_resolution_score(name),
                "base_name": get_base_movie_name(name),
            }
        else:
            print(f"[DEAD - HTTP {res.status_code}] -> Removed: {name[:40]}")
            return None
    except Exception as e:
        print(f"[DEAD - {type(e).__name__}] -> Removed: {name[:40]}")
        return None


def parse_external_m3u(text_content, active_subdomain):
    lines = [line.strip() for line in text_content.splitlines() if line.strip()]
    parsed_items = []
    i = 0
    total = len(lines)

    while i < total:
        current = lines[i]
        if current.startswith("#EXTINF:"):
            logo_match = re.search(r'tvg-logo="([^"]*)"', current)
            logo = logo_match.group(1) if logo_match else ""
            logo = update_cdn_domain(logo, active_subdomain)

            category = "Others"
            match_quotes = re.search(
                r'(?i)\bgroup-title\s*=\s*(["\'])(.*?)\1', current
            )
            if match_quotes:
                category = match_quotes.group(2).strip()
            else:
                match_no_quotes = re.search(r"(?i)\bgroup-title\s*=\s*([^\s,]+)", current)
                if match_no_quotes:
                    category = match_no_quotes.group(1).strip()

            name = current.split(",")[-1].strip()

            i += 1
            ref = None
            url = None
            while i < total and not lines[i].startswith("#EXTINF:"):
                if "http-referrer=" in lines[i]:
                    ref = (
                        lines[i]
                        .replace("#EXTVLCOPT:http-referrer=", "")
                        .replace("http-referrer=", "")
                        .strip()
                    )
                elif lines[i].startswith("http://") or lines[i].startswith("https://"):
                    url = lines[i]
                    url = update_cdn_domain(url, active_subdomain)
                    i += 1
                    break
                i += 1

            if url:
                parsed_items.append({
                    "name": name,
                    "logo": logo,
                    "raw_logo": logo,
                    "url": url,
                    "raw_url": url,
                    "referrer": ref,
                    "category": category,
                    "res_score": get_resolution_score(name),
                    "base_name": get_base_movie_name(name),
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

    lines = [
        line.strip()
        for line in raw_lines
        if line.strip()
        and not line.startswith("##")
        and not (line.startswith("#") and not line.startswith("#EXT"))
    ]

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
                    ref = (
                        lines[i]
                        .replace("#EXTVLCOPT:http-referrer=", "")
                        .replace("http-referrer=", "")
                        .strip()
                    )
                elif lines[i].startswith("http://") or lines[i].startswith("https://"):
                    url = lines[i]
                    i += 1
                    break
                i += 1
            if url:
                local_parsed_items.append(
                    {"name": name, "logo": logo, "url": url, "referrer": ref}
                )
        elif (
            i + 2 < total
            and (lines[i + 1].startswith("http://") or lines[i + 1].startswith("https://"))
            and (lines[i + 2].startswith("http://") or lines[i + 2].startswith("https://"))
        ):
            name = lines[i]
            logo = lines[i + 1]
            url = lines[i + 2]
            i += 3
            ref = None
            if i < total and "http-referrer=" in lines[i]:
                ref = (
                    lines[i]
                    .replace("http-referrer=", "")
                    .replace("#EXTVLCOPT:", "")
                    .strip()
                )
                i += 1
            local_parsed_items.append(
                {"name": name, "logo": logo, "url": url, "referrer": ref}
            )
        else:
            i += 1

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

        updated_logo = update_cdn_domain(item["logo"], active_subdomain)
        updated_url = update_cdn_domain(item["url"], active_subdomain)

        processed_local_items.append({
            "name": clean_name,
            "logo": updated_logo,
            "raw_logo": item["logo"],
            "url": updated_url,
            "raw_url": item["url"],
            "referrer": item["referrer"],
            "category": cat,
            "res_score": get_resolution_score(clean_name),
            "base_name": get_base_movie_name(clean_name),
        })

    # All_movie.m3u থেকে লিংক ফেচ করার অংশ
    external_movies = []
    print(f"[*] Fetching external playlist: {EXTERNAL_PLAYLIST_URL}")
    try:
        ext_res = requests.get(EXTERNAL_PLAYLIST_URL, timeout=15)
        if ext_res.status_code == 200:
            parsed_ext = parse_external_m3u(ext_res.text, active_subdomain)
            for item in parsed_ext:
                item["name"] = f"{item['name']} | {item['category']}"
                external_movies.append(item)
            print(f"[✓] Fetched {len(external_movies)} items from All_movie.m3u.")
        else:
            print(f"[!] Failed to fetch external playlist. HTTP {ext_res.status_code}")
    except Exception as e:
        print(f"[!] Error fetching external playlist: {e}")

    all_candidates = processed_local_items + external_movies

    run_full_check = (
        os.environ.get("CHECK_EXTERNAL_CHECK", "false").lower() == "true"
    )

    if run_full_check:
        print("[*] Manual mode: Validating all items with HTTP check...")
        active_movies_raw = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
            futures = [
                executor.submit(check_single_movie, item, active_subdomain)
                for item in all_candidates
            ]
            for f in futures:
                result = f.result()
                if result:
                    active_movies_raw.append(result)
        final_active_items = active_movies_raw
    else:
        print("[*] Auto mode: Skipping HTTP checks for speed, using all fetched items.")
        final_active_items = all_candidates

    movie_dict = {}
    for m in final_active_items:
        b_name = m["base_name"]
        score = m["res_score"]
        if b_name not in movie_dict or score > movie_dict[b_name]["res_score"]:
            movie_dict[b_name] = m

    final_movies = list(movie_dict.values())
    dedup_removed = len(final_active_items) - len(final_movies)

    current_time_str = get_current_time()
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        f.write("# ==========================================\n")
        f.write("# Playlist Name    : Farabi VOD Collection\n")
        f.write(f"# Developer        : {DEVELOPER_NAME}\n")
        f.write(f"# Last Updated     : {current_time_str}\n")
        f.write(f"# Active Subdomain : {active_subdomain}\n")
        f.write(f"# Total Unique VOD : {len(final_movies)}\n")
        f.write(f"# Dupes Removed    : {dedup_removed}\n")
        f.write("# ==========================================\n\n")

        for m in final_movies:
            category = m.get("category", "My Collection")
            final_logo = get_proxied_logo(m["logo"])

            entry_str = (
                f'#EXTINF:-1 tvg-logo="{final_logo}" group-title="VOD;{category}",'
                f' {m["name"]}\n'
            )
            if m.get("referrer"):
                entry_str += f"#EXTVLCOPT:http-referrer={m['referrer']}\n"
            entry_str += f"{m['url']}\n\n"
            f.write(entry_str)

    print("\n" + "=" * 40)
    print(f"[✓] Final Unique Playlist Count : {len(final_movies)}")
    print(f"[🔄] Lower-Res Dupes Removed     : {dedup_removed}")
    print(f"[✓] Updated: {OUTPUT_FILE}")
    print("=" * 40)


if __name__ == "__main__":
    generate_playlist()
