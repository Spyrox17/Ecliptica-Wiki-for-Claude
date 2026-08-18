#!/usr/bin/env python3
"""
Ecliptica Wiki Sync
--------------------
Downloads every page on the Ecliptica Miraheze wiki as clean wikitext,
one .txt file per page, into an output folder. Designed to be re-run
on a schedule (see run_daily.ps1 / cron) so you can just git commit
the output folder and see exactly what changed each time.

Usage:
    python sync_wiki.py

Output:
    ./wiki_pages/<Page_Name>.txt   for every page on the wiki
    ./wiki_pages/_index.json       metadata: page list + last revision ids
"""

import json
import os
import re
import time
import urllib.request
import urllib.parse

API_URL = "https://ecliptica.miraheze.org/w/api.php"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wiki_pages")
USER_AGENT = "EclipticaWikiSync/1.0 (personal archival script)"


def api_get(params: dict) -> dict:
    """Make a GET request to the MediaWiki API and return parsed JSON."""
    params = {**params, "format": "json"}
    url = f"{API_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_all_page_titles() -> list[str]:
    """Fetch every page title in the main namespace, handling pagination."""
    titles = []
    apcontinue = None
    while True:
        params = {
            "action": "query",
            "list": "allpages",
            "aplimit": "500",
            "apnamespace": "0",  # main content namespace only
        }
        if apcontinue:
            params["apcontinue"] = apcontinue

        data = api_get(params)
        pages = data.get("query", {}).get("allpages", [])
        titles.extend(p["title"] for p in pages)

        if "continue" in data:
            apcontinue = data["continue"]["apcontinue"]
        else:
            break
        time.sleep(0.3)  # be polite to the API

    return titles


def get_page_wikitext(title: str) -> tuple[str, int]:
    """Fetch raw wikitext + latest revision id for a single page."""
    params = {
        "action": "query",
        "titles": title,
        "prop": "revisions",
        "rvslots": "main",
        "rvprop": "content|ids",
    }
    data = api_get(params)
    pages = data.get("query", {}).get("pages", {})
    for _, page in pages.items():
        revisions = page.get("revisions", [])
        if not revisions:
            return "", 0
        rev = revisions[0]
        content = rev["slots"]["main"]["*"]
        revid = rev["revid"]
        return content, revid
    return "", 0


def safe_filename(title: str) -> str:
    """Turn a wiki page title into a safe filename."""
    name = title.replace(" ", "_")
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    return name + ".txt"


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("Fetching page list from Ecliptica wiki...")
    titles = get_all_page_titles()
    print(f"Found {len(titles)} pages.")

    index = {}
    for i, title in enumerate(titles, start=1):
        print(f"[{i}/{len(titles)}] {title}")
        try:
            content, revid = get_page_wikitext(title)
        except Exception as e:
            print(f"  ! Failed to fetch '{title}': {e}")
            continue

        filename = safe_filename(title)
        filepath = os.path.join(OUTPUT_DIR, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        index[title] = {"file": filename, "revid": revid}
        time.sleep(0.3)  # be polite to the API

    index_path = os.path.join(OUTPUT_DIR, "_index.json")
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)

    print(f"\nDone. {len(index)} pages saved to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()