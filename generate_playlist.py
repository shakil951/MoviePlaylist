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


def check_and_format_entry(raw_item, active_subdomain):
  """লিংক ভ্যালিডেট করে এবং group-title="VOD" নিশ্চিত করে"""
  name = raw_item["name"]
  logo = raw_item["logo"]
  url = update_cdn_domain(raw_item["url"], active_subdomain)
  referrer = raw_item.get("referrer")

  # হেডারে রেফারার সেট করা
  req_headers = DEFAULT_HEADERS.copy()
  if referrer:
    req_headers["Referer"] = referrer
  elif "r2.dev" in url:
    req_headers.pop("Referer", None)

  # ফাইল ডাউনলোড না করে দ্রুত কানেকশন চেক
  req_headers["Range"] = "bytes=0-1024"

  try:
    res = requests.get(
        url, headers=req_headers, stream=True, timeout=8, allow_redirects=True
    )
    if res.status_code in [200, 206, 302]:
      print(f"[ACTIVE] -> {name[:40]}")
      entry_str = (
          f'#EXTINF:-1 tvg-logo="{logo}" group-title="VOD", {name}\n'
      )
      if referrer:
        entry_str += f"#EXTVLCOPT:http-referrer={referrer}\n"
      entry_str += url
      return entry_str
    else:
      print(f"[DEAD - HTTP {res.status_code}] -> Skipping: {name[:40]}")
      return None
  except Exception:
    print(f"[DEAD - Timeout/Error] -> Skipping: {name[:40]}")
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

    # #EXTINF ফরম্যাটে থাকলে
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

    # সাধারণ ৩ লাইনের ফরম্যাটে থাকলে (Name -> Logo -> URL)
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

  print(f"[*] Found {len(parsed_items)} movies to check.")
  print("[*] Validating links & filtering dead links...")

  active_entries = []
  # মাল্টি-থ্রেডিং দিয়ে দ্রুত চেক
  with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
    futures = [
        executor.submit(check_and_format_entry, item, active_subdomain)
        for item in parsed_items
    ]
    for f in futures:
      result = f.result()
      if result:
        active_entries.append(result)

  current_time_str = get_current_time()

  with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    f.write("#EXTM3U\n")
    f.write("# ==========================================\n")
    f.write("# Playlist Name    : Farabi VOD Collection (Verified)\n")
    f.write(f"# Developer        : {DEVELOPER_NAME}\n")
    f.write(f"# Last Updated     : {current_time_str}\n")
    f.write(f"# Active Subdomain : {active_subdomain}\n")
    f.write(f"# Total Active VOD : {len(active_entries)}\n")
    f.write(f"# Dead Removed     : {len(parsed_items) - len(active_entries)}\n")
    f.write("# ==========================================\n\n")

    for entry in active_entries:
      f.write(f"{entry}\n\n")

  print(
      f"\n[✓] Done! Saved {len(active_entries)} live movies to {OUTPUT_FILE}."
  )


if __name__ == "__main__":
  generate_playlist()
