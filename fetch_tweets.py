import requests
from bs4 import BeautifulSoup
import json
import re
import time

POSFIE_URL = "https://posfie.com/@coldgifts/p/DZkG06Z"
DATA_FILE = "data/tweets.json"

def fetch_page(page_num):
    url = f"{POSFIE_URL}?page={page_num}"
    resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
    resp.raise_for_status()
    return resp.text

def extract_tweets(html):
    soup = BeautifulSoup(html, "html.parser")
    tweet_urls = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        m = re.match(r"https://x\.com/(ngnchiikawa|ngntrtr)/status/(\d+)", href)
        if m:
            tweet_urls.add(href)
    return tweet_urls

def get_total_pages(html):
    soup = BeautifulSoup(html, "html.parser")
    # Look for page links
    pages = set()
    for a in soup.find_all("a", href=True):
        m = re.search(r"[?&]page=(\d+)", a["href"])
        if m:
            pages.add(int(m.group(1)))
    return max(pages) if pages else 1

def main():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            existing = json.load(f)
        existing_urls = {t["url"] for t in existing}
    except Exception:
        existing = []
        existing_urls = set()

    # Fetch first page to get total pages
    print("Fetching page 1...")
    first_html = fetch_page(1)
    total_pages = get_total_pages(first_html)
    print(f"Total pages: {total_pages}")

    all_urls = set()
    all_urls.update(extract_tweets(first_html))

    # Only fetch pages we haven't fully processed (check last few pages for new content)
    # New tweets appear on the last page, so always fetch last 3 pages
    pages_to_fetch = list(range(2, total_pages + 1))
    if existing_urls:
        # If we have existing data, only fetch recent pages (last 3) for updates
        pages_to_fetch = list(range(max(1, total_pages - 2), total_pages + 1))

    for page in pages_to_fetch:
        print(f"Fetching page {page}/{total_pages}...")
        try:
            html = fetch_page(page)
            all_urls.update(extract_tweets(html))
            time.sleep(0.5)
        except Exception as e:
            print(f"Error on page {page}: {e}")

    # If first run (no existing data), fetch ALL pages
    if not existing_urls:
        for page in range(2, total_pages + 1):
            if page not in pages_to_fetch:
                print(f"Fetching page {page}/{total_pages}...")
                try:
                    html = fetch_page(page)
                    all_urls.update(extract_tweets(html))
                    time.sleep(0.5)
                except Exception as e:
                    print(f"Error on page {page}: {e}")

    new_count = 0
    for url in all_urls:
        if url not in existing_urls:
            m = re.search(r"/status/(\d+)", url)
            tweet_id = m.group(1) if m else ""
            existing.append({"url": url, "id": tweet_id})
            existing_urls.add(url)
            new_count += 1

    # Sort by tweet ID (chronological order)
    existing.sort(key=lambda t: int(t["id"]) if t["id"].isdigit() else 0)

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    print(f"Added {new_count} new tweets. Total: {len(existing)}")

if __name__ == "__main__":
    main()
