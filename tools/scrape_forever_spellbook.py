"""Scrapes the WoW: Forever spellbook for all nine classes into tools/data/forever_spellbook.json.

    python tools/scrape_forever_spellbook.py

Source: foreverchanges.pro/spellbook/<class> (built from the Forever beta client; highest rank per spell,
exact tooltip text). Spells marked "Not in Forever" are skipped. Re-run when Forever patches change spells,
then run tools/test_spellbook.py.
"""
import html
import json
import os
import re
import urllib.request

CLASSES = ("warrior", "paladin", "hunter", "rogue", "priest", "shaman", "mage", "warlock", "druid")
URL = "https://foreverchanges.pro/spellbook/{}"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "forever_spellbook.json")

ENTRY = re.compile(r'<li class="xi-kind-(?P<kind>[\w-]+)">(?P<body>.*?)</li>', re.S)
FIELD = {
    "name": re.compile(r'<strong class="xi-name">(.*?)</strong>', re.S),
    "rank": re.compile(r"<small>(.*?)</small>", re.S),
    "status": re.compile(r"<em>(.*?)</em>", re.S),
    "tooltip": re.compile(r"<span>(.*?)</span>", re.S),  # the Forever text; Classic text is <span class="xi-classic">
}


def text(fragment):
    return html.unescape(re.sub(r"<[^>]+>", "", fragment)).strip()


def fetch(cls):
    request = urllib.request.Request(URL.format(cls), headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def parse(cls, page):
    spells = []
    for match in ENTRY.finditer(page):
        if match.group("kind") == "missing":  # "Not in Forever"
            continue
        body = match.group("body")
        fields = {key: pattern.search(body) for key, pattern in FIELD.items()}
        if not fields["name"] or not fields["tooltip"]:
            continue
        spells.append({
            "class": cls,
            "name": text(fields["name"].group(1)),
            "rank": text(fields["rank"].group(1)) if fields["rank"] else "",
            "kind": match.group("kind"),
            "tooltip": text(fields["tooltip"].group(1)),
        })
    return spells


def main():
    spells = []
    for cls in CLASSES:
        found = parse(cls, fetch(cls))
        print(f"{cls:8} {len(found)} spells")
        spells.extend(found)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(spells, f, indent=1, ensure_ascii=False)
    print(f"wrote {len(spells)} spells to {os.path.relpath(OUT)}")


if __name__ == "__main__":
    main()
