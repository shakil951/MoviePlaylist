import concurrent.futures
from datetime import datetime
from pathlib import Path
import re
import zoneinfo
import requests
import os

INPUT_FILE = "movies.txt"
OUTPUT_FILE = "playlist.m3u"
DEVELOPER_NAME = "FARABI"
BASE_CHECK_URL = "https://fibwatch.art/"
FALLBACK_SUBDOMAIN = "ywerf"

# ইমেজ প্রক্সি ওয়ার্কার লিংক
IMAGE_PROXY_BASE = "https://image-proxy.usergamil15.workers.dev/?url="

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://fibwatch.art/",
}

# কানেকশন দ্রুত করার জন্য গ্লোবাল সেশন
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=100, pool_maxsize=100)
session.mount('http://', adapter)
session.mount('https://', adapter)


def get_proxied_logo(logo_url):
    """লোগোর লিংকে ওয়ার্কার প্রক্সি অ্যাড করবে এবং ডাবল প্রক্সি ঠেকাবে"""
    if not logo_url:
        return ""
    if "?url=" in logo_url:
        logo_url = logo_url.split("?url=")[-1]
    return f"{IMAGE_PROXY_BASE}{logo_url}"


def get_active_subdomain(sample_bcdn_url=None):
    """ওয়েবসাইট থেকে নিখুঁতভাবে লাইভ b-cdn.net সাবডোমেইন খুঁজে বের করবে"""
    headers = {
        "User-Agent": DEFAULT_HEADERS["User-Agent"],
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    
    urls_to_probe = [
        BASE_CHECK_URL,
        f"{BASE_CHECK_URL}movies",
        f"{BASE_CHECK_URL}latest",
    ]

    cdn_pattern = re.compile(r'(?:https?:)?(?:\\/|/){2}([a-zA-Z0-9\-]+)\.b-cdn\.net', re.IGNORECASE)

    for probe_url in urls_to_probe:
        try:
            response = session.get(probe_url, headers=headers, timeout=10, allow_redirects=True)
            print(f"[*] Probing {probe_url} -> Status: {response.status_code}")
            
            if response.status_code == 200:
                matches = cdn_pattern.findall(response.text)
                valid_subs = [m for m in matches if m.lower() not in ["www", "cdn", "static"]]
                if valid_subs:
                    best_subdomain = max(set(valid_subs), key=valid_subs.count)
                    print(f"[✓] Live CDN Subdomain Detected: {best_subdomain}")
                    return best_subdomain
        except Exception as e:
            print(f"[!] Probe warning for {probe_url}: {e}")

    if sample_bcdn_url:
        old_match = re.search(r'([a-zA-Z0-9\-]+)\.b-cdn\.net', sample_bcdn_url, re.IGNORECASE)
        if old_match:
            existing_sub = old_match.group(1)
            try:
                test_res = session.get(
                    sample_bcdn_url,
                    headers={**DEFAULT_HEADERS, "Range": "bytes=0-512"},
                    timeout=5,
                    stream=True
                )
                test_res.close()
                if test_res.status_code in [200, 206, 301, 302]:
                    print(f"[✓] Existing Subdomain Still Active: {existing_sub}")
                    return existing_sub
            except Exception:
                pass

    print(f"[!] Using Fallback Subdomain: {FALLBACK_SUBDOMAIN}")
    return FALLBACK_SUBDOMAIN


def update_cdn_domain(text_block, active_subdomain):
    """শুধুমাত্র নির্দিষ্ট আইটেমের পুরোনো b-cdn.net সাবডোমেইনকে নতুনটি দিয়ে রিপ্লেস করবে"""
    if not text_block or not active_subdomain:
        return text_block
    return re.sub(
        r"(?<=://)[a-zA-Z0-9\-]+(?=\.b-cdn\.net)",
        active_subdomain,
        text_block,
        flags=re.IGNORECASE
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
    cleaned = re.sub(r'(?i)\b(4k|2160p|1080p|720p|480p|360p|fhd|hd|sd|web-dl|bluray|rip|hdrip|hdts)\b', '', name)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip().lower()
    return cleaned


def check_single_movie(raw_item, active_subdomain):
    """শুধুমাত্র লোকাল ও মেইন Fibwatch প্লেলিস্টের লিংক চেক করবে"""
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
        res = session.get(
            updated_url, headers=req_headers, stream=True, timeout=5, allow_redirects=True
        )
        valid_codes = [200, 206, 301, 302, 307, 308, 416]
        res.close()

        if res.status_code in valid_codes:
            print(f"[ACTIVE] -> {name[:40]}")
            return {
                "name": name,
                "logo": updated_logo,
                "url": updated_url,
                "referrer": referrer,
                "category": raw_item.get("category", "My Collection"),
                "use_proxy": True,
                "res_score": get_resolution_score(name),
                "base_name": get_base_movie_name(name)
            }
        else:
            print(f"[DEAD - HTTP {res.status_code}] -> Removed: {name[:40]}")
            return None
    except Exception:
        print(f"[DEAD - Timeout/Err] -> Removed: {name[:40]}")
        return None


def parse_m3u_content(text_content, active_subdomain=None, apply_fibwatch_logic=False):
    """M3U পার্স করবে; apply_fibwatch_logic=True হলেই কেবল সাবডোমেইন ও প্রক্সি সেট হবে"""
    lines = [line.strip() for line in text_content.splitlines() if line.strip()]
    parsed_items = []
    i = 0
    total = len(lines)

    while i < total:
        current = lines[i]
        if current.startswith("#EXTINF:"):
            logo_match = re.search(r'tvg-logo="([^"]*)"', current)
            logo = logo_match.group(1) if logo_match else ""
            if apply_fibwatch_logic and active_subdomain:
                logo = update_cdn_domain(logo, active_subdomain)
            
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
                    if apply_fibwatch_logic and active_subdomain:
                        url = update_cdn_domain(url, active_subdomain)
                    i += 1
                    break
                i += 1

            if url:
                parsed_items.append({
                    "name": f"{name} | {category}",
                    "logo": logo,
                    "url": url,
                    "referrer": ref,
                    "category": category,
                    "use_proxy": apply_fibwatch_logic,
                    "res_score": get_resolution_score(name),
                    "base_name": get_base_movie_name(name)
                })
        else:
            i += 1
    return parsed_items


def generate_playlist():
    txt_path = Path(INPUT_FILE)
    if not txt_path.exists():
        print(f"Error: {INPUT_FILE} not found!")
        return

    raw_lines = txt_path.read_text(encoding="utf-8").splitlines()
    sample_bcdn = next((line.strip() for line in raw_lines if ".b-cdn.net" in line and line.strip().startswith("http")), None)
    
    # লাইভ সাবডোমেইন ডিটেকশন
    active_subdomain = get_active_subdomain(sample_bcdn)

    lines = [
        line.strip() for line in raw_lines 
        if line.strip() and not line.startswith("##") and not (line.startswith("#") and not line.startswith("#EXT"))
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

    # ১. লোকাল movies.txt আইটেম প্রসেস (সাবডোমেইন আপডেট + প্রক্সি সহ)
    fibwatch_items_pool = []
    for item in local_parsed_items:
        raw_name = item["name"]
        if "|" in raw_name:
            parts = raw_name.split("|", 1)
            clean_name = parts[0].strip()
            cat = parts[1].strip()
        else:
            clean_name = raw_name.strip()
            cat = "My Collection"
        
        fibwatch_items_pool.append({
            "name": clean_name,
            "logo": update_cdn_domain(item["logo"], active_subdomain),
            "url": update_cdn_domain(item["url"], active_subdomain),
            "referrer": item["referrer"],
            "category": cat,
            "use_proxy": True,
            "res_score": get_resolution_score(clean_name),
            "base_name": get_base_movie_name(clean_name)
        })

    # ২. মেইন এক্সটার্নাল লিংক (All_movie.m3u) -> অটো ও ম্যানুয়াল উভয় মোডেই নতুন লিংক নিয়ে আসবে (সাবডোমেইন আপডেট ও প্রক্সি সহ)
    main_external_url = "https://raw.githubusercontent.com/sm-monirulislam/SM-Movie-Hup-Auto-Update/refs/heads/main/All_movie.m3u"
    print(f"[*] Fetching main Fibwatch playlist: {main_external_url}")
    try:
        ext_res = session.get(main_external_url, timeout=15)
        if ext_res.status_code == 200:
            parsed_main_ext = parse_m3u_content(ext_res.text, active_subdomain, apply_fibwatch_logic=True)
            fibwatch_items_pool.extend(parsed_main_ext)
            print(f"[✓] Fetched {len(parsed_main_ext)} items from All_movie.m3u")
        else:
            print(f"[!] Failed to fetch main external playlist. HTTP {ext_res.status_code}")
    except Exception as e:
        print(f"[!] Error fetching main external playlist: {e}")

    # ৩. ডেড লিংক চেকিং: শুধুমাত্র আপনি ম্যানুয়ালি অ্যাকশন দিলে (CHECK_EXTERNAL_CHECK=true) চলবে
    run_full_check = os.environ.get("CHECK_EXTERNAL_CHECK", "false").lower() == "true"
    if run_full_check:
        print(f"[*] Manual Check Mode: Validating {len(fibwatch_items_pool)} Fibwatch/Local items with 100 fast workers...")
        validated_fibwatch_items = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
            futures = [executor.submit(check_single_movie, item, active_subdomain) for item in fibwatch_items_pool]
            for f in concurrent.futures.as_completed(futures):
                result = f.result()
                if result:
                    validated_fibwatch_items.append(result)
    else:
        print("[*] Auto Mode: Imported all new & existing links without HTTP dead-link check.")
        validated_fibwatch_items = fibwatch_items_pool

    # ৪. বাকি দুটি এক্সটার্নাল লিংক (কোনো চেকিং, সাবডোমেইন বা ইমেজ প্রক্সি ছাড়াই সরাসরি যুক্ত হবে)
    direct_passthrough_urls = [
        "https://raw.githubusercontent.com/sm-monirulislam/SM-Movie-Hup-Auto-Update/refs/heads/main/ftp_movie.m3u",
        "https://raw.githubusercontent.com/MRM3UK/New-try/refs/heads/main/Metflix_Playlist_1792332597030.m3u"
    ]

    passthrough_items = []
    for d_url in direct_passthrough_urls:
        print(f"[*] Fetching direct passthrough playlist: {d_url}")
        try:
            d_res = session.get(d_url, timeout=15)
            if d_res.status_code == 200:
                parsed_direct = parse_m3u_content(d_res.text, active_subdomain=None, apply_fibwatch_logic=False)
                passthrough_items.extend(parsed_direct)
            else:
                print(f"[!] Failed to fetch passthrough playlist. HTTP {d_res.status_code}")
        except Exception as e:
            print(f"[!] Error fetching passthrough playlist: {e}")

    # সব আইটেম একত্র করা
    all_final_candidates = validated_fibwatch_items + passthrough_items

    # ডুপ্লিকেট রিমুভ এবং সর্বোচ্চ রেজোলিউশন বাছাই
    movie_dict = {}
    for m in all_final_candidates:
        b_name = m["base_name"]
        score = m["res_score"]
        if b_name not in movie_dict or score > movie_dict[b_name]["res_score"]:
            movie_dict[b_name] = m
            
    final_movies = list(movie_dict.values())
    dedup_removed = len(all_final_candidates) - len(final_movies)

    # প্লেলিস্ট ফাইল রাইট করা
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
            final_logo = get_proxied_logo(m["logo"]) if m.get("use_proxy") else m["logo"]
            
            entry_str = (
                f'#EXTINF:-1 tvg-logo="{final_logo}" group-title="VOD;{category}",'
                f' {m["name"]}\n'
            )
            if m.get("referrer"):
                entry_str += f"#EXTVLCOPT:http-referrer={m['referrer']}\n"
            entry_str += f"{m['url']}\n\n"
            f.write(entry_str)

    print("\n" + "=" * 40)
    print(f"[✓] Active Subdomain Used       : {active_subdomain}")
    print(f"[✓] Final Unique Playlist Count : {len(final_movies)}")
    print(f"[🔄] Lower-Res Dupes Removed      : {dedup_removed}")
    print(f"[✓] Updated: {OUTPUT_FILE}")
    print("=" * 40)


if __name__ == "__main__":
    generate_playlist()
