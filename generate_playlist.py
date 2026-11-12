# অটো বা ম্যানুয়াল উভয় মোডেই movies.txt ফাইলটি নতুন ইউনিক মুভিগুলো দিয়ে আপডেট হয়ে যাবে
    with open(INPUT_FILE, "w", encoding="utf-8") as f:
        for m in final_movies:
            name_to_save = m['name']
            if "|" not in name_to_save and m.get("category"):
                name_to_save = f"{m['name']} | {m['category']}"
            f.write(f"{name_to_save}\n")
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
        f.write(f"# Total Unique VOD : {len(final_movies)}\n")
        f.write(f"# Dupes Removed    : {dedup_removed}\n")
        f.write("# ==========================================\n\n")

        for m in final_movies:
            category = m.get("category", "My Collection")
            
            if m.get("use_proxy", True):
                final_logo = get_proxied_logo(m["logo"])
            else:
                final_logo = m["logo"]
            
            entry_str = (
                f'#EXTINF:-1 tvg-logo="{final_logo}" group-title="VOD;{category}",'
                f' {m["name"]}\n'
            )
            if m.get("referrer"):
                entry_str += f"#EXTVLCOPT:http-referrer={m['referrer']}\n"
            entry_str += f"{m['url']}\n\n"
            f.write(entry_str)
