from pathlib import Path

INPUT_FILE = "movies.txt"
OUTPUT_FILE = "playlist.m3u"

GROUP_TITLE = "Movies"


def generate_playlist():
    lines = Path(INPUT_FILE).read_text(
        encoding="utf-8"
    ).splitlines()

    entries = []

    i = 0

    while i < len(lines):
        line = lines[i].strip()

        # Skip empty lines
        if not line:
            i += 1
            continue

        name = line

        # Find the next non-empty line as URL
        i += 1

        while i < len(lines) and not lines[i].strip():
            i += 1

        if i >= len(lines):
            break

        url = lines[i].strip()

        # Ignore invalid entries
        if not url.startswith(("http://", "https://")):
            i += 1
            continue

        entries.append((name, url))

        i += 1

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n\n")

        for name, url in entries:
            f.write(
                f'#EXTINF:-1 group-title="{GROUP_TITLE}",{name}\n'
            )
            f.write(f"{url}\n\n")

    print(f"Created {OUTPUT_FILE}")
    print(f"Total entries: {len(entries)}")


if __name__ == "__main__":
    generate_playlist()
