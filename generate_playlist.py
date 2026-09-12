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
                "raw_logo": raw_item["logo"],
                "url": updated_url,
                "raw_url": raw_item["url"],
                "referrer": referrer,
            }
        else:
            print(f"[DEAD - HTTP {res.status_code}] -> Removed: {name[:40]}")
            return None
    except Exception:
        print(f"[DEAD - Timeout/Error] -> Removed: {name[:40]}")
        return None


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
        if (
            not s
            or s.startswith("##")
            or (s.startswith("#") and not s.startswith("#EXT"))
        ):
            continue
        lines.append(s)

    parsed_items = []
    i = 0
    total = len(lines)

    while i < total:
        current = lines[i]

        if current.startswith("#EXTINF:"):
            logo_match = re.search(r'tvg-logo="([^"]*)"', current)
            logo = logo_match.group(1) if logo_match else ""
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
                    i += 1
                    break
                i += 1

            if url:
                parsed_items.append(
                    {"name": name, "logo": logo, "url": url, "referrer": ref}
                )

        elif (
            i + 2 < total
            and (
                lines[i + 1].startswith("http://")
                or lines[i + 1].startswith("https://")
            )
            and (
                lines[i + 2].startswith("http://")
                or lines[i + 2].startswith("https://")
            )
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

            parsed_items.append(
                {"name": name, "logo": logo, "url": url, "referrer": ref}
            )
        else:
            i += 1

    print(f"[*] Total movies in {INPUT_FILE}: {len(parsed_items)}")
    print("[*] Validating links & purging dead entries...")

    active_movies = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [
            executor.submit(check_single_movie, item, active_subdomain)
            for item in parsed_items
        ]
        for f in futures:
            result = f.result()
            if result:
                active_movies.append(result)

    dead_count = len(parsed_items) - len(active_movies)

    with open(INPUT_FILE, "w", encoding="utf-8") as f:
        for m in active_movies:
            f.write(f"{m['name']}\n")
            f.write(f"{m['raw_logo']}\n")
            f.write(f"{m['raw_url']}\n")
            if m.get("referrer"):
                f.write(f"http-referrer={m['referrer']}\n")
            f.write("\n")

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

        # ১. আপনার নিজের মুভিগুলোতে VOD;My Collection যুক্ত করা হচ্ছে
        for m in active_movies:
            entry_str = (
                f'#EXTINF:-1 tvg-logo="{m["logo"]}" group-title="VOD;My Collection",'
                f' {m["name"]}\n'
            )
            if m.get("referrer"):
                entry_str += f"#EXTVLCOPT:http-referrer={m['referrer']}\n"
            entry_str += f"{m['url']}\n\n"
            f.write(entry_str)

    # === ৩. এক্সটার্নাল প্লেলিস্ট যুক্ত করার নতুন ডুয়াল-টাইটেল কোড ===
    external_url = "https://raw.githubusercontent.com/sm-monirulislam/SM-Movie-Hup-Auto-Update/refs/heads/main/Movie_Combined.m3u"
    print(f"[*] Fetching external playlist: {external_url}")
    
    try:
        ext_res = requests.get(external_url, timeout=15)
        if ext_res.status_code == 200:
            import re
            
            clean_lines = []
            for line in ext_res.text.splitlines():
                line = line.strip()
                lower_line = line.lower()
                
                if line.startswith("#EXTINF") or line.startswith("#EXTVLCOPT") or lower_line.startswith("http"):
                    
                    if line.startswith("#EXTINF"):
                        
                        # (ক) আসল ক্যাটাগরি খুঁজে বের করা
                        original_category = "Others" # ডিফল্ট ক্যাটাগরি
                        match_quotes = re.search(r'(?i)\bgroup-title\s*=\s*(["\'])(.*?)\1', line)
                        if match_quotes:
                            original_category = match_quotes.group(2).strip()
                        else:
                            match_no_quotes = re.search(r'(?i)\bgroup-title\s*=\s*([^\s,]+)', line)
                            if match_no_quotes:
                                original_category = match_no_quotes.group(1).strip()
                        
                        # (খ) আগের যেকোনো group-title মুছে ফেলা
                        line = re.sub(r'(?i)\bgroup-title\s*=\s*["\'][^"\']*["\']', '', line)
                        line = re.sub(r'(?i)\bgroup-title\s*=\s*[^\s,]+', '', line)
                        
                        # (গ) নতুন ডুয়াল-টাইটেল বসানো: VOD;[আসল ক্যাটাগরি]
                        parts = line.split(',', 1)
                        if len(parts) == 2:
                            line = f'{parts[0]} group-title="VOD;{original_category}",{parts[1]}'
                        else:
                            line = f'{line} group-title="VOD;{original_category}",'
                        
                    clean_lines.append(line)
            
            ext_content = "\n".join(clean_lines)
            
            with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
                f.write("\n\n# ==========================================\n")
                f.write("#       EXTERNAL PLAYLIST (SM Movie Hub)      \n")
                f.write("# ==========================================\n\n")
                f.write(ext_content)
                f.write("\n")
            print("[✓] External playlist merged with Dual Titles successfully!")
        else:
            print(f"[!] Failed to fetch external playlist. HTTP {ext_res.status_code}")
    except Exception as e:
        print(f"[!] Error fetching external playlist: {e}")

    print("\n" + "=" * 40)
    print(f"[✓] Active Movies Kept : {len(active_movies)}")
    print(f"[✗] Dead Movies Purged : {dead_count}")
    print(f"[✓] Updated: {INPUT_FILE} and {OUTPUT_FILE}")
    print("=" * 40)


if __name__ == "__main__":
    generate_playlist()
