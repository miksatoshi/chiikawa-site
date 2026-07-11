import requests
from bs4 import BeautifulSoup
import json
import re
import time
import math

POSFIE_URL = "https://posfie.com/@coldgifts/p/DZkG06Z"
DATA_FILE = "data/tweets.json"
BATCH_SIZE = 100

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
        m = re.match(r"https://x\.com/(ngnchiikawa|ngntrtr)/status/(\d+)$", href)
        if m:
            tweet_urls.add(href)
    return tweet_urls

def get_total_pages(html):
    soup = BeautifulSoup(html, "html.parser")
    pages = set()
    for a in soup.find_all("a", href=True):
        m = re.search(r"[?&]page=(\d+)", a["href"])
        if m:
            pages.add(int(m.group(1)))
    return max(pages) if pages else 1

def float_to_base36(n):
    chars = '0123456789abcdefghijklmnopqrstuvwxyz'
    int_part = int(n)
    frac_part = n - int_part
    if int_part == 0:
        result = '0'
    else:
        result = ''
        tmp = int_part
        while tmp > 0:
            result = chars[tmp % 36] + result
            tmp //= 36
    if frac_part > 1e-10:
        result += '.'
        for _ in range(10):
            frac_part *= 36
            d = int(frac_part)
            result += chars[d]
            frac_part -= d
            if frac_part < 1e-10:
                break
    return result

def get_tweet_token(tweet_id):
    val = (int(tweet_id) / 1e15) * math.pi
    b36 = float_to_base36(val)
    return re.sub(r'[0.]', '', b36)

def get_tweet_media(tweet_id):
    token = get_tweet_token(tweet_id)
    url = f"https://cdn.syndication.twimg.com/tweet-result?id={tweet_id}&lang=ja&token={token}"
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if resp.status_code != 200:
            print(f"  API {resp.status_code} for {tweet_id}")
            return [], ""
        data = resp.json()
        images = []
        for media in data.get("mediaDetails", []):
            if media.get("type") == "photo":
                img_url = media.get("media_url_https", "")
                if img_url:
                    images.append(img_url + "?format=jpg&name=large")
        text = data.get("text", "")
        text = re.sub(r"https://t\.co/\S+", "", text).strip()
        return images, text
    except Exception as e:
        print(f"  Error for {tweet_id}: {e}")
        return [], ""

def main():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            existing = json.load(f)
    except Exception:
        existing = []

    # /photo/1 などのサブURLを除去
    before = len(existing)
    existing = [t for t in existing if re.search(r"/status/(\d+)$", t.get("url", ""))]
    removed = before - len(existing)
    if removed:
        print(f"Removed {removed} sub-URL entries.")

    existing_ids = {t["id"] for t in existing}

    # posfieから最新ツイートIDを収集
    print("Fetching page 1...")
    first_html = fetch_page(1)
    total_pages = get_total_pages(first_html)
    print(f"Total pages: {total_pages}")

    all_urls = set()
    all_urls.update(extract_tweets(first_html))

    if existing_ids:
        pages_to_fetch = list(range(max(1, total_pages - 2), total_pages + 1))
    else:
        pages_to_fetch = list(range(2, total_pages + 1))

    for page in pages_to_fetch:
        print(f"Fetching page {page}/{total_pages}...")
        try:
            html = fetch_page(page)
            all_urls.update(extract_tweets(html))
            time.sleep(0.5)
        except Exception as e:
            print(f"Error on page {page}: {e}")

    if not existing_ids:
        for page in range(2, total_pages + 1):
            if page not in pages_to_fetch:
                print(f"Fetching page {page}/{total_pages}...")
                try:
                    html = fetch_page(page)
                    all_urls.update(extract_tweets(html))
                    time.sleep(0.3)
                except Exception as e:
                    print(f"Error on page {page}: {e}")

    new_count = 0
    for url in all_urls:
        m = re.search(r"/status/(\d+)$", url)
        tweet_id = m.group(1) if m else ""
        if tweet_id and tweet_id not in existing_ids:
            existing.append({"url": url, "id": tweet_id, "images": [], "text": ""})
            existing_ids.add(tweet_id)
            new_count += 1

    print(f"Added {new_count} new tweet entries.")

    # 画像未取得のツイートを処理
    need_media = [t for t in existing if not t.get("images")]
    print(f"Fetching media for {len(need_media)} tweets (batch: {BATCH_SIZE})...")
    processed = 0
    for tweet in need_media[:BATCH_SIZE]:
        images, text = get_tweet_media(tweet["id"])
        tweet["images"] = images
        tweet["text"] = text
        processed += 1
        if processed % 10 == 0:
            print(f"  {processed}/{min(len(need_media), BATCH_SIZE)} done")
        time.sleep(0.3)

    print(f"Media fetched for {processed} tweets.")

    existing.sort(key=lambda t: int(t["id"]) if t["id"].isdigit() else 0)

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    remaining = len([t for t in existing if not t.get("images")])
    print(f"Total: {len(existing)} tweets. Remaining without media: {remaining}")

if __name__ == "__main__":
    main()
