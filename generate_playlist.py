from pathlib import Path

INPUT_FILE = "movies.txt"
OUTPUT_FILE = "playlist.m3u"

GROUP_TITLE = "Movies"


def generate_playlist():
    lines = [
        line.strip()
        for line in Path(INPUT_FILE).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    entries = []

    # প্রতি movie = 3 lines
    # 1. Name
    # 2. Logo
    # 3. Video URL

    for i in range(0, len(lines), 3):

        if i + 2 >= len(lines):
            print(f"Skipping incomplete entry starting at line {i + 1}")
            continue

        name = lines[i]
        logo = lines[i + 1]
        url = lines[i + 2]

        if not url.startswith(("http://", "https://")):
            print(f"Invalid video URL: {url}")
            continue

        entries.append((name, logo, url))

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:

        f.write("#EXTM3U\n\n")

        for name, logo, url in entries:

            f.write(
                f'#EXTINF:-1 tvg-logo="{logo}" '
                f'group-title="{GROUP_TITLE}",{name}\n'
            )

            f.write(f"{url}\n\n")

    print(f"Playlist generated successfully!")
    print(f"Total entries: {len(entries)}")


if __name__ == "__main__":
    generate_playlist()
