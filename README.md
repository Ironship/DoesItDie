# DoesItDie (DE)

A fork of [DoesItDie](https://github.com/swirllyman/DoesItDie) by Joe Greive (swirllyman), a WoW: Forever addon
that marks on the target's health bar the damage your DoTs still have to deal. All of the addon is his work and
stays under his MIT licence (see `LICENSE`).

This branch makes it work on a German client. `DoesItDie/Locale.lua` reads German spell descriptions
("verursacht 12 Sek. lang 40 Punkt(e) Schattenschaden", "1.132", "7,1 Sek.") and gives the name-keyed tables
their German names, plus whatever name the client reports for each spell ID. English descriptions are read
exactly as before: the English patterns run first and are unchanged.

Install the `DoesItDie` folder as `Interface\AddOns\DoesItDie-DE` (it loads `DoesItDie-DE.toc`, shown as
"DoesItDie (DE)"), and remove the original `DoesItDie` so the two don't both load.

Tests: `python tools/test_locale.py` (Lua 5.1 through lupa) or `lua tools/test_locale.lua` runs 340 German and
340 English descriptions through the parser; `python tools/make_locale_cases.py` rebuilds its cases from
`tools/data/spell_descriptions.json`. The other `tools/test_*.py` scripts work as upstream.
