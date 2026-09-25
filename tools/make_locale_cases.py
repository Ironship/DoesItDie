"""Builds tools/data/locale_cases.lua, the cases tools/test_locale.lua runs through the parser.

    python tools/make_locale_cases.py

Input: tools/data/spell_descriptions.json, English and German descriptions of every rank of the DoTs (and of
the spells DoesItDie deliberately ignores or must not mistake for DoTs):
  * "wowhead-classic": Classic Era tooltips from Wowhead (the Blizzard API has no Classic Era spell text)
  * "static-classic1x-eu": Classic Era rogue poison items from the Blizzard API
  * "static-eu": Retail, from the Blizzard API (thousands separators and decimal commas)
  * "wowhead-cata": Cataclysm, for the "Bane" names Forever uses

The expected values are read from each text here, with one hand-written regular expression per spell and
language, and the school, tick interval and ignore list stated per spell. None of this comes from the addon's
own patterns, so a test failure means the addon and this reading disagree.

Two clean-ups are applied to the text first, because the game never shows them: Wowhead prints some numbers as
formulas ("[6 * 1 * (7)]", evaluated here), and non-breaking spaces where the game has plain ones.

English numbers are read the way the unchanged English parser reads them ("1,132" as 132): English behaviour
must not change, and Forever's Classic-style text has no separators.
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data", "spell_descriptions.json")
OUT = os.path.join(HERE, "data", "locale_cases.lua")

# The addon's name tables, by English name (what the tables are expected to contain in every language).
TWO_SECOND_TICKS = {"Insect Swarm", "Curse of Agony", "Bane of Agony", "Fireball", "Holy Fire", "Rip", "Rupture"}
AGONY = {"Curse of Agony", "Bane of Agony"}
SCHOOL_BY_NAME = {"Siphon Life": 32}
IGNORED = {
    "Rain of Fire", "Hellfire", "Blizzard", "Flamestrike", "Consecration", "Hurricane", "Volley", "Drain Life",
    "Drain Soul", "Drain Mana", "Health Funnel", "Mind Flay", "Arcane Missiles", "Starshards", "Immolation Trap",
    "Explosive Trap", "Wyvern Sting",
}

# Number shapes. German totals may carry thousands dots ("1.132"), durations a decimal comma ("7,1").
T = r"(?P<t>\d+)"
ED = r"(?P<d>\d+(?:\.\d+)?)"
N = r"(?P<t>\d+(?:\.\d{3})*)"
D = r"(?P<d>\d+(?:,\d+)?)"

SHADOW, FIRE, NATURE, FROST, ARCANE, HOLY, PHYSICAL, FROSTFIRE = 32, 4, 8, 16, 64, 2, 1, 20


def dot(school, *patterns):
    return ("dot", school, patterns)


def every(school, *patterns):
    return ("every", school, patterns)


def fin(*patterns):
    return ("fin", None, patterns)


NONE = None

# (English name, source group) -> {"en": spec, "de": spec}. A spec of None means "not a DoT" (nothing parsed).
CLASSIC = {
    "Corruption": {"en": dot(SHADOW, rf"causing {T} Shadow damage over {ED} sec"),
                   "de": dot(SHADOW, rf"verursacht {D} Sek\. lang {N} Punkt\(e\) Schattenschaden")},
    "Curse of Agony": {"en": dot(SHADOW, rf"causing {T} Shadow damage over {ED} sec"),
                       "de": dot(SHADOW, rf"fügt {D} Sek\. lang {N} Punkt\(e\) Schattenschaden zu")},
    "Immolate": {"en": dot(FIRE, rf"additional {T} Fire damage over {ED} sec"),
                 "de": dot(FIRE, rf"im Verlauf von {D} Sek\. insgesamt {N} zusätzlichen Feuerschaden")},
    "Siphon Life": {
        "en": every(PHYSICAL, r"Transfers (?P<a>\d+) health from the target to the caster every (?P<e>\d+) sec\.\s+Lasts (?P<l>\d+) sec"),
        "de": every(PHYSICAL, r"Überträgt alle (?P<e>\d+) Sek\. (?P<a>\d+) Punkt\(e\) Gesundheit vom Ziel auf den Zaubernden\. Hält (?P<l>\d+) Sek\. lang an")},
    "Curse of Doom": {"en": NONE, "de": NONE},
    "Drain Life": {"en": NONE, "de": NONE},
    "Drain Soul": {"en": dot(SHADOW, rf"causing {T} Shadow damage over {ED} sec"),
                   "de": dot(SHADOW, rf"verursacht {D} Sek\. lang {N} Punkt\(e\) Schattenschaden")},
    "Drain Mana": {"en": NONE, "de": NONE},
    "Health Funnel": {"en": NONE, "de": NONE},
    "Rain of Fire": {"en": dot(FIRE, rf"for {T} Fire damage over {ED} sec"),
                     "de": dot(FIRE, rf"der {D} Sek\. lang Feinde im Wirkungsbereich mit {N} Punkt\(en\) Feuerschaden")},
    "Hellfire": {"en": NONE, "de": NONE},
    "Shadow Word: Pain": {"en": dot(SHADOW, rf"causes {T} Shadow damage over {ED} sec"),
                          "de": dot(SHADOW, rf"das {D} Sek\. lang {N} Punkt\(e\) Schattenschaden zufügt")},
    "Devouring Plague": {"en": dot(SHADOW, rf"causes {T} Shadow damage over {ED} sec"),
                         "de": dot(SHADOW, rf"fügt so {D} Sek\. lang {N} Punkt\(e\) Schattenschaden zu")},
    "Holy Fire": {"en": dot(HOLY, rf"additional {T} Holy damage over {ED} sec"),
                  "de": dot(HOLY, rf"sowie {D} Sek\. lang zusätzlich {N} Punkt\(e\) Heiligschaden")},
    "Renew": {"en": NONE, "de": NONE},
    "Rejuvenation": {"en": NONE, "de": NONE},
    "Regrowth": {"en": NONE, "de": NONE},
    "Mind Flay": {"en": dot(SHADOW, rf"causing {T} Shadow damage over {ED} sec"),
                  "de": dot(SHADOW, rf"{N} Schattenschaden im Verlauf von {D} Sek\.")},
    "Starshards": {"en": dot(ARCANE, rf"causing {T} Arcane damage over {ED} sec"),
                   "de": dot(ARCANE, rf"verursacht {D} Sek\. lang {N} Punkt\(e\) Arkanschaden")},
    "Moonfire": {"en": dot(ARCANE, rf"additional {T} Arcane damage over {ED} sec"),
                 "de": dot(ARCANE, rf"sowie {D} Sek\. lang {N} Punkt\(e\) zusätzlichen Arkanschaden")},
    "Insect Swarm": {"en": dot(NATURE, rf"causing {T} Nature damage over {ED} sec"),
                     "de": dot(NATURE, rf"über {D} Sek\. {N} Naturschaden")},
    "Rake": {"en": dot(PHYSICAL, rf"additional {T} damage over {ED} sec"),
             "de": dot(PHYSICAL, rf"{N} Punkt\(e\) zusätzlichen Schaden im Verlauf von {D} Sek\.")},
    "Rip": {"en": fin(r"(\d+) points?\s*: (\d+) damage over (\d+) sec"),
            "de": fin(r"(\d+) Punkte?: (\d+) Schaden im Verlauf von (\d+) Sek\.")},
    "Hurricane": {"en": NONE,
                  "de": every(NATURE, r"alle (?P<e>\d+) Sek\. (?P<a>\d+) Naturschaden zufügt.*Hält (?P<l>\d+) Sek\. lang an")},
    "Serpent Sting": {"en": dot(NATURE, rf"causing {T} Nature damage over {ED} sec"),
                      "de": dot(NATURE, rf"verursacht {D} Sek\. lang {N} Naturschaden")},
    "Immolation Trap": {"en": dot(FIRE, rf"for {T} Fire damage over {ED} sec"),
                        "de": dot(FIRE, rf"die {D} Sek\. lang dem ersten sich nähernden Feind {N} Punkt\(e\) Feuerschaden")},
    "Explosive Trap": {"en": dot(FIRE, rf"{T} additional Fire damage over {ED} sec"),
                       "de": dot(FIRE, rf"verbrennt {D} Sek\. lang alle Feinde in einem Umkreis von 10 Metern, indem sie ihnen {N} zusätzlichen Feuerschaden")},
    "Volley": {"en": NONE, "de": NONE},
    "Wyvern Sting": {"en": dot(NATURE, rf"causes {T} Nature damage over {ED} sec"),
                     "de": dot(NATURE, rf"der Stich {N} Naturschaden im Verlauf von {D} Sek\.",
                               rf"der Stich {D} Sek\. lang {N} Naturschaden")},
    "Rupture": {"en": fin(r"(\d+) points?\s*: (\d+) damage over (\d+) secs"),
                "de": fin(r"(\d+) Punkte?: (\d+) Schaden über (\d+) Sekunden")},
    "Garrote": {"en": dot(PHYSICAL, rf"causing {T} damage over {ED} sec"),
                "de": dot(PHYSICAL, rf"verursacht {D} Sek\. lang {N} Schaden, erhöht")},
    "Eviscerate": {"en": NONE, "de": NONE},
    "Sinister Strike": {"en": NONE, "de": NONE},
    "Rend": {"en": dot(PHYSICAL, rf"bleed for {T} damage over {ED} sec"),
             "de": dot(PHYSICAL, rf"lässt es {D} Sek\. lang bluten und fügt damit {N} Punkt\(e\) Schaden zu")},
    "Fireball": {"en": dot(FIRE, rf"additional {T} Fire damage over {ED} sec"),
                 "de": dot(FIRE, rf"sowie {D} Sek\. lang {N} Punkt\(e\) zusätzlichen Feuerschaden")},
    "Pyroblast": {"en": dot(FIRE, rf"additional {T} Fire damage over {ED} sec"),
                  "de": dot(FIRE, rf"zusätzlich {D} Sek\. lang {N} Punkt\(e\) zusätzlichen Feuerschaden")},
    "Blizzard": {"en": dot(FROST, rf"doing {T} Frost damage over {ED} sec"),
                 "de": dot(FROST, rf"verursachen {D} Sek\. lang insgesamt {N} Frostschaden")},
    "Flamestrike": {"en": dot(FIRE, rf"additional {T} Fire damage over {ED} sec"),
                    "de": dot(FIRE, rf"und zusätzlich {D} Sek\. lang {N} Punkt\(e\) Feuerschaden")},
    "Arcane Missiles": {"en": NONE, "de": NONE},
    "Flame Shock": {"en": dot(FIRE, rf"and {T} Fire damage over {ED} sec"),
                    "de": dot(FIRE, rf"sowie {D} Sek\. lang {N}(?: Punkt\(e\))? Feuerschaden")},
    "Consecration": {"en": dot(HOLY, rf"doing {T} Holy damage over {ED} sec"),
                     "de": dot(HOLY, rf"fügt {D} Sek\. lang Feinden, die das Gebiet betreten, {N} Punkt\(e\) Heiligschaden")},
}
for poison in ["Deadly Poison", "Deadly Poison II", "Deadly Poison III", "Deadly Poison IV", "Deadly Poison V",
               "Instant Poison", "Instant Poison II", "Instant Poison III", "Instant Poison IV", "Instant Poison V",
               "Instant Poison VI", "Mind-numbing Poison"]:
    CLASSIC[poison] = {"en": NONE, "de": NONE}  # weapon coatings

CATA = {
    "Bane of Agony": {"en": dot(SHADOW, rf"causing {T} Shadow damage over {ED} sec"),
                      "de": dot(SHADOW, rf"im Verlauf von {D} Sek\. {N} Schattenschaden")},
    "Bane of Doom": {"en": NONE, "de": NONE},  # "every 15 sec ... Lasts for 1 min": minutes aren't read
    "Immolate": {"en": dot(FIRE, rf"additional {T} Fire damage over {ED} sec"),
                 "de": dot(FIRE, rf"im Verlauf von {D} Sek\. insgesamt {N} Feuerschaden")},
    "Corruption": {"en": dot(SHADOW, rf"causing {T} Shadow damage over {ED} sec"),
                   "de": dot(SHADOW, rf"{D} Sek\. lang insgesamt {N} Schattenschaden")},
    "Frostfire Bolt": {"en": dot(PHYSICAL, rf"{T} additional damage over {ED} sec"),
                       "de": dot(PHYSICAL, rf"im Verlauf von {D} Sek\. zusätzlich {N} Schaden\.")},
}

RETAIL = {
    "Corruption": {"en": dot(SHADOW, rf"{T} Shadow damage over {ED} sec"),
                   "de": dot(SHADOW, rf"im Verlauf von {D} Sek\. {N} zusätzlichen Schattenschaden")},
    "Agony": {"en": dot(SHADOW, rf"{T} Shadow damage over {ED} sec"),
              "de": dot(SHADOW, rf"im Verlauf von {D} Sek\. {N} Schattenschaden")},
    "Immolate": {"en": dot(FIRE, rf"{T} Fire damage over {ED} sec"),
                 "de": dot(FIRE, rf"im Verlauf von {D} Sek\. zusätzlich {N} Feuerschaden")},
    "Doom": {"en": NONE, "de": NONE},
    "Rain of Fire": {"en": dot(FIRE, rf"{T} Fire damage over {ED} sec"),
                     "de": dot(FIRE, rf"im Verlauf von {D} Sek\. {N} Feuerschaden")},
    "Shadow Word: Pain": {"en": dot(SHADOW, rf"{T} Shadow damage over {ED} sec"),
                          "de": dot(SHADOW, rf"im Verlauf von {D} Sek\. zusätzlich {N} Schattenschaden")},
    "Holy Fire": {"en": dot(HOLY, rf"{T} Holy damage over {ED} sec"),
                  "de": dot(HOLY, rf"zusätzlich im Verlauf von {D} Sek\. {N} Heiligschaden")},
    "Renew": {"en": NONE, "de": NONE},
    "Mind Flay": {"en": dot(SHADOW, rf"{T} Shadow damage over {ED} sec"),
                  "de": dot(SHADOW, rf"im Verlauf von {D} Sek\. {N} Schattenschaden")},
    "Moonfire": {"en": dot(ARCANE, rf"{T} Arcane damage over {ED} sec"),
                 "de": dot(ARCANE, rf"im Verlauf von {D} Sek\. mit zusätzlich {N} Arkanschaden")},
    "Rake": {"en": dot(PHYSICAL, rf"{T} Bleed damage over {ED} sec"),
             "de": dot(PHYSICAL, rf"im Verlauf von {D} Sek\. zusätzlich {N} Blutungsschaden")},
    # The English reader needs "damage over" in finisher lines, Retail writes "8 over 1 sec".
    "Rip": {"en": NONE, "de": fin(r"(\d+) Punkte?: (\d+) Schaden im Verlauf von (\d+) Sek\.")},
    "Rejuvenation": {"en": NONE, "de": NONE},
    "Regrowth": {"en": NONE, "de": NONE},
    "Rupture": {"en": NONE, "de": fin(r"(\d+) Punkte?: (\d+) im Verlauf von (\d+) Sek\.")},
    "Garrote": {"en": dot(PHYSICAL, rf"{T} Bleed damage over {ED} sec"),
                "de": dot(PHYSICAL, rf"im Verlauf von {D} Sek\. {N} Blutungsschaden")},
    "Dispatch": {"en": NONE, "de": NONE},
    "Eviscerate": {"en": NONE, "de": NONE},
    # The English reader skips "Coats a weapon"; Retail says "Coats your weapons", so English reads the proc.
    "Deadly Poison": {"en": dot(NATURE, rf"for {T} Nature damage over {ED} sec"), "de": NONE},
    "Wound Poison": {"en": NONE, "de": NONE},
    "Instant Poison": {"en": NONE, "de": NONE},
    "Sinister Strike": {"en": NONE, "de": NONE},
    "Rend": {"en": dot(PHYSICAL, rf"{T} Bleed damage over {ED} sec"),
             "de": dot(PHYSICAL, rf"zusätzlich im Verlauf von {D} Sek\. {N} Blutungsschaden")},
    "Fireball": {"en": NONE, "de": NONE},
    "Pyroblast": {"en": NONE, "de": NONE},
    "Flamestrike": {"en": NONE, "de": NONE},
    "Arcane Missiles": {"en": NONE,
                        "de": dot(ARCANE, rf"im Verlauf von {D} Sek\. 5 Wellen arkaner Geschosse auf den Gegner ab, die insgesamt {N} Arkanschaden")},
    "Consecration": {"en": dot(HOLY, rf"{T} Holy damage over {ED} sec"),
                     "de": dot(HOLY, rf"im Verlauf von {D} Sek\. {N} Heiligschaden")},
    "Siphon Life": {"en": dot(SHADOW, rf"{T} Shadow damage over {ED} sec"),
                    "de": dot(SHADOW, rf"im Verlauf von {D} Sek\. {N} Schattenschaden")},
    "Drain Life": {"en": dot(SHADOW, rf"{T} Shadow damage over {ED} sec"),
                   "de": dot(SHADOW, rf"im Verlauf von {D} Sek\. {N} Schattenschaden")},
    "Drain Soul": {"en": dot(SHADOW, rf"{T} Shadow damage over {ED} sec"),
                   "de": dot(SHADOW, rf"im Verlauf von {D} Sek\. {N} Schattenschaden")},
    "Hurricane": {"en": NONE, "de": NONE},
    "Serpent Sting": {"en": dot(NATURE, rf"additional {T} Nature damage over {ED} sec"),
                      "de": dot(NATURE, rf"zusätzlich {N} Naturschaden im Verlauf von {D} Sek\.")},
    "Volley": {"en": NONE,
               "de": dot(PHYSICAL, rf"im Verlauf von {D} Sek\. eine Pfeilsalve herabregnen, die allen Gegnern im Effektbereich bis zu {N} körperlichen Schaden")},
    "Deep Wounds": {"en": dot(PHYSICAL, rf"{T} Bleed damage over {ED} sec"),
                    "de": dot(PHYSICAL, rf"{D} Sek\. lang {N} Blutungsschaden")},
    "Blizzard": {"en": dot(FROST, rf"{T} Frost damage over {ED} sec"),
                 "de": dot(FROST, rf"im Verlauf von {D} Sek\. {N} Frostschaden")},
    "Flame Shock": {"en": dot(PHYSICAL, rf"{T} Volcanic damage over {ED} sec"),
                    "de": dot(PHYSICAL, rf"im Verlauf von {D} Sek\. {N} zusätzlichen Vulkanschaden")},
    "Frostfire Bolt": {"en": dot(FROSTFIRE, rf"{T} Frostfire damage over {ED} sec"),
                       "de": dot(FROSTFIRE, rf"im Verlauf von {D} Sek\. {N} zusätzlichen Frostfeuerschaden")},
}
# Retail talents and passives that share a name with a DoT but describe no DoT.
RETAIL_BY_ID = {i: {"en": NONE, "de": NONE} for i in
                (28829, 452999, 326646, 28716, 28744, 81297, 327980, 1249804, 113780, 343194, 11366)}
RETAIL_BY_ID[321711] = {"en": dot(FIRE, rf"{T} Fire damage over {ED} sec"),
                        "de": dot(FIRE, rf"{N} Feuerschaden im Verlauf von {D} Sek\.")}

GROUPS = {"wowhead-classic": CLASSIC, "static-classic1x-eu": CLASSIC, "wowhead-cata": CATA, "static-eu": RETAIL}


def evaluate_formulas(text):
    """Wowhead's "[6 * 1 * (7)]" -> "42" (the game prints the number)."""
    def value(match):
        v = eval(match.group(1), {"__builtins__": {}})  # digits and arithmetic only, see the pattern
        return str(int(round(v)))
    return re.sub(r"\[([\d\s.*+\-/()]+)\]", value, text)


def clean(text):
    return evaluate_formulas(text).replace("\xa0", " ")


def number(text, lang):
    return int(text.replace(".", "")) if lang == "de" else int(text)


def seconds(text):
    value = float(text.replace(",", "."))
    return int(value) if value == int(value) else value


def expect(spec, text, lang, family):
    """Returns (expected parse or False, per-point table or None)."""
    if spec is None:
        return False, None
    kind, school, patterns = spec
    if kind == "fin":
        for pattern in patterns:
            rows = re.findall(pattern, text)
            if rows:
                return None, {int(p): (number(t, lang), seconds(d)) for p, t, d in rows}
        raise SystemExit(f"no finisher lines in {family} ({lang}): {text!r}")
    for pattern in patterns:
        m = re.search(pattern, text, re.S)
        if not m:
            continue
        if kind == "dot":
            return {"total": number(m["t"], lang), "school": school, "duration": seconds(m["d"])}, None
        amount, each, lasts = int(m["a"]), seconds(m["e"]), seconds(m["l"])
        return {"total": amount * int(lasts / each + 0.5), "school": school, "duration": lasts, "interval": each}, None
    raise SystemExit(f"rule for {family} ({lang}) doesn't match: {text!r}")


def lua_string(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\r", "\\r").replace("\n", "\\n") + '"'


def lua_value(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, str):
        return lua_string(v)
    if isinstance(v, dict):
        return "{ " + ", ".join(f"{k} = {lua_value(x)}" for k, x in v.items()) + " }"
    return repr(v)


def main():
    rows = json.load(open(DATA, encoding="utf-8"))
    lines = ["-- Generated by tools/make_locale_cases.py from tools/data/spell_descriptions.json; don't edit by hand.",
             "-- expect = false: not a DoT (nothing parsed). fin: finisher, [combo points] = { total, duration }.",
             "return {"]
    count = 0
    for row in rows:
        family = row["en_name"]
        if not (row["en_description"] or row["de_description"]):
            continue  # proc and talent ranks without a description
        spec_by_lang = (RETAIL_BY_ID.get(row["id"]) if row["namespace"] == "static-eu" else None) \
            or GROUPS[row["namespace"]].get(family)
        if spec_by_lang is None:
            raise SystemExit(f"no rule for {family} ({row['namespace']} {row['id']})")
        for lang in ("en", "de"):
            desc = row[f"{lang}_description"]
            if not desc:
                continue  # proc and talent ranks without a description
            text = clean(desc)
            parsed, points = expect(spec_by_lang[lang], text, lang, family)
            case = {
                "id": row["id"], "source": row["namespace"], "lang": lang, "family": family,
                "name": row[f"{lang}_name"], "desc": text,
            }
            if points:
                case["fin"] = points
            else:
                if parsed:
                    parsed.setdefault("interval", 2 if family in TWO_SECOND_TICKS else 3)
                    parsed["school"] = SCHOOL_BY_NAME.get(family, parsed["school"])
                case["expect"] = parsed
            case["interval"] = 2 if family in TWO_SECOND_TICKS else 3  # for finishers: from the name table
            case["ignored"] = family in IGNORED
            case["shaped"] = family in AGONY
            case["finisher"] = ("Finishing move" in text) if lang == "en" else ("Finishing-Move" in text)
            award = re.search(r"Awards (\d+) combo point" if lang == "en" else r"Gewährt[^.]*?(\d+) Combopunkt", text)
            case["awarded"] = int(award.group(1)) if award else False
            count += 1
            parts = []
            for key, value in case.items():
                if key == "fin":
                    table = ", ".join(f"[{p}] = {{ {t}, {lua_value(d)} }}" for p, (t, d) in sorted(value.items()))
                    parts.append(f"fin = {{ {table} }}")
                else:
                    parts.append(f"{key} = {lua_value(value)}")
            lines.append("    { " + ", ".join(parts) + " },")
    lines.append("}")
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    print(f"{count} cases -> {os.path.relpath(OUT)}")


if __name__ == "__main__":
    main()
