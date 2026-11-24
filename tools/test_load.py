"""Smoke test: loads the whole addon (every file in the .toc) in Lua with a fake WoW environment, then drives it
like a player: ADDON_LOADED, /did, every tab, every preset, checkboxes, sliders, dropdowns, Simulate fight,
closing the window. Fails on any Lua error and checks a few results.

    pip install lupa
    python tools/test_load.py

The fake frames accept any method (unknown ones do nothing) and record what matters: scripts, text, values,
shown state. It catches runtime mistakes (nil calls, typos, wrong arguments to our own functions), not
visual ones.
"""
import os
import sys

import locale  # noqa: E402
locale.setlocale(locale.LC_CTYPE, "C")  # as in WoW: Lua's %d and %s follow the C library's locale
from lupa.lua51 import LuaRuntime  # WoW runs Lua 5.1

HERE = os.path.dirname(os.path.abspath(__file__))
ADDON = os.path.join(HERE, "..", "DoesItDie")

FAKE_WOW = r"""
now = 1000
chat = {}
frames = {}
tickers = {}

local methods = {}
local function mock(kind, parent)
    local o = { kind = kind, parent = parent, scripts = {}, shown = true, width = 100, height = 20, children = {} }
    if parent and type(parent) == "table" and parent.children then table.insert(parent.children, o) end
    table.insert(frames, o)
    -- Unknown methods (CamelCase, like WoW's) do nothing; unknown fields are nil like a real table.
    return setmetatable(o, { __index = function(t, k)
        if methods[k] then return methods[k] end
        if type(k) == "string" and k:match("^%u") then return function() end end
    end })
end
FakeMock = mock

function methods.SetScript(self, name, fn) self.scripts[name] = fn end
function methods.GetScript(self, name) return self.scripts[name] end
function methods.HookScript(self, name, fn) self.scripts[name] = fn end
function methods.Show(self)
    local was = self.shown
    self.shown = true
    if not was and self.scripts.OnShow then self.scripts.OnShow(self) end
end
function methods.Hide(self)
    local was = self.shown
    self.shown = false
    if was and self.scripts.OnHide then self.scripts.OnHide(self) end
end
function methods.SetShown(self, v) if v then self:Show() else self:Hide() end end
function methods.IsShown(self) return self.shown end
function methods.GetObjectType(self) return self.kind end
function methods.IsVisible(self)
    if not self.shown then return false end
    local parent = self.parent
    if type(parent) == "table" and parent.shown ~= nil then return methods.IsVisible(parent) end
    return true
end
function methods.SetText(self, t) self.text = t end
function methods.GetText(self) return self.text end
function methods.SetSize(self, w, h) self.width, self.height = w, h end
function methods.SetWidth(self, w) self.width = w end
function methods.SetHeight(self, h) self.height = h end
function methods.GetWidth(self) return self.width end
function methods.GetHeight(self) return self.height end
function methods.GetStringWidth(self) return #(self.text or "") * 6 end
function methods.GetFont(self) return "Fonts\\FRIZQT__.TTF", 12, "" end
function methods.SetFrameStrata(self, v) self.strata = v end
function methods.GetFrameStrata(self) return self.strata or "MEDIUM" end
function methods.SetFrameLevel(self, v) self.level = v end
function methods.GetFrameLevel(self) return self.level or 5 end
function methods.GetChildren(self) return end
function methods.SetClipsChildren(self, v) self.clips = v end
function methods.IsMouseOver(self) return false end
function methods.GetStatusBarTexture(self) self._tex = self._tex or mock("tex", self); return self._tex end
function methods.GetThumbTexture(self) self._thumb = self._thumb or mock("thumb", self); return self._thumb end
function methods.CreateTexture(self) return mock("texture", self) end
function methods.CreateMaskTexture(self) return mock("mask", self) end
function methods.CreateFontString(self) return mock("fontstring", self) end
function methods.CreateAnimationGroup(self) return mock("animgroup", self) end
function methods.CreateAnimation(self) return mock("anim", self) end
function methods.SetChecked(self, v) self.checked = v end
function methods.GetChecked(self) return self.checked end
function methods.SetMinMaxValues(self, a, b) self.min, self.max = a, b end
function methods.GetMinMaxValues(self) return self.min, self.max end
function methods.SetValue(self, v)
    if self.min and type(v) == "number" then v = math.max(self.min, math.min(self.max, v)) end
    self.value = v
    if self.scripts.OnValueChanged then self.scripts.OnValueChanged(self, v, false) end
end
function methods.GetValue(self) return self.value or 0 end
function methods.SetReverseFill(self, v) self.reverseFill = v end
function methods.GetReverseFill(self) return self.reverseFill == true end
function methods.RegisterEvent(self, e) self.events = self.events or {}; self.events[e] = true end
function methods.RegisterUnitEvent(self, e) self.events = self.events or {}; self.events[e] = true end
function methods.GetDebugName(self) return self.name or "mock" end
function methods.GetName(self) return self.name end
function methods.GetParent(self) return self.parent end
function methods.SetParent(self, parent)
    if self.parent and type(self.parent) == "table" and self.parent.children then
        for i, child in ipairs(self.parent.children) do
            if child == self then table.remove(self.parent.children, i); break end
        end
    end
    self.parent = parent
    if parent and type(parent) == "table" and parent.children then
        table.insert(parent.children, self)
    end
end
function methods.SetAllPoints(self, target) self.allPoints = target end

function CreateFrame(kind, name, parent, template)
    local f = mock(kind, parent)
    f.name, f.template = name, template
    if kind ~= "Frame" or name then f.shown = true end
    if name then _G[name] = f end
    return f
end
UIParent = mock("UIParent")
GameTooltip = mock("GameTooltip")
GameFontNormalSmall = mock("font")
DEFAULT_CHAT_FRAME = mock("chat")
function DEFAULT_CHAT_FRAME.AddMessage(self, msg) table.insert(chat, msg) end
SlashCmdList = {}
UISpecialFrames = {}
Settings = {
    RegisterCanvasLayoutCategory = function() return mock("category") end,
    RegisterAddOnCategory = function() end,
}
C_Timer = {
    After = function(t, fn) end,
    NewTicker = function(t, fn)
        local ticker = { fn = fn, cancelled = false }
        function ticker:Cancel() self.cancelled = true end
        table.insert(tickers, ticker)
        return ticker
    end,
}
local SPELLS = {
    [172] = { "Corruption", "Corrupts the target, causing 40 Shadow damage over 12 sec." },
    [348] = { "Immolate", "Burns the enemy for 11 Fire damage and then an additional 20 Fire damage over 15 sec." },
}
C_Spell = {
    GetSpellName = function(id) return SPELLS[id] and SPELLS[id][1] or "Spell" end,
    GetSpellDescription = function(id) return SPELLS[id] and SPELLS[id][2] or "" end,
}
Enum = { PowerType = { ComboPoints = 4 } }
function GetTime() return now end
targetGuid = nil -- set later: the target and nameplate1 are then the same mob
function UnitExists(unit) return unit == "nameplate1" or (unit == "target" and targetGuid ~= nil) end
function UnitCanAttack() return true end
function IsInInstance() return false, "none" end
local plate = mock("Frame")
FakePlate = plate
plate.UnitFrame = mock("Frame", plate)
plate.UnitFrame.healthBar = mock("StatusBar", plate.UnitFrame)
C_NamePlate = { GetNamePlateForUnit = function(unit) if unit == "nameplate1" then return plate end end }
function UnitGUID(unit) if unit == "target" or unit == "nameplate1" then return targetGuid end end
function UnitIsDead() return false end
function UnitClass() return "Mage", "MAGE" end
combat = false
function UnitAffectingCombat() return combat end
function InCombatLockdown() return combat end
function UnitHealth() return 100 end
function UnitHealthMax() return 100 end
function hooksecurefunc() end
function HideUIPanel() end
function CreateColor(...) return { ... } end
function wipe(t) for k in pairs(t) do t[k] = nil end return t end
function strlower(s) return string.lower(s) end
function strtrim(s) return (s:gsub("^%s+", ""):gsub("%s+$", "")) end
function date() return "12:00:00" end
unpack = unpack or table.unpack
"""

HELPERS = r"""
local H = {}
function H.load(path, src, ns)
    local fn, err = (loadstring or load)(src, "@" .. path)
    if not fn then error(err) end
    fn("DoesItDie", ns)
end
function H.fire(event, ...)
    for _, f in ipairs(frames) do
        if f.events and f.events[event] and f.scripts.OnEvent then f.scripts.OnEvent(f, event, ...) end
    end
end
function H.update(elapsed)
    now = now + elapsed
    for _, f in ipairs(frames) do
        if f.scripts.OnUpdate then f.scripts.OnUpdate(f, elapsed) end
    end
end
-- The same in reverse order: WoW doesn't promise an order between frames' OnUpdate scripts.
function H.updateReversed(elapsed)
    now = now + elapsed
    for i = #frames, 1, -1 do
        local f = frames[i]
        if f.scripts.OnUpdate then f.scripts.OnUpdate(f, elapsed) end
    end
end
-- The clickable owner of a visible text (buttons with SetText, or a button whose child font string has it).
function H.clickText(text)
    for _, f in ipairs(frames) do
        if f.text == text then
            local target = f.scripts.OnClick and f or f.parent
            if target and target.scripts and target.scripts.OnClick then
                target.scripts.OnClick(target)
                return true
            end
        end
    end
    error("nothing clickable with text: " .. text)
end
-- The row whose label is `text`: returns its first child widget of the given kind.
function H.rowWidget(text, kind)
    for _, f in ipairs(frames) do
        if f.kind == "fontstring" and f.text == text and f.parent then
            for _, child in ipairs(f.parent.children) do
                if child.kind == kind then return child end
            end
        end
    end
    error("no " .. kind .. " in row " .. text)
end
function H.shownMenuEntries()
    local out = {}
    for _, f in ipairs(frames) do
        if f.kind == "Button" and f.swatch and f.shown and f.scripts.OnClick then table.insert(out, f) end
    end
    return out
end
function H.runTickers(times)
    for _ = 1, times do
        for _, t in ipairs(tickers) do if not t.cancelled then now = now + 0.5; t.fn() end end
    end
end
return H
"""

lua = LuaRuntime(unpack_returned_tuples=True)
lua.execute(FAKE_WOW)
H = lua.execute(HELPERS)
G = lua.globals()
failures = 0


def check(label, actual, expected):
    global failures
    ok = actual == expected
    failures += not ok
    print(f"{'PASS' if ok else 'FAIL'}  {label:<60} {actual}" + ("" if ok else f"   (expected {expected})"))


def step(label, fn):
    global failures
    try:
        fn()
        print(f"PASS  {label}")
    except Exception as e:  # a Lua error surfaces here
        failures += 1
        print(f"FAIL  {label}\n      {e}")


ns = lua.table()
toc = open(os.path.join(ADDON, "DoesItDie.toc"), encoding="utf-8").read().splitlines()
files = [line.strip() for line in toc if line.strip().endswith(".lua")]
for name in files:
    step(f"load {name}", lambda name=name: H.load(name, open(os.path.join(ADDON, name), encoding="utf-8").read(), ns))

ns.locale.collectStrings = True  # every text the window asks T for (see --dump-strings)
step("ADDON_LOADED", lambda: H.fire("ADDON_LOADED", "DoesItDie"))
check("defaults applied", G.DoesItDieDB.skullIcon, "cross")
# The window's own text: a test language with one translation, chosen as the window language.
ns.locale.register(lua.eval('{ tag = "xxXX", label = "Test", strings = { ["Live preview"] = "Vorschau (test)" } }'))
G.DoesItDieDB.uiLanguage = "xxXX"
check("a language with translations is offered", [e.id for e in ns.locale.windowLanguages().values()],
      ["auto", "enUS", "deDE", "ruRU", "xxXX"])
step("run the display loop with no target", lambda: H.update(0.2))
step("/did opens the window", lambda: G.SlashCmdList.DOESITDIE(""))
check("window shown", G.DoesItDieOptions.shown, True)
check("translated text shown in the window language", lua.eval("""function(frames)
    for _, f in ipairs(frames) do if f.text == "Vorschau (test)" then return true end end
    return false
end""")(lua.globals().frames), True)
check("untranslated text stays English", ns.locale.T("Simulate fight"), "Simulate fight")
step("display loop with the window's preview", lambda: H.update(0.2))

for tab in ("Kill icon", "Marker", "Effects", "Text", "Nameplates", "Focus", "Advanced"):
    step(f"open tab {tab}", lambda tab=tab: H.clickText(tab))

# Tab pages scroll when their rows don't fit (the Nameplates and Focus tabs used to run into the footer buttons).
# The mock has no layout, so the page is given the real settings area's height: 548 window - 52 header - 10 margin,
# minus 40 for the tab buttons and 40 for the footer.
SCROLL_TEST = lua.eval("""function(frames, label, visible)
    local page
    for _, f in ipairs(frames) do
        if f.kind == "ScrollFrame" and f.shown then page = f end
    end
    if not page then return "no page" end
    local content
    for _, c in ipairs(page.children) do if c.scrollWheel then content = c end end
    local bar
    for _, c in ipairs(page.children) do if c.kind == "Slider" then bar = c end end
    local offset = 0
    page.SetVerticalScroll = function(_, v) offset = v end
    page.GetVerticalScroll = function() return offset end
    page.height = visible
    page.scripts.OnShow(page)
    local fits = content.height <= visible
    -- A slider on the page: the wheel over it scrolls the page when the page scrolls.
    local slider
    for _, row in ipairs(content.children) do
        for _, c in ipairs(row.children) do if c.kind == "Slider" and not slider then slider = c end end
    end
    local before = slider and slider:GetValue()
    page.scripts.OnMouseWheel(page, -1)
    local scrolled = offset
    if slider then slider.scripts.OnMouseWheel(slider, -1) end
    local sliderMoved = slider and slider:GetValue() ~= before
    page.scripts.OnMouseWheel(page, -100)
    local atEnd = offset
    page.scripts.OnMouseWheel(page, 100)
    return string.format("fits=%s bar=%s scrolled=%s sliderMoved=%s end=%s back=%s", tostring(fits),
        tostring(bar.shown), tostring(scrolled > 0), tostring(sliderMoved),
        tostring(atEnd == math.max(0, content.height - visible)), tostring(offset == 0))
end""")
for tab, fits in (("Kill icon", True), ("Marker", True), ("Effects", True), ("Text", True), ("Nameplates", False),
                  ("Focus", False), ("Advanced", True)):
    H.clickText(tab)
    want = ("fits=true bar=false scrolled=false sliderMoved=%s end=true back=true"
            % ("nil" if tab == "Advanced" else "true") if fits else
            "fits=false bar=true scrolled=true sliderMoved=false end=true back=true")
    check(f"  {tab} tab page {'fits' if fits else 'scrolls'}", SCROLL_TEST(G.frames, tab, 548 - 52 - 10 - 80), want)


def copy_marker_look():
    H.clickText("Nameplates")
    G.DoesItDieDB.fillColor = "gold"
    H.clickText("Copy from Marker tab")


step("Nameplates: Copy from Marker tab", copy_marker_look)
check("  plate fill color copied from the marker", G.DoesItDieDB.plateFillColor, "gold")

for preset in ("Minimal", "Classic", "Debug", "Juicy"):
    step(f"apply preset {preset}", lambda p=preset: H.clickText(p))
    step(f"  display loop after {preset}", lambda: H.update(0.2))
check("Juicy preset set the fill", G.DoesItDieDB.fillTexture, "stripes")


def toggle_glow():
    box = H.rowWidget("Glow", "CheckButton")
    box.checked = False
    box.scripts.OnClick(box)


step("untick Glow", toggle_glow)
check("  glow setting off", G.DoesItDieDB.showGlow, False)


def set_slider(label, value):
    def run():
        H.rowWidget(label, "Slider").SetValue(H.rowWidget(label, "Slider"), value)
    return run


step("drag Size slider to 40", set_slider("Size", 40))
check("  icon size saved", G.DoesItDieDB.skullSize, 40)
step("drag Target health to 30", set_slider("Target health", 30))
step("drag DoT damage to 50", set_slider("DoT damage", 50))
step("display loop with a lethal preview", lambda: H.update(1.2))
check("  marker frame shown", G.DoesItDieRemaining.shown, True)
check("  marker filled to the DoT damage", round(G.DoesItDieRemaining.value or -1), 50)
check("  kill icon frame shown", G.DoesItDieSkull.shown, True)
check("  marker layered above the window's strata", G.DoesItDieRemaining.strata, "FULLSCREEN")


same = lua.eval("function(a, b) return rawequal(a, b) end")


def preview_plate_markers():
    # The mock nameplate is the window's only frame whose child StatusBar is sized 140x10.
    for f in G.frames.values():
        if f.kind == "Frame" and f.width == 140 and f.height == 26:
            return [c for c in f.children.values() if c.kind == "StatusBar" and c.width != 140]
    return []


markers_on_preview_plate = preview_plate_markers()
check("  preview nameplate got a marker", len(markers_on_preview_plate) >= 1, True)
check("  preview nameplate marker filled to the DoT damage",
      round(markers_on_preview_plate[0].value) if markers_on_preview_plate else None, 50)
preview_focus_bar = G.DoesItDieOptions.focusHealthBar
preview_focus_markers = [f for f in G.frames.values() if f.kind == "StatusBar" and f.allPoints is not None
                         and same(f.allPoints, preview_focus_bar)]
check("  preview focus frame got a marker", len(preview_focus_markers), 1)
check("  preview focus marker filled to the DoT damage",
      round(preview_focus_markers[0].value) if preview_focus_markers else None, 50)
check("  preview focus marker shown", preview_focus_markers[0].shown if preview_focus_markers else None, True)


def preview_focus_icon_window():
    mock_focus = preview_focus_bar.parent
    return next((c for c in mock_focus.children.values() if c.kind == "Frame" and c.clips), None)


G.DoesItDieDB.focusIconSize, G.DoesItDieDB.nameplateIconSize = 40, 18
step("focus kill icon size 40, nameplates' 18", lambda: H.update(0.2))
check("  the focus uses its own look", preview_focus_icon_window().width if preview_focus_icon_window() else None, 40)
step("Copy from Nameplates tab", lambda: (H.clickText("Focus"), H.clickText("Copy from Nameplates tab"),
                                          H.update(0.2)))
check("  copied the nameplates' icon size", G.DoesItDieDB.focusIconSize, 18)
check("  and their fill", G.DoesItDieDB.focusFillTexture, G.DoesItDieDB.plateFillTexture)
check("  but not their show mode", G.DoesItDieDB.focusMode, "markerIcon")
check("  preview follows", preview_focus_icon_window().width if preview_focus_icon_window() else None, 18)

# CurseForge request (2026-11-07): nameplate addons whose health drains to the right.
G.DoesItDieDB.plateFillDirection = "rightToLeft"
step("nameplate marker fills from the right", lambda: H.update(0.2))
plate_marker = preview_plate_markers()[0]
check("  mock plate drains to the right", G.DoesItDieOptions.plateHealthBar.reverseFill, True)
check("  plate marker fills from the right", plate_marker.reverseFill, True)
check("  focus marker unchanged", preview_focus_markers[0].reverseFill, False)
G.DoesItDieDB.plateFillDirection = "auto"
step("back to auto (the mock plate drains left again)", lambda: H.update(0.2))
check("  plate marker follows the bar: from the left", plate_marker.reverseFill, False)


def pick_outline_none():
    H.clickText("Marker")
    button = H.rowWidget("Outline", "Button")
    button.scripts.OnClick(button)
    entries = H.shownMenuEntries()
    for entry in entries.values():
        if entry.text and "None" in entry.text.text:
            entry.scripts.OnClick(entry)
            return
    raise AssertionError("no None entry in the outline menu")


step("pick Outline: None from the dropdown", pick_outline_none)
check("  outline style saved", G.DoesItDieDB.outlineStyle, "none")
step("display loop without outline", lambda: H.update(0.2))

step("Reset this tab (Marker)", lambda: H.clickText("Reset this tab"))
check("  outline back to default", G.DoesItDieDB.outlineStyle, "dashed")

def enter_combat():
    G.combat = True
    H.fire("PLAYER_REGEN_DISABLED")
    H.update(1.2)


def leave_combat():
    G.combat = False
    H.fire("PLAYER_REGEN_ENABLED")
    H.update(1.2)


step("enter combat with the window open", enter_combat)
check("  display back on the target frame (not the window's strata)", G.DoesItDieRemaining.strata != "FULLSCREEN", True)
check("  log says the preview stepped aside",
      any("PREVIEW off" in line for line in list(G.DoesItDieDB.log.values())[-5:]), True)
step("leave combat", leave_combat)
check("  preview has the display again", G.DoesItDieRemaining.strata, "FULLSCREEN")

step("start Simulate fight", lambda: H.clickText("Simulate fight"))
step("run the simulated fight", lambda: (H.runTickers(25), H.update(0.2)))
step("Flash button", lambda: H.clickText("Flash"))
step("Reset learned tick sizes", lambda: H.clickText("Reset"))
step("close the window", lambda: G.DoesItDieOptions.Hide(G.DoesItDieOptions))
check("window hidden", G.DoesItDieOptions.shown, False)
step("display loop back on the (absent) target", lambda: H.update(0.2))
def chat_text():
    return "\n".join(str(line) for line in G.chat.values())


step("/did help", lambda: G.SlashCmdList.DOESITDIE("help"))
step("/did skull", lambda: (G.SlashCmdList.DOESITDIE("skull"), H.update(0.2)))
step("/did line (markers off)", lambda: G.SlashCmdList.DOESITDIE("line"))
check("  markers off", G.DoesItDieDB.showMarkers, False)
step("/did line (markers on)", lambda: G.SlashCmdList.DOESITDIE("line"))
check("  markers on; no target frame in this fake UI, so it says so",
      chat_text().splitlines()[-1].endswith("health bar markers unavailable."), True)
step("/did debug twice", lambda: (G.SlashCmdList.DOESITDIE("debug"), G.SlashCmdList.DOESITDIE("debug")))
step("/did plates", lambda: G.SlashCmdList.DOESITDIE("plates"))
plate_lines = [line for line in G.DoesItDieDB.log.values() if "PLATES" in line]
check("  probe logged the fake nameplate", any("nameplate1" in line and "healthBar=UnitFrame.healthBar" in line
                                                and "anchorPlate=ok" in line for line in plate_lines), True)
check("  probe summary", plate_lines[-1].split("PLATES ")[1], "probe done: 1 nameplates, 1 test bars shown")
step("test bars hide after 8 seconds", lambda: H.update(9))


def exec_log():
    return [line for line in G.DoesItDieDB.log.values() if "EXEC" in line]


def exec_bar():
    return next((f for f in G.DoesItDieExecute.children.values() if f.kind == "StatusBar"), None)


def estimate():
    result = ns.execute.estimate()
    return result[0] if isinstance(result, tuple) else result


ex = ns.execute
check("Execute tooltip read: base and rage", list(ex.parseHit(
    "Attempt to finish off a wounded foe, causing 600 damage and converting each extra point of rage into 15 "
    "additional damage. Only usable on enemies that have 20% or less health.")), [600, 600, 15])
check("Hammer of Wrath tooltip read: range", list(ex.parseHit(
    "Hurls a hammer that strikes an enemy for 474 to 522 Holy damage. Only usable on enemies that have 20% or "
    "less health.")), [474, 522, 0])
check("German tooltip: first numbers, percent left out", list(ex.parseHit(
    "Nur bei Gegnern mit 20% Gesundheit oder weniger. Schleudert einen Hammer, der 474 bis 522 Heiligschaden "
    "verursacht.")), [474, 522, 0])
check("no number: nothing", ex.parseHit("Does something."), None)

G.targetGuid = "Creature-0-1-2-3-3099-000001"
step("/did exec as a mage: nothing to watch", lambda: G.SlashCmdList.DOESITDIE("exec"))
check("  says so", "No execute ability found" in chat_text().splitlines()[-1], True)
lua.execute("""
    playerClass = "PALADIN"
    function UnitClass() return "Paladin", playerClass end
    function IsPlayerSpell(id) return id == 24239 or id == 20662 end
    function GetSpellCritChance() return 10 end
    function GetCritChance() return 20 end
    rage = 40
    function UnitPower(unit, kind) if kind == 1 then return rage end return 0 end
    local spells = { [24239] = { "Hammer of Wrath", "Hurls a hammer that strikes an enemy for 474 to 522 Holy "
        .. "damage. Only usable on enemies that have 20% or less health." },
        [20662] = { "Execute", "Attempt to finish off a wounded foe, causing 600 damage and converting each extra "
        .. "point of rage into 15 additional damage. Only usable on enemies that have 20% or less health." } }
    local name, desc = C_Spell.GetSpellName, C_Spell.GetSpellDescription
    C_Spell.GetSpellName = function(id) return spells[id] and spells[id][1] or name(id) end
    C_Spell.GetSpellDescription = function(id) return spells[id] and spells[id][2] or desc(id) end
    C_Spell.GetSpellTexture = function(id) return 135000 + id end
    targetHealth = 1000
    function UnitHealth(unit) if unit == "target" or unit == "nameplate1" then return targetHealth end return 100 end
""")
step("spells loaded as a paladin", lambda: (H.fire("SPELLS_CHANGED"), H.update(0.2)))
check("  watching Hammer of Wrath", any("watching Hammer of Wrath (24239)" in l for l in exec_log()), True)
check("  estimate is the tooltip's low end", estimate(), 474)
check("  1000 health: bar not full", (exec_bar().max, exec_bar().value) if exec_bar() else None, (1000, 474))
G.targetHealth = 400
step("target at 400 health", lambda: H.update(0.2))
check("  bar full: the icon shows", (exec_bar().max, exec_bar().value), (400, 400))
check("  window shown", G.DoesItDieExecute.shown, True)


def plate_exec_icon():
    icons = list(ns.execute.plateIcons.values())
    return icons[0] if icons else None


check("  and on the mob's nameplate", plate_exec_icon().window.shown if plate_exec_icon() else None, True)
check("  its bar: the plate mob's health vs the hit", (plate_exec_icon().bar.max, plate_exec_icon().bar.value),
      (400, 400))
G.DoesItDieDB.execPlates = False
step("nameplate execute icon switched off", lambda: H.update(0.2))
check("  plate icon hidden", plate_exec_icon().window.shown, False)
check("  target's still shown", G.DoesItDieExecute.shown, True)
G.DoesItDieDB.execPlates = True
step("  back on", lambda: H.update(0.2))
check("  plate icon shown again", plate_exec_icon().window.shown, True)
lua.execute("C_Spell.IsSpellUsable = function() return false end")
step("the game says it can't be cast", lambda: H.update(0.2))
check("  hidden", G.DoesItDieExecute.shown, False)
lua.execute("C_Spell.IsSpellUsable = nil")


def hammer_fight(casts, meter_total):
    G.combat = True
    for i in range(casts):
        H.fire("UNIT_SPELLCAST_SENT", "player", "", "how-%d" % i, 24239)
        H.fire("UNIT_SPELLCAST_SUCCEEDED", "player", "how-%d" % i, 24239)
    G.combat = False
    return ex.learn(lua.table_from([lua.table_from({"spellID": 24239, "totalAmount": meter_total})]),
                    ex.takeTally())


# Two casts averaging 600 with 10% crits at 1.5x: 600 / 1.05 = 571.4 a hit, vs the tooltip's 498 average.
check("learned from the damage meter", hammer_fight(2, 1200), 1)
check("  ratio saved", G.DoesItDieDB.execRatios[24239].ratio, round(1200 / 1.05 / 996, 3))
check("  estimate scales the low end", round(estimate()), round(474 * round(1200 / 1.05 / 996, 3)))
check("a meter total far off the tooltip isn't learned", hammer_fight(1, 5000), 0)

lua.execute("""playerClass = "WARRIOR" """)
step("spells changed: now a warrior", lambda: (H.fire("SPELLS_CHANGED"), H.update(0.2)))
check("  Execute with 40 rage: 600 + 25 extra x 15", estimate(), 975)


def execute_fight(rage_readable):
    G.combat = True
    if not rage_readable:
        lua.execute("UnitPower = function() return nil end")
    H.fire("UNIT_SPELLCAST_SENT", "player", "", "ex-1", 20662)
    H.fire("UNIT_SPELLCAST_SUCCEEDED", "player", "ex-1", 20662)
    G.combat = False
    return ex.learn(lua.table_from([lua.table_from({"spellID": 20662, "totalAmount": 1100})]), ex.takeTally())


check("Execute without readable rage isn't learned", execute_fight(False), 0)
check("  and the estimate is the base 600", estimate(), 600)
check("  log says why", any("rage wasn't readable" in l for l in exec_log()), True)
lua.execute("function UnitPower(unit, kind) if kind == 1 then return rage end return 0 end")
# 40 rage at send: 600 + 375 = 975 expected; a 1100 hit with 20% crits at 2x is 1100 / 1.2 = 916.7 a hit.
check("Execute with readable rage learns", execute_fight(True), 1)
check("  ratio", G.DoesItDieDB.execRatios[20662].ratio, round(1100 / 1.2 / 975, 3))
step("/did exec prints the estimate and shows the icon", lambda: (G.SlashCmdList.DOESITDIE("exec"), H.update(0.2)))
check("  printed", "Execute: 600 + 25 rage x 15" in chat_text(), True)
check("  shown for the test", G.DoesItDieExecute.shown, True)
step("/did reset forgets it", lambda: G.SlashCmdList.DOESITDIE("reset"))
check("  gone", G.DoesItDieDB.execRatios[20662], None)
step("5 seconds later, back to the real check", lambda: H.update(5.2))
G.targetHealth = 100
G.DoesItDieDB.execShow = False
step("switched off", lambda: H.update(0.2))
check("  hidden", G.DoesItDieExecute.shown, False)
G.DoesItDieDB.execShow = True

# Finishers: Ferocious Bite's row for the current combo points, plus extra energy.
BITE = ("Finishing move that causes damage per combo point and converts each extra point of energy into 2.0 "
        "additional damage. Damage is increased by your Attack Power.\n1 point : 122-162 damage\n2 points: 214-254 "
        "damage\n3 points: 306-346 damage\n4 points: 398-438 damage\n5 points: 490-530 damage")
check("Ferocious Bite at 3 points", list(ex.parseHit(BITE, 3)), [306, 346, 2])
check("  at 7 points: the top row", list(ex.parseHit(BITE, 7)), [490, 530, 2])
check("  points unknown: the first row", list(ex.parseHit(BITE)), [122, 162, 2])
# Thousands separators in execute and finisher tooltips (English, German, Russian).
check("parseHit: English range with commas", list(ex.parseHit("Inflicts 1,100 to 1,240 Shadow damage.")), [1100, 1240, 0])
check("parseHit: English single hit with comma", list(ex.parseHit("Causing 1,050 damage and converting each extra point of rage into 15.5 additional damage.")), [1050, 1050, 15.5])
check("parseHit: finisher row with commas", list(ex.parseHit("1 point : 200-240 damage\n5 points: 1,020-1,140 damage", 5)), [1020, 1140, 0])
check("parseHit: German dots", list(ex.parseHit("Verursacht 1.050 bis 1.200 Schattenschaden.")), [1050, 1200, 0])
check("parseHit: Russian NBSP thousands", list(ex.parseHit("Наносит 1\u00a0050–1\u00a0150 ед. урона.")), [1050, 1150, 0])
lua.execute("""
    playerClass = "DRUID"
    function IsPlayerSpell(id) return id == 22828 end
    local name, desc = C_Spell.GetSpellName, C_Spell.GetSpellDescription
    C_Spell.GetSpellName = function(id) if id == 22828 then return "Ferocious Bite" end return name(id) end
    C_Spell.GetSpellDescription = function(id) if id == 22828 then return biteText end return desc(id) end
    energy, comboPoints = 65, 4
    function UnitPower(unit, kind) if kind == 3 then return energy end end
    function GetComboPoints() return comboPoints end
""")
G.biteText = BITE
step("now a druid", lambda: (H.fire("SPELLS_CHANGED"), H.update(0.2)))
check("  watching Ferocious Bite", any("watching Ferocious Bite (22828)" in l for l in exec_log()), True)
# Forever renumbers ranks: with only rank 1's Classic ID "known", the real top rank (another ID) is in the spellbook.
lua.execute("""
    function IsPlayerSpell(id) return id == 22568 or id == 99999 end
    local name, desc = C_Spell.GetSpellName, C_Spell.GetSpellDescription
    C_Spell.GetSpellName = function(id) if id == 22568 or id == 99999 then return "Ferocious Bite" end return name(id) end
    C_Spell.GetSpellDescription = function(id)
        if id == 22568 then return "Finishing move that causes damage per combo point. 1 point : 50-66 damage "
            .. "5 points: 186-202 damage" end
        if id == 99999 then return biteText end
        return desc(id)
    end
    C_SpellBook = { GetSpellBookItemInfo = function(index)
        local ids = { 1126, 22568, 99999 }
        if ids[index] then return { spellID = ids[index], name = C_Spell.GetSpellName(ids[index]) } end
    end }
""")
step("spellbook has Forever's rank 3 under a new ID", lambda: (H.fire("SPELLS_CHANGED"), H.update(0.2)))
check("  watches the strongest rank, not rank 1", any("watching Ferocious Bite (99999)" in l and "22568=186" in l
                                                       for l in exec_log()), True)
lua.execute("C_SpellBook = nil; function IsPlayerSpell(id) return id == 22828 end")
step("  back to the Classic ID", lambda: (H.fire("SPELLS_CHANGED"), H.update(0.2)))
check("  4 points, 40 extra energy: 398 + 80", estimate(), 478)
G.targetHealth = 400
step("finisher: the plate isn't the target's", lambda: H.update(0.2))
check("  no finisher icon on another mob's plate", plate_exec_icon().window.shown, False)
check("  but on the target frame", G.DoesItDieExecute.shown, True)
lua.execute("""
    local getPlate = C_NamePlate.GetNamePlateForUnit
    C_NamePlate.GetNamePlateForUnit = function(unit) return getPlate(unit == "target" and "nameplate1" or unit) end
""")
step("  the plate is the target's", lambda: H.update(0.2))
check("  finisher icon on it", plate_exec_icon().window.shown, True)
lua.execute("""
    local getPlate = C_NamePlate.GetNamePlateForUnit
    C_NamePlate.GetNamePlateForUnit = function(unit) if unit ~= "target" then return getPlate(unit) end end
""")
G.targetHealth = 1000
# Cache 4 combo points via UNIT_POWER_FREQUENT, then drop API reading to 0: API 0 must beat the stale cache.
H.fire("UNIT_POWER_FREQUENT", "player", "COMBO_POINTS")
G.comboPoints = 0
check("  API 0 beats stale cached combo points", list(ns.currentComboPoints()), [0, "read"])
check("  no combo points: no estimate", estimate(), None)
check("  and /did exec says it's the combo points, not the tooltip", "no combo points" in str(ns.execute.estimate()[1]), True)
G.biteText = "Finishing move."
G.comboPoints = 3
check("  unreadable tooltip: /did exec shows what came back", "\"Finishing move.\"" in str(ns.execute.estimate()[1]), True)
G.biteText = BITE
G.comboPoints = 0
# A finisher cast sent when API already reports 0 points must not learn against the 1-point row.
G.combat = True
H.fire("UNIT_SPELLCAST_SENT", "player", "", "fb-zero", 22828)
H.fire("UNIT_SPELLCAST_SUCCEEDED", "player", "fb-zero", 22828)
G.combat = False
check("  Bite sent at 0 read points isn't learned against 1-point row",
      ex.learn(lua.table_from([lua.table_from({"spellID": 22828, "totalAmount": 700})]), ex.takeTally()), 0)
lua.execute("GetComboPoints = function() return nil end")
# Stale cache still helps when API is unreadable (secret), and clears on target change.
H.fire("PLAYER_TARGET_CHANGED")
check("  points unreadable, none counted: 1 point's row", estimate(), 122 + 80)


def bite_fight(points_readable):
    G.combat = True
    if points_readable:
        lua.execute("GetComboPoints = function() return 5 end")
    H.fire("UNIT_SPELLCAST_SENT", "player", "", "fb-1", 22828)
    H.fire("UNIT_SPELLCAST_SUCCEEDED", "player", "fb-1", 22828)
    G.combat = False
    return ex.learn(lua.table_from([lua.table_from({"spellID": 22828, "totalAmount": 700})]), ex.takeTally())


check("Bite without readable combo points isn't learned", bite_fight(False), 0)
check("  log says why", any("combo points weren't readable" in l for l in exec_log()), True)
# 5 points read, 40 extra energy: 510 + 80 = 590 expected; 700 with 20% crits at 2x is 583.3 a hit.
check("Bite with readable points learns", bite_fight(True), 1)
check("  ratio", G.DoesItDieDB.execRatios[22828].ratio, round(700 / 1.2 / 590, 3))
# Options' "Reset learned tick sizes" (ns.resetLearnedTicks) clears execute ratios and active DoT snapshots too.
lua.execute("DoesItDieDB.ticks[172] = 25")
G.targetGuid = "Creature-0-1-2-3-3099-000099"
H.fire("PLAYER_TARGET_CHANGED")
H.fire("UNIT_SPELLCAST_SUCCEEDED", "player", "cast-reset", 172)
check("  untouched Corruption uses learned 25/tick (100 dmg)", ns.tracking.targetRemainingDamage()[0], 100)
step("/did reset drops active snapshot and execute ratios", lambda: G.SlashCmdList.DOESITDIE("reset"))
check("  active DoT falls back to description (40 dmg)", ns.tracking.targetRemainingDamage()[0], 40)
check("  execute ratio cleared", G.DoesItDieDB.execRatios[22828], None)
lua.execute("GetComboPoints = nil")

lua.execute("function UnitHealth() return 100 end; playerClass = 'MAGE'")
step("back to a mage", lambda: (H.fire("SPELLS_CHANGED"), H.update(0.2)))
check("  nothing watched, hidden", G.DoesItDieExecute.shown, False)
check("  no errors in the execute icon's update", any("EXEC error" in l for l in exec_log()), False)
G.targetGuid = None


def plate_children(kind):
    return [c for c in G.FakePlate.children.values() if c.kind == kind]


def dot_the_mob():
    G.targetGuid = "Creature-0-1-2-3-3099-000001"
    H.fire("UNIT_SPELLCAST_SUCCEEDED", "player", "cast-1", 172)
    H.update(0.2)


step("cast Corruption on the mob behind nameplate1", dot_the_mob)
markers = plate_children("StatusBar")
check("  nameplate got a marker", len(markers), 1)
check("  marker filled to Corruption's 40", markers[0].value if markers else None, 40)
check("  marker shown", markers[0].shown if markers else None, True)
# the clipped kill icon window (not the execute icon's, which the paladin and druid steps above left on the plate)
icon_windows = [f for f in plate_children("Frame") if f.clips
                and not any(same(f, p.window) for p in ns.execute.plateIcons.values())]
check("  kill icon window shown", icon_windows[0].shown if icon_windows else None, True)


def fire_and_update(event, *args):
    def run():
        H.fire(event, "player", *args)
        H.update(0.2)
    return run


step("start casting Immolate (cast time) on it", fire_and_update("UNIT_SPELLCAST_START", "cast-2", 348))
check("  nameplate marker counts it while casting: 40 + 20", markers[0].value if markers else None, 60)
step("the cast is interrupted", fire_and_update("UNIT_SPELLCAST_INTERRUPTED", "cast-2", 348))
check("  back to Corruption alone", markers[0].value if markers else None, 40)

# Public API (API.lua): what another addon sees for the same mob.
check("API: version", G.DoesItDie.API_VERSION, 1)
check("API: remaining damage on the target", list(lua.eval("{DoesItDie.GetRemainingDamage('target')}").values()),
      [40, 1])
check("API: same mob through its nameplate", list(lua.eval("{DoesItDie.GetRemainingDamage('nameplate1')}").values()),
      [40, 1])
check("API: nothing on a missing unit", list(lua.eval("{DoesItDie.GetRemainingDamage('focus')}").values()), [0, 0])
check("API: nil unit doesn't error", list(lua.eval("{DoesItDie.GetRemainingDamage(nil)}").values()), [0, 0])
api_dots = G.DoesItDie.GetDoTs("target")
check("API: the DoT list", [(d.name, d.spellID, d.school, d.damage, d.provisional) for d in api_dots.values()],
      [("Corruption", 172, 32, 40, False)])
check("API: the list has its expiry", api_dots[1].expiresAt > api_dots[1].appliedAt if len(api_dots) else None, True)
lua.execute("""
    apiEvents = {}
    DoesItDie.RegisterCallback("TestAddon", function(event, unit) table.insert(apiEvents, event .. " " .. unit) end)
    DoesItDie.RegisterCallback("Broken", function() error("consumer bug") end)
""")
step("API: register callbacks, run the display loop", lambda: H.update(0.2))
check("  first run reports what's there", sorted(G.apiEvents.values()),
      ["DOTS_CHANGED nameplate1", "DOTS_CHANGED target"])
check("  a consumer's error is logged, not raised",
      any("API callback error (Broken)" in line for line in G.DoesItDieDB.log.values()), True)
step("API: nothing changed", lambda: (lua.execute("apiEvents = {}"), H.update(0.2)))
check("  no events", len(G.apiEvents), 0)
step("API: start casting Immolate", fire_and_update("UNIT_SPELLCAST_START", "cast-2", 348))
check("  both units report the change", sorted(G.apiEvents.values()),
      ["DOTS_CHANGED nameplate1", "DOTS_CHANGED target"])
check("  the cast shows as provisional", [(d.name, d.provisional) for d in G.DoesItDie.GetDoTs("target").values()],
      [("Corruption", False), ("Immolate", True)])
step("API: the cast is interrupted", fire_and_update("UNIT_SPELLCAST_INTERRUPTED", "cast-2", 348))
check("  back to 40", list(lua.eval("{DoesItDie.GetRemainingDamage('target')}").values()), [40, 1])
lua.execute('DoesItDie.UnregisterCallback("TestAddon"); DoesItDie.UnregisterCallback("Broken"); apiEvents = {}')
step("API: unregistered", fire_and_update("UNIT_SPELLCAST_START", "cast-2", 348))
check("  no more events", len(G.apiEvents), 0)
step("API: interrupt again", fire_and_update("UNIT_SPELLCAST_INTERRUPTED", "cast-2", 348))


def set_estimate(on):
    def run():
        H.clickText("Advanced")
        box = H.rowWidget("Estimate during casting", "CheckButton")
        box.checked = on
        box.scripts.OnClick(box)
    return run


step("untick Estimate during casting", set_estimate(False))
check("  setting off", G.DoesItDieDB.estimateDuringCast, False)
step("start casting Immolate with it off", fire_and_update("UNIT_SPELLCAST_START", "cast-3", 348))
check("  nothing added while casting", markers[0].value if markers else None, 40)
step("  and interrupted", fire_and_update("UNIT_SPELLCAST_INTERRUPTED", "cast-3", 348))
step("tick it again", set_estimate(True))
check("  setting on", G.DoesItDieDB.estimateDuringCast, True)
step("cast Immolate again", fire_and_update("UNIT_SPELLCAST_START", "cast-4", 348))
step("  it lands (SUCCEEDED, then STOP)", lambda: (H.fire("UNIT_SPELLCAST_SUCCEEDED", "player", "cast-4", 348),
                                                   H.fire("UNIT_SPELLCAST_STOP", "player", "cast-4", 348),
                                                   H.update(1.0)))
check("  counted once: 40 + 20", markers[0].value if markers else None, 60)


def plates_off():
    G.DoesItDieDB.nameplateMode = "off"
    H.update(0.2)


step("switch nameplates off", plates_off)
check("  marker hidden", markers[0].shown if markers else None, False)
check("  kill icon hidden", icon_windows[0].shown if icon_windows else None, False)


# Custom target frame (Advanced tab), as for a unit frame addon that replaces Blizzard's target frame.
lua.execute("""
    local custom = CreateFrame("Frame", "MyTargetFrame", UIParent)
    custom.Health = CreateFrame("StatusBar", nil, custom)
""")
custom_bar = G.MyTargetFrame.Health
check("frame path of an unnamed child found by its key", ns.framePath(custom_bar), "MyTargetFrame.Health")
check("  and resolves back to it", same(ns.resolveFramePath("MyTargetFrame.Health"), custom_bar), True)
check("  a missing path resolves to nothing", ns.resolveFramePath("NoSuchFrame.Health"), None)


def type_frame_path(label, text):
    def run():
        box = H.rowWidget(label, "EditBox")
        box.SetText(box, text)
        box.scripts.OnEditFocusLost(box)
    return run


step("type a custom health bar path", type_frame_path("Target health bar", "MyTargetFrame.Health"))
check("  saved", G.DoesItDieDB.customHealthBar, "MyTargetFrame.Health")
step("display loop on the custom frame", lambda: H.update(0.2))
check("  marker laid over the custom health bar", same(G.DoesItDieRemaining.allPoints, custom_bar), True)
check("  status shows it in use", "MyTargetFrame.Health" in ns.attachStatus()[0], True)
check("  marker still showing Corruption", G.DoesItDieRemaining.shown, True)


def hide_custom_frame():
    G.MyTargetFrame.Hide(G.MyTargetFrame)
    H.update(0.2)


step("custom target frame hidden", hide_custom_frame)
check("  marker hidden with it", G.DoesItDieRemaining.shown, False)
G.MyTargetFrame.Show(G.MyTargetFrame)
step("type a path that doesn't exist", type_frame_path("Target health bar", "Gone.Health"))
check("  status says not found", "not found" in ns.attachStatus()[0], True)
step("clear it", type_frame_path("Target health bar", ""))
check("  back to Blizzard's", ns.attachStatus()[0], "Blizzard's target frame")
step("Pick button starts pick mode", lambda: H.clickText("Pick"))
step("  a right-click cancels it", lambda: H.fire("GLOBAL_MOUSE_DOWN", "RightButton"))

# In-game, IsMouseOver on Blizzard's target frame textures returned a secret boolean and every pick update errored
# (Frames.lua:96, 57 times). Secret values here are a sentinel that issecretvalue recognizes.
lua.execute("""
    SECRET = setmetatable({}, { __tostring = function() return "<secret>" end })
    function issecretvalue(v) return v == SECRET end
    local frame, bar = MyTargetFrame, MyTargetFrame.Health
    function frame:GetChildren() return bar end
    function frame:GetRect() return 0, 0, 200, 40 end
    function frame:IsMouseOver() return SECRET end
    function bar:GetObjectType() return "StatusBar" end
    function bar:GetRect() return 10, 10, 150, 12 end
    function bar:IsMouseOver() return SECRET end
    function bar:GetEffectiveScale() return 1 end
    function frame:GetEffectiveScale() return 1 end
    function GetCursorPosition() return 50, 15 end
    function GetMouseFoci() return { frame } end
""")


def pick_with_secret_mouseover():
    H.clickText("Pick")  # the health bar row's
    H.update(0.1)
    H.fire("GLOBAL_MOUSE_DOWN", "LeftButton")


step("Pick over a bar whose IsMouseOver is secret: no error", pick_with_secret_mouseover)
check("  falls back to the rectangle and picks the bar", G.DoesItDieDB.customHealthBar, "MyTargetFrame.Health")
check("  no pick error logged", any("ERROR in frame pick" in l for l in G.DoesItDieDB.log.values()), False)
lua.execute("issecretvalue = nil")

# EllesmereUI's nameplates: it parks Blizzard's health bar on a hidden frame and shows its own plate frame (pooled,
# parented to the Blizzard plate while in use, listed by unit in EllesmereNameplates_NS.plates, bar at .health).
lua.execute("""
    local parking = CreateFrame("Frame")
    parking:Hide()
    FakePlate.UnitFrame.healthBar.parent = parking
    local eui = CreateFrame("Frame", nil, FakePlate)
    eui.health = CreateFrame("StatusBar", nil, eui)
    eui.health:SetFrameStrata("MEDIUM")
    eui.nameplate, eui.unit = FakePlate, "nameplate1"
    FakeEllesmerePlate = eui
    EllesmereNameplates_NS = { plates = { nameplate1 = eui } }
""")
eui = G.FakeEllesmerePlate


def plates_on_with_ellesmere():
    G.DoesItDieDB.nameplateMode = "markerIcon"
    H.fire("UNIT_SPELLCAST_SUCCEEDED", "player", "cast-2", 172)
    H.update(0.2)


step("EllesmereUI's plate on nameplate1, Corruption recast", plates_on_with_ellesmere)
eui_markers = [c for c in eui.children.values() if c.kind == "StatusBar" and same(c.allPoints, eui.health)]
check("  marker laid over EllesmereUI's health bar", len(eui_markers), 1)
check("  filled to Corruption's 40 + the Immolate cast earlier", eui_markers[0].value if eui_markers else None, 60)
check("  shown", eui_markers[0].shown if eui_markers else None, True)
check("  in the bar's strata", eui_markers[0].strata if eui_markers else None, "MEDIUM")
check("  nothing drawn on Blizzard's parked bar", markers[0].shown if markers else None, False)

step("EllesmereUI releases its plate to the pool", lambda: eui.Hide(eui))
check("  marker hidden at once", eui_markers[0].shown if eui_markers else None, False)
step("  the plate comes back for another mob", lambda: eui.Show(eui))
check("  no stale marker before the next update", eui_markers[0].shown if eui_markers else None, False)
step("  next update", lambda: H.update(0.2))
check("  marker back for this mob's DoTs", eui_markers[0].shown if eui_markers else None, True)

lua.execute("function UnitIsDead(unit) return unit == 'nameplate1' end")
step("the mob dies with Corruption still on it (its plate lingers)", lambda: H.update(0.2))
check("  no marker on the corpse", eui_markers[0].shown if eui_markers else None, False)
lua.execute("function UnitIsDead() return false end")
step("  (alive again for the next checks)", lambda: H.update(0.2))

step("/did plates with EllesmereUI's plate", lambda: G.SlashCmdList.DOESITDIE("plates"))
plate_lines = [line for line in G.DoesItDieDB.log.values() if "PLATES" in line]
check("  probe reports its health bar", any("healthBar=EllesmereUI plate.health" in line and "barShown=true" in line
                                            and "barStrata=MEDIUM" in line for line in plate_lines), True)

lua.execute("""
    EllesmereNameplates_NS = nil
    FakePlate.UnitFrame.healthBar.parent = FakePlate.UnitFrame
""")
step("without EllesmereUI's plates", lambda: H.update(0.2))
check("  marker back on Blizzard's bar", markers[0].shown if markers else None, True)
check("  EllesmereUI plate's marker hidden", eui_markers[0].shown if eui_markers else None, False)

# EllesmereUI's unit frames: its target frame is used without a setting. The frame only exists while EllesmereUI
# draws the target frame itself.
lua.execute("""
    local frame = CreateFrame("Frame", "EllesmereUIUnitFrames_Target", UIParent)
    frame.Health = CreateFrame("StatusBar", nil, frame)
    -- The portrait sits on a backdrop, which EllesmereUI hides when portraits are off.
    local backdrop = CreateFrame("Frame", nil, frame)
    frame.Portrait = backdrop:CreateTexture()
    frame.Portrait.name = "EllesmereUIPortrait"
""")
eui_target_bar = G.EllesmereUIUnitFrames_Target.Health


def last_attach():
    return [line for line in G.DoesItDieDB.log.values() if "ATTACH" in line][-1]



def type_and_update(text):
    def run():
        type_frame_path("Target health bar", text)()
        H.update(0.2)
    return run


step("EllesmereUI's target frame appears", lambda: (H.fire("PLAYER_TARGET_CHANGED"), H.update(0.2)))
check("  a typed path still wins", same(G.DoesItDieRemaining.allPoints, custom_bar), True)
step("clear the path", type_and_update(""))
check("  marker laid over EllesmereUI's health bar", same(G.DoesItDieRemaining.allPoints, eui_target_bar), True)
check("  status names it", ns.attachStatus()[0], "EllesmereUI's target frame")
check("  kill icon on its portrait", ns.attachStatus()[1], "EllesmereUI's portrait")
check("    and attached there", "ATTACH portrait: EllesmereUIPortrait" in last_attach(), True)


def portraits_off():
    lua.execute("EllesmereUIUnitFrames_Target.Portrait:GetParent():Hide()")
    H.fire("PLAYER_TARGET_CHANGED")
    H.update(0.2)


step("EllesmereUI's portraits turned off", portraits_off)
check("  kill icon on its health bar", ns.attachStatus()[1], "the health bar")
check("    and attached there", "ATTACH portrait: not found" in last_attach(), True)
step("type a path that doesn't exist", type_and_update("Gone.Health"))
check("  falls back to EllesmereUI's, not Blizzard's", same(G.DoesItDieRemaining.allPoints, eui_target_bar), True)
check("  status says so", "using EllesmereUI's target frame" in ns.attachStatus()[0], True)
lua.execute("EllesmereUIUnitFrames_Target = nil")
step("clear it, with EllesmereUI's target frame off", type_and_update(""))
check("  back to Blizzard's", ns.attachStatus()[0], "Blizzard's target frame")

# BetterBlizzFrames: bigger health bars are its own bar drawn over Blizzard's, which goes invisible at its old size.
lua.execute("""
    TargetFrame = CreateFrame("Frame", "TargetFrame", UIParent)
    TargetFrame.TargetFrameContainer = CreateFrame("Frame", nil, TargetFrame)
    TargetFrame.TargetFrameContainer.Portrait = TargetFrame.TargetFrameContainer:CreateTexture()
    TargetFrame.TargetFrameContent = CreateFrame("Frame", nil, TargetFrame)
    TargetFrame.TargetFrameContent.TargetFrameContentMain = CreateFrame("Frame", nil, TargetFrame.TargetFrameContent)
    local main = TargetFrame.TargetFrameContent.TargetFrameContentMain
    main.HealthBarsContainer = CreateFrame("Frame", nil, main)
    TargetFrameHealthBar = CreateFrame("StatusBar", nil, main.HealthBarsContainer)
    main.HealthBarsContainer.HealthBar = TargetFrameHealthBar
    BBFMirrorBar = CreateFrame("StatusBar", nil, TargetFrame)
    BBFMirrorOn = false
    BBF = { HealthBar = function(frame)
        if frame == TargetFrame then return BBFMirrorOn and BBFMirrorBar or TargetFrameHealthBar end
    end }
""")
step("BetterBlizzFrames with normal bars", lambda: (H.fire("PLAYER_TARGET_CHANGED"), H.update(0.2)))
check("  marker on Blizzard's bar", same(G.DoesItDieRemaining.allPoints, G.TargetFrameHealthBar), True)
lua.execute("BBFMirrorOn = true")
step("its bigger bars turned on (no target change)", lambda: H.update(1.2))
check("  marker moves to its bar", same(G.DoesItDieRemaining.allPoints, G.BBFMirrorBar), True)
lua.execute("BBF.HealthBar = function() error('broken') end")
step("a BBF that throws", lambda: H.update(1.2))
check("  falls back to Blizzard's bar", same(G.DoesItDieRemaining.allPoints, G.TargetFrameHealthBar), True)
# Issue #36: the layering walk over the target frame's tree ran every second even with nothing to show, over
# however many frames other addons had hung there. Now it only runs while the marker shows, and stops at 300.
lua.execute("""
    layerVisits = 0
    local function leaf()
        return { GetFrameStrata = function() layerVisits = layerVisits + 1; return "LOW" end,
                 GetFrameLevel = function() return 1 end, GetChildren = function() end }
    end
    local crowd = {}
    for i = 1, 50 do
        local kids = {}
        for j = 1, 50 do kids[j] = leaf() end
        local node = leaf()
        node.GetChildren = function() return unpack(kids) end
        crowd[i] = node
    end
    TargetFrame.GetChildren = function() return unpack(crowd) end
""")


def no_target_for_a_while():
    G.targetGuid = None
    H.fire("PLAYER_TARGET_CHANGED")
    H.update(1.2)
    H.update(1.2)


step("2,500 frames under the target frame, no target", no_target_for_a_while)
check("  no layering walk while nothing shows", G.layerVisits, 0)


def dot_with_crowded_frame():
    G.targetGuid = "Creature-0-1-2-3-3099-000001"
    H.fire("PLAYER_TARGET_CHANGED")
    H.fire("UNIT_SPELLCAST_SUCCEEDED", "player", "cast-L1", 172)
    H.update(1.2)


step("Corruption on a target with that frame", dot_with_crowded_frame)
check("  walked", G.layerVisits > 0, True)
step("one more layer check", lambda: (lua.execute("layerVisits = 0"), H.update(1.2)))
check("  stopped at 300 frames", 0 < G.layerVisits <= 300, True)
check("  logged once as slow",
      sum("SLOW layer check" in line for line in G.DoesItDieDB.log.values()), 1)
G.targetGuid = None
lua.execute("BBF, TargetFrame, TargetFrameHealthBar, BBFMirrorBar, BBFMirrorOn = nil, nil, nil, nil, nil")
step("no BetterBlizzFrames, no target frame again", lambda: (H.fire("PLAYER_TARGET_CHANGED"), H.update(1.2)))


# Learned tick sizes viewer (Advanced > View, /did ticks).
def learn_some_ticks():
    ticks = ns.db.ticks
    lua.execute("wipe(DoesItDieDB.ticks)")
    ticks[172] = 12       # Corruption: tooltip 40 over 12s = 10 per tick
    ticks[348] = 4.4      # Immolate: tooltip 20 over 15s = 4 per tick
    ticks["1079x3"] = 22  # a 3-point finisher the client has no description for here


step("learn three tick sizes", learn_some_ticks)
step("/did ticks opens the viewer", lambda: G.SlashCmdList.DOESITDIE("ticks"))
viewer = G.DoesItDieLearnedTicks
check("  shown", viewer.shown if viewer else None, True)
rows = viewer.rows


def cells(i):
    row = rows[i]
    return [row.name.text, row.cells.combo.text, row.cells.learned.text, row.cells.tooltip.text,
            row.cells.bonus.text, row.cells.total.text]


check("  Corruption: 12 learned, tooltip 10, +20%, 48 in all", cells(1), ["Corruption", "", "12", "10", "+20%", "48"])
check("  Immolate: decimals kept", cells(2), ["Immolate", "", "4.4", "4", "+10%", "22"])
check("  finisher: its combo points, no tooltip numbers", cells(3), ["Spell", 3, "22", "-", "-", "-"])
check("  no fourth row", rows[4].shown, False)
def viewer_count():
    for child in viewer.children.values():
        if child.kind == "fontstring" and "learned tick size" in str(child.text or ""):
            return child.text


check("  count", viewer_count(), "3 learned tick sizes")
step("hover a row (spell tooltip plus learned numbers)", lambda: rows[1].scripts.OnEnter(rows[1]))
lua.execute('linked = nil; function IsShiftKeyDown() return true end; '
            'function ChatEdit_InsertLink(l) linked = l; return true end; '
            'C_Spell.GetSpellLink = function(id) return "[link " .. id .. "]" end')
step("shift-click Corruption", lambda: rows[1].scripts.OnClick(rows[1]))
check("  linked in chat", G.linked, "[link 172]")


def forget_first_row():
    for child in rows[1].children.values():
        if child.kind == "Button":
            child.scripts.OnClick(child)
            return
    raise AssertionError("no forget button")


step("forget Corruption's tick size", forget_first_row)
check("  gone from the saved data", ns.db.ticks[172], None)
check("  Immolate moves up", rows[1].name.text, "Immolate")
step("Forget all", lambda: H.clickText("Forget all"))
check("  saved data empty", len(list(ns.db.ticks.keys())), 0)
check("  no rows", rows[1].shown, False)
step("/did ticks again closes it", lambda: G.SlashCmdList.DOESITDIE("ticks"))
check("  hidden", viewer.shown, False)
step("Advanced tab's View button opens it", lambda: H.clickText("View"))
check("  shown", viewer.shown, True)


# Focus frame (Focus.lua): a focus mob ("FocusMob") with Blizzard's focus frame, a [@focus] Corruption on it.
lua.execute("""
    focusGuid = "Creature-0-1-2-3-3099-0000F0"
    local unitExists, unitGUID = UnitExists, UnitGUID
    function UnitExists(unit) if unit == "focus" then return focusGuid ~= nil end return unitExists(unit) end
    function UnitGUID(unit) if unit == "focus" then return focusGuid end return unitGUID(unit) end
    function UnitName(unit) if unit == "focus" and focusGuid then return "FocusMob" end end
    local focus = CreateFrame("Frame", "FocusFrame", UIParent)
    focus.TargetFrameContent = CreateFrame("Frame", nil, focus)
    focus.TargetFrameContent.TargetFrameContentMain = CreateFrame("Frame", nil, focus.TargetFrameContent)
    local main = focus.TargetFrameContent.TargetFrameContentMain
    main.HealthBarsContainer = CreateFrame("Frame", nil, main)
    main.HealthBarsContainer.HealthBar = CreateFrame("StatusBar", nil, main.HealthBarsContainer)
    BlizzardFocusBar = main.HealthBarsContainer.HealthBar
    -- Like Blizzard's: art layered far above the health bar (the target frame's top was MEDIUM/1001 in game).
    focus:SetFrameStrata("MEDIUM")
    focus:SetFrameLevel(1001)
""")


def markers_on(bar):
    return [f for f in G.frames.values() if f.kind == "StatusBar" and f.allPoints is not None and same(f.allPoints, bar)]


def focus_cast():
    H.fire("UNIT_SPELLCAST_SENT", "player", "FocusMob", "cast-f1", 172)
    H.fire("UNIT_SPELLCAST_SUCCEEDED", "player", "cast-f1", 172)
    H.update(0.2)


G.DoesItDieDB.nameplateMode = "markerIcon"
step("[@focus] Corruption on the focus", focus_cast)
focus_markers = markers_on(G.BlizzardFocusBar)
check("  marker on Blizzard's focus health bar", len(focus_markers), 1)
check("  filled to Corruption's 40", focus_markers[0].value if focus_markers else None, 40)
check("  shown", focus_markers[0].shown if focus_markers else None, True)
check("  status names it", ns.focusStatus(), "Blizzard's focus frame")
check("  layered above the focus frame's top (MEDIUM/1001)",
      (focus_markers[0].strata, focus_markers[0].level) if focus_markers else None, ("MEDIUM", 1006))
step("another update (the nameplate refresh must leave it alone)", lambda: H.update(0.2))
check("  still shown", focus_markers[0].shown if focus_markers else None, True)
step("  and with the updates in the other order", lambda: H.updateReversed(0.2))
check("  still shown", focus_markers[0].shown if focus_markers else None, True)
lua.execute("focusGuid = nil")
step("focus cleared", lambda: H.update(0.2))
check("  hidden", focus_markers[0].shown if focus_markers else None, False)
lua.execute('focusGuid = "Creature-0-1-2-3-3099-0000F0"')
G.DoesItDieDB.focusMode = "off"
step("focus back, Show on focus frame off", lambda: H.update(0.2))
check("  hidden", focus_markers[0].shown if focus_markers else None, False)
G.DoesItDieDB.focusMode = "markerIcon"
lua.execute("""
    BBFFocusBar = CreateFrame("StatusBar", nil, FocusFrame)
    BBF = { HealthBar = function(frame) if frame == FocusFrame then return BBFFocusBar end end }
""")
step("BetterBlizzFrames' bigger focus bar", lambda: H.update(0.2))
bbf_focus = markers_on(G.BBFFocusBar)
check("  marker on its bar", len(bbf_focus), 1)
check("    and shown", bbf_focus[0].shown if bbf_focus else None, True)
lua.execute("BBF, BBFFocusBar = nil, nil")
step("without it", lambda: H.update(0.2))
check("  back on Blizzard's focus bar", focus_markers[0].shown if focus_markers else None, True)
lua.execute("""
    local eui = CreateFrame("Frame", "EllesmereUIUnitFrames_Focus", UIParent)
    eui.Health = CreateFrame("StatusBar", nil, eui)
""")
step("EllesmereUI's focus frame appears", lambda: H.update(0.2))
eui_focus = markers_on(G.EllesmereUIUnitFrames_Focus.Health)
check("  marker moves to its health bar", len(eui_focus), 1)
check("  status names it", ns.focusStatus(), "EllesmereUI's focus frame")
check("  Advanced tab has the focus rows", all(H.rowWidget(label, kind) is not None for label, kind in
      (("Show on focus frame", "Button"), ("Focus health bar", "EditBox"))), True)


# Instances (PR #8): creature GUIDs are secret; the target's nameplate token stands in for its GUID.
lua.execute("""
    savedUnitGUID, savedGetPlate = UnitGUID, C_NamePlate.GetNamePlateForUnit
    function issecretvalue(v) return v == SECRET end
    FakePlate.namePlateUnitToken = "nameplate1"
    plateUp = true
    function UnitGUID(unit) if unit == "target" or unit == "nameplate1" then return SECRET end end
    C_NamePlate.GetNamePlateForUnit = function(unit)
        if plateUp and (unit == "nameplate1" or unit == "target") then return FakePlate end
    end
    targetGuid = SECRET
""")


def dungeon_cast(guid):
    def run():
        H.fire("PLAYER_TARGET_CHANGED")
        H.fire("UNIT_SPELLCAST_SENT", "player", "", guid, 172)
        H.fire("UNIT_SPELLCAST_SUCCEEDED", "player", guid, 172)
        H.update(0.2)
    return run


def dot_total(unit):
    return ns.dotBreakdownForUnit(unit)[1]


step("in a dungeon: Corruption on the target (secret GUID, nameplate up)", dungeon_cast("cast-d1"))
check("  tracked on the target", dot_total("target"), 40)
check("  and on its nameplate: the same mob", dot_total("nameplate1"), 40)
check("  logged why", any("tracking each mob by its nameplate" in l for l in G.DoesItDieDB.log.values()), True)
step("its nameplate goes away", lambda: (H.fire("NAME_PLATE_UNIT_REMOVED", "nameplate1"), H.update(0.2)))
check("  its DoTs are dropped (the token will be another mob's)", dot_total("nameplate1"), 0)
check("  logged", any("PLATE nameplate1 removed" in l for l in G.DoesItDieDB.log.values()), True)
lua.execute("plateUp = false")
step("no nameplate at all: Corruption on the target", dungeon_cast("cast-d2"))
check("  tracked on the target only (the old fallback)", dot_total("target"), 40)
lua.execute("""
    UnitGUID, C_NamePlate.GetNamePlateForUnit = savedUnitGUID, savedGetPlate
    targetGuid = nil
    issecretvalue = nil
""")


# Other nameplate addons (Plater, ...): Blizzard's plate bar hidden, the addon's own frame on the plate with its bar
# under a "health" key, found by the automatic search; then the Advanced tab's path for one it would miss.
lua.execute("""
    EllesmereNameplates_NS, Platynator = nil, nil
    targetGuid = "Creature-0-1-2-3-3099-0000A1"
    FakePlate.UnitFrame:Hide()
    FakePlate.unitFrame = CreateFrame("Frame", nil, FakePlate)
    FakePlate.unitFrame.PlateFrame = FakePlate -- (a back-reference, as Plater keeps)
    FakePlate.unitFrame.healthBar = CreateFrame("StatusBar", nil, FakePlate.unitFrame)
    PlaterBar = FakePlate.unitFrame.healthBar
    -- A reference to a frame outside the plate, with its own health bar, under a key that's searched first.
    local outside = CreateFrame("Frame", nil, UIParent)
    outside.healthBar = CreateFrame("StatusBar", nil, outside)
    FakePlate.aaaElsewhere = outside
""")


def plate_cast():
    H.fire("PLAYER_TARGET_CHANGED")
    H.fire("UNIT_SPELLCAST_SENT", "player", "", "cast-p1", 172)
    H.fire("UNIT_SPELLCAST_SUCCEEDED", "player", "cast-p1", 172)
    H.update(0.2)


G.DoesItDieDB.nameplateMode = "markerIcon"
step("Plater-like plate: Corruption on its mob", plate_cast)
plater_markers = markers_on(G.PlaterBar)
check("  marker found Plater's bar on its own", len(plater_markers), 1)
check("  filled to Corruption's 40", plater_markers[0].value if plater_markers else None, 40)
check("  shown", plater_markers[0].shown if plater_markers else None, True)
check("  status says where", ns.plateBarStatus(), "found: unitFrame.healthBar")
step("/did plates with it", lambda: G.SlashCmdList.DOESITDIE("plates"))
check("  probe names the bar", any("healthBar=auto unitFrame.healthBar" in l
                                   for l in G.DoesItDieDB.log.values()), True)
lua.execute("""
    FakePlate.mine = CreateFrame("Frame", nil, FakePlate)
    FakePlate.mine.bar = CreateFrame("StatusBar", nil, FakePlate.mine)
    MineBar = FakePlate.mine.bar
""")
G.DoesItDieDB.customPlateHealthBar = "mine.bar"
step("Advanced: Nameplate health bar = mine.bar", lambda: H.update(0.2))
mine_markers = markers_on(G.MineBar)
check("  marker on that bar", len(mine_markers), 1)
check("  status shows the path", "mine.bar" in ns.plateBarStatus(), True)
G.DoesItDieDB.customPlateHealthBar = "nothing.here"
step("  a path that doesn't exist: back to the automatic search", lambda: H.update(0.2))
check("  on Plater's bar again", ns.plateBarStatus(), "found: unitFrame.healthBar")
G.DoesItDieDB.customPlateHealthBar = ""

# A field that errors when read (frameworks' objects with a throwing __index), searched before Plater's frame: it
# used to abort the whole search, so Plater's bar was never found (CurseForge, tuwzz).
lua.execute("""
    FakePlate.aaaBomb = setmetatable({}, { __index = function() error("framework object: no such key") end })
""")


def fresh_search():
    # a different plate frame each time would be cleaner; waiting out the per-plate cache does the same
    H.update(1.5)


def search_again():
    # The cache keeps a shown bar: hide it for one update so the next search really runs.
    lua.execute("PlaterBar:Hide()")
    H.update(0.2)
    lua.execute("PlaterBar:Show()")
    H.update(1.5)


step("a field that errors when read sits before Plater's frame", search_again)
check("  Plater's bar still found and drawn on", any(m.shown for m in markers_on(G.PlaterBar)), True)


def isolated_search():
    # The real searchHealthBar on its own, on a plate with a throwing field sorted before a Plater-like frame.
    # (The fake environment above doesn't reproduce the abort; v0.8.1's search fails this, the current one passes.)
    import re
    source = open(os.path.join(ADDON, "Nameplates.lua"), encoding="utf-8").read()
    code = source[source.index("local function isStatusBar"):source.index("local function autoHealthBar")]
    code = re.sub(r"^local SEARCH_(DEPTH|INTERVAL) = \d+\n", "", code, flags=re.M)
    return LuaRuntime().execute("""
        local function isSecret() return false end
        local SEARCH_DEPTH, SEARCH_INTERVAL = 4, 1
        local function frame(kind, parent)
            local f = { kind = kind, parent = parent, shown = true }
            function f.GetObjectType(self) return self.kind end
            function f.GetParent(self) return self.parent end
            function f.IsVisible(self) return self.shown end
            function f.GetEffectiveAlpha() return 1 end
            function f.IsForbidden() return false end
            return f
        end
        local function barShown(bar) return bar:IsVisible() end
    """ + code + """
        local plate = frame("Frame", nil)
        plate.UnitFrame = frame("Frame", plate)
        plate.aaaBomb = setmetatable({}, { __index = function() error("framework object: no such key") end })
        plate.unitFrame = frame("Frame", plate)
        plate.unitFrame.healthBar = frame("StatusBar", plate.unitFrame)
        local ok, _, path = pcall(searchHealthBar, plate)
        return ok and path or "search aborted"
    """)


check("  the search itself, run in isolation, gets past the throwing field", isolated_search(), "unitFrame.healthBar")

# A bar kept in a plain table: mine.visual.healthbar.
lua.execute("""
    PlaterBar:Hide(); FakePlate.unitFrame = nil
    FakePlate.mine = CreateFrame("Frame", nil, FakePlate)
    FakePlate.mine.visual = {}
    FakePlate.mine.visual.healthbar = CreateFrame("StatusBar", nil, FakePlate.mine)
    TableBar = FakePlate.mine.visual.healthbar
""")
step("a bar in a plain table", fresh_search)
check("  found through the plain table", ns.plateBarStatus(), "found: mine.visual.healthbar")
check("  marker on it", len(markers_on(G.TableBar)), 1)

# Threat Plates, as its source builds it: the plate frame hangs off WorldFrame (not the plate), referenced as
# plate.TPFrame, active while drawing the unit, bar at .visual.Healthbar. The search can't reach it.
lua.execute("""
    TableBar:Hide(); FakePlate.mine = nil
    FakePlate.TPFrame = CreateFrame("Frame", "ThreatPlatesFrameNamePlate1", nil)
    FakePlate.TPFrame.Parent, FakePlate.TPFrame.Active = FakePlate, true
    FakePlate.TPFrame.visual = {}
    FakePlate.TPFrame.visual.Healthbar = CreateFrame("StatusBar", nil, FakePlate.TPFrame)
    ThreatBar = FakePlate.TPFrame.visual.Healthbar
""")
step("Threat Plates plate (Corruption recast: the steps above outlast it)", lambda: (plate_cast(), fresh_search()))
check("  its bar found", ns.plateBarStatus(), "Threat Plates TPFrame.visual.Healthbar")
check("  marker on it", len(markers_on(G.ThreatBar)), 1)
lua.execute("FakePlate.TPFrame.Active = false")
step("Threat Plates not drawing this unit", fresh_search)
check("  its bar not used", ns.plateBarStatus() == "Threat Plates TPFrame.visual.Healthbar", False)

# Nothing readable and Blizzard's bar hidden: the kill icon alone, beside the plate (as before v0.7.0).
lua.execute("ThreatBar:Hide(); FakePlate.TPFrame, FakePlate.aaaBomb = nil, nil")
step("a plate addon we can't read", fresh_search)
check("  status says so", "kill icon only" in ns.plateBarStatus(), True)
blizzard_markers = markers_on(G.FakePlate.UnitFrame.healthBar)
check("  no marker over the hidden bar", any(m.shown for m in blizzard_markers), False)
icon_windows = [c for c in G.FakePlate.children.values() if c.kind == "Frame" and c.clips]
check("  but the kill icon shows", any(w.shown for w in icon_windows), True)

lua.execute("""
    FakePlate.UnitFrame:Show()
    FakePlate.unitFrame, FakePlate.mine, FakePlate.TPFrame, FakePlate.aaaBomb = nil, nil, nil, nil
    targetGuid = nil
""")


# ElvUI parents unit frames under a shared hider and ElvUIParent, alongside the rest of the UI.
# A layer scan must stay inside the target unit frame, even when no target/DoTs are active.
lua.execute("""
    layerVisits = 0
    local function frame(kind, name, parent, level, unit)
        local f = CreateFrame(kind, name, parent)
        f:SetFrameStrata("MEDIUM")
        f:SetFrameLevel(level)
        function f:GetAttribute(key) if key == "unit" then return unit end end
        function f:GetChildren()
            layerVisits = layerVisits + 1
            return unpack(self.children)
        end
        return f
    end
    local root = frame("Frame", "ElvUIParent", UIParent, 1)
    local hider = frame("Frame", "ElvUF_UFParentFrameHider", root, 2)
    local target = frame("Button", "ElvUF_Target", hider, 5, "target")
    target.Health = frame("StatusBar", nil, target, 6)
    target.Portrait = frame("Frame", nil, target, 40)
    for i = 1, 1000 do
        frame("Frame", nil, root, 500)
    end
    DoesItDieDB.customHealthBar = "ElvUF_Target.Health"
    DoesItDieDB.customIconAnchor = ""
    targetGuid = nil
""")
step("attach to a unit frame below a shared UI root", lambda: ns.display.attach(True))
step("ten idle seconds on a custom unit frame", lambda: [H.update(1.1) for _ in range(10)])
check("  no layer checks while nothing shows (issue #36)", G.layerVisits, 0)


def dot_and_settle():
    G.targetGuid = "Creature-0-1-2-3-3099-000001"
    H.fire("PLAYER_TARGET_CHANGED")
    H.fire("UNIT_SPELLCAST_SUCCEEDED", "player", "cast-E1", 172)
    H.update(1.1)
    lua.execute("layerVisits = 0")


step("Corruption on the target", dot_and_settle)
# Three, not ten: the Corruption never ticks here, so it's dropped as resisted after two missed ticks.
step("three layer checks while it shows", lambda: [H.update(1.1) for _ in range(3)])
check("  visits only target, health and portrait on each check", G.layerVisits, 9)
check("  marker above target portrait, not unrelated UI", G.DoesItDieRemaining.level, 41)
check("  picker still finds the top-level UI root", same(ns.frameRoot(G.ElvUF_Target.Health), G.ElvUIParent), True)
check("  unit-less replacement keeps its previous root", same(ns.frameRoot(custom_bar, "target"), G.MyTargetFrame), True)
lua.execute("""
    local focus = CreateFrame("Button", "ElvUF_Focus", ElvUF_UFParentFrameHider)
    function focus:GetAttribute(key) if key == "unit" then return "focus" end end
    focus.Health = CreateFrame("StatusBar", nil, focus)
    function ElvUF_Target.Health:GetAttribute() error("unreadable attribute") end
""")
check("  unreadable child attribute still reaches unit owner",
      same(ns.frameRoot(G.ElvUF_Target.Health, "target"), G.ElvUF_Target), True)
check("  focus stays inside its own unit frame",
      same(ns.frameRoot(G.ElvUF_Focus.Health, "focus"), G.ElvUF_Focus), True)
lua.execute("""
    function issecretvalue(v) return v == SECRET end
    function ElvUF_Target.Health:GetAttribute() return SECRET end
""")
check("  secret unit attribute is skipped",
      same(ns.frameRoot(G.ElvUF_Target.Health, "target"), G.ElvUF_Target), True)
lua.execute("issecretvalue = nil")

# Hidden Edit Mode selection frame (HIGH/1000) under target frame must not pull the marker into its strata/level.
lua.execute("""
    local sel = CreateFrame("Frame", nil, ElvUF_Target)
    sel:SetFrameStrata("HIGH")
    sel:SetFrameLevel(1000)
    sel:Hide()
    function sel:GetChildren() layerVisits = layerVisits + 1 return unpack(self.children) end
""")
G.targetGuid = "Creature-0-1-2-3-3099-000001"
H.fire("PLAYER_TARGET_CHANGED")
H.fire("UNIT_SPELLCAST_SUCCEEDED", "player", "cast-E2", 172)
H.update(1.1)
check("  hidden selection frame doesn't pull marker to HIGH/1000",
      (G.DoesItDieRemaining.strata, G.DoesItDieRemaining.level), ("MEDIUM", 41))

# Overlay StatusBars (TempMaxHealthLoss, absorb, prediction) are ignored by Pick and redirected to HealthBar.
lua.execute("""
    local holder = CreateFrame("Frame", "CamelotBarsHolder", UIParent)
    local realBar = CreateFrame("StatusBar", nil, holder)
    local lossBar = CreateFrame("StatusBar", nil, holder)
    function realBar:GetParentKey() return "HealthBar" end
    function lossBar:GetParentKey() return "TempMaxHealthLoss" end
    holder.HealthBar = realBar
    holder.TempMaxHealthLoss = lossBar
    DoesItDieDB.customHealthBar = "CamelotBarsHolder.TempMaxHealthLoss"
""")
check("  isOverlayBar flags TempMaxHealthLoss, not HealthBar",
      (ns.isOverlayBar(G.CamelotBarsHolder.TempMaxHealthLoss), ns.isOverlayBar(G.CamelotBarsHolder.HealthBar)),
      (True, False))
check("  healthBarOf redirects saved TempMaxHealthLoss to sibling HealthBar",
      same(ns.healthBarOf(G.CamelotBarsHolder.TempMaxHealthLoss), G.CamelotBarsHolder.HealthBar), True)
lua.execute('DoesItDieDB.customHealthBar = "ElvUF_Target.Health"')


# Party DoTs (Party.lua, issue #25): a party member's message adds to the target's total and the API's list, only
# with the option on. Party.lua's own behavior is in tools/test_party.py; this checks the wiring.
lua.execute("""
    partySent = {}
    C_ChatInfo = {
        RegisterAddonMessagePrefix = function() return 0 end,
        SendAddonMessage = function(prefix, msg, channel) table.insert(partySent, msg) return 0 end,
    }
    function IsInGroup() return true end
    function IsInRaid() return false end
    function IsEncounterInProgress() return false end
    function UnitName(unit) if unit == "player" then return "Priest" elseif unit == "party1" then return "Warlock" end end
""")
G.targetGuid = "Creature-0-1-2-3-3099-000001"
base_damage, base_count = ns.tracking.targetRemainingDamage()[:2]
PARTY_MSG = "M;1;" + G.targetGuid + ";172:32:240:1:4:3"  # 172 = Corruption in the fake spellbook
step("party message with the option off", lambda: H.fire("CHAT_MSG_ADDON", "DoesItDie", PARTY_MSG, "PARTY",
                                                         "Warlock-Realm"))
check("  option off: target total unchanged", ns.tracking.targetRemainingDamage()[0], base_damage)
check("party option is off by default", G.DoesItDieDB.partyDots, False)
G.DoesItDieDB.partyDots = True
step("party message with the option on", lambda: (H.update(0.3), H.fire("CHAT_MSG_ADDON", "DoesItDie", PARTY_MSG,
                                                                        "PARTY", "Warlock-Realm")))
check("  target total includes the party member's DoT", ns.tracking.targetRemainingDamage()[:2],
      (base_damage + 240, base_count + 1))
remote = [e for e in G.DoesItDie.GetDoTs("target").values() if e.remote]
check("  API GetDoTs lists it with remote = true", [(e.name, e.damage, e.sender) for e in remote],
      [("Corruption", 240, "Warlock")])
check("  API GetRemainingDamage includes it", G.DoesItDie.GetRemainingDamage("target")[0], base_damage + 240)
step("display loop with a party DoT", lambda: H.update(0.2))
step("nameplate loop with a party DoT", lambda: ns.dotBreakdownForUnit("nameplate1"))
check("  nameplate sees it too", ns.dotBreakdownForUnit("nameplate1")[1], base_damage + 240)
check("party DoT segment uses the party color", list(ns.dotColor(remote[0]).values()) if remote else None,
      list(ns.display.colorById(G.DoesItDieDB.partyDotColor).values()))
# The real tracker -> wire path: a party member answered, I cast Corruption on the target, and it goes out.
step("a party member with the option answers the hello", lambda: H.fire("CHAT_MSG_ADDON", "DoesItDie", "H;1;a",
                                                                        "PARTY", "Warlock-Realm"))
lua.execute("for i = #partySent, 1, -1 do partySent[i] = nil end")
step("cast Corruption on the target", lambda: (
    H.fire("UNIT_SPELLCAST_SENT", "player", "Kobold", "Cast-P", 172),
    H.fire("UNIT_SPELLCAST_SUCCEEDED", "player", "Cast-P", 172),
    H.update(0.5)))
own_msgs = [m for m in G.partySent.values() if m.startswith("M;1;" + G.targetGuid + ";172:")]
check("  my Corruption goes out to the party", len(own_msgs) >= 1, True)
decoded = ns.party.decode(own_msgs[-1]) if own_msgs else (None, None)
check("  ...and decodes: Corruption, Shadow, 4 ticks of 3 s", decoded[0] == "M" and [
    (d.spellID, d.school, d.ticksLeft, d.interval) for d in decoded[1].dots.values()], [(172, 32, 4, 3)])
G.DoesItDieDB.partyDots = False
step("option off again", lambda: H.update(0.3))
check("  option off: no party DoTs in the list (only my own)",
      [e.remote for e in ns.dotBreakdownForUnit("target")[0].values() if e.remote], [])
check("Marker tab has the party rows", lua.eval("""function(frames)
    local found = 0
    for _, f in ipairs(frames) do
        if f.text == "Share DoTs with party" or f.text == "Party DoT color" then found = found + 1 end
    end
    return found >= 2
end""")(G.frames), True)
G.targetGuid = None


# Target & focus marker parenting and layering on Forever:
# - Markers hang directly on healthBar out of combat (so LOW-strata UIParent issues don't hide them) and return
#   to UIParent during options preview.
# - Secret strata/level, gamepad UI, or combat lockdown fallback raises the marker/skull to HIGH (+1000).
# - The 300-frame walk cap still considers healthBar and unwrapped Texture portraits, and throwing children
#   do not abort the scan.
G.targetGuid = "Creature-0-1-2-3-3099-000001"
H.fire("PLAYER_TARGET_CHANGED")
H.fire("UNIT_SPELLCAST_SUCCEEDED", "player", "cast-P1", 172)
step("target marker hangs on healthBar out of combat", lambda: [H.update(1.1) for _ in range(3)])
check("  parent is ElvUF_Target.Health", same(G.DoesItDieRemaining.parent, G.ElvUF_Target.Health), True)
check("  layer stays pinned above portrait across ticks", (G.DoesItDieRemaining.strata, G.DoesItDieRemaining.level), ("MEDIUM", 41))

step("options preview moves target marker back to UIParent", lambda: (G.SlashCmdList.DOESITDIE(""), H.update(0.2)))
check("  preview parent is UIParent", same(G.DoesItDieRemaining.parent, G.UIParent), True)
check("  preview strata is FULLSCREEN", G.DoesItDieRemaining.strata, "FULLSCREEN")

step("closing options returns target marker to healthBar", lambda: (G.DoesItDieOptions.Hide(G.DoesItDieOptions), H.update(1.1)))
check("  restored parent is ElvUF_Target.Health", same(G.DoesItDieRemaining.parent, G.ElvUF_Target.Health), True)
check("  restored layer is MEDIUM/41", (G.DoesItDieRemaining.strata, G.DoesItDieRemaining.level), ("MEDIUM", 41))

# Mid-combat attach when marker starts on UIParent: fallback floor while locked in combat, then drops on leave.
G.DoesItDieDB.customHealthBar = "Missing.Bar"
G.DoesItDieDB.customIconAnchor = ""
step("detach to missing bar out of combat", lambda: (ns.reattach(), H.update(1.1)))
check("  detached marker sits on UIParent", same(G.DoesItDieRemaining.parent, G.UIParent), True)
G.combat = True
G.DoesItDieDB.customHealthBar = "ElvUF_Target.Health"
step("attach to ElvUF_Target.Health during combat lockdown", lambda: (
    ns.reattach(), H.fire("UNIT_SPELLCAST_SUCCEEDED", "player", "cast-P2", 172), H.update(1.1)))
check("  combat lockdown keeps marker on UIParent", same(G.DoesItDieRemaining.parent, G.UIParent), True)
check("  fallback floor lifts stuck marker to HIGH",
      (G.DoesItDieRemaining.strata, G.DoesItDieRemaining.level >= 1041), ("HIGH", True))
G.combat = False
step("leave combat so recheckAttach reparents onto healthBar", lambda: H.update(1.1))
check("  reparented onto ElvUF_Target.Health", same(G.DoesItDieRemaining.parent, G.ElvUF_Target.Health), True)
check("  layer returns to MEDIUM/41", (G.DoesItDieRemaining.strata, G.DoesItDieRemaining.level), ("MEDIUM", 41))

# Secret strata/level on a visible child and gamepad UI both trigger the fallback floor (hidden secret child does not).
lua.execute("""
    function issecretvalue(v) return v == SECRET end
    SecretChildFrame = CreateFrame("Frame", nil, ElvUF_Target)
    function SecretChildFrame:GetFrameStrata() return SECRET end
    function SecretChildFrame:GetFrameLevel() return SECRET end
""")
step("visible child with secret strata/level", lambda: (
    H.fire("UNIT_SPELLCAST_SUCCEEDED", "player", "cast-P3", 172), H.update(1.1)))
check("  target marker uses HIGH fallback",
      (G.DoesItDieRemaining.strata, G.DoesItDieRemaining.level >= 1041), ("HIGH", True))
check("  kill icon uses HIGH >= 2000 fallback",
      (G.DoesItDieSkull.strata, G.DoesItDieSkull.level >= 2000), ("HIGH", True))
lua.execute("SecretChildFrame:Hide()")
step("hiding secret child drops back to exact target layer", lambda: H.update(1.1))
check("  back to MEDIUM/41", (G.DoesItDieRemaining.strata, G.DoesItDieRemaining.level), ("MEDIUM", 41))
lua.execute("IsUsingGamepad = function() return true end")
step("gamepad UI active", lambda: H.update(1.1))
check("  marker uses HIGH fallback under gamepad UI",
      (G.DoesItDieRemaining.strata, G.DoesItDieRemaining.level >= 1041), ("HIGH", True))
check("  skull uses HIGH >= 2000 under gamepad UI",
      (G.DoesItDieSkull.strata, G.DoesItDieSkull.level >= 2000), ("HIGH", True))
lua.execute("IsUsingGamepad = nil; issecretvalue = nil")
step("gamepad UI off again", lambda: H.update(1.1))
check("  back to MEDIUM/41", (G.DoesItDieRemaining.strata, G.DoesItDieRemaining.level), ("MEDIUM", 41))

# Capped walk (>300 siblings) and throwing child GetChildren/GetFrameStrata still cover healthBar and Texture portrait.
lua.execute("""
    local capped = CreateFrame("Button", "CappedTargetFrame", UIParent)
    capped:SetFrameStrata("LOW")
    capped:SetFrameLevel(2)
    function capped:GetAttribute(k) if k == "unit" then return "target" end end
    function capped:GetChildren() return unpack(self.children) end
    local kids = {}
    for i = 1, 320 do
        local c = CreateFrame("Frame", nil, capped)
        c:SetFrameStrata("LOW")
        c:SetFrameLevel(1)
        kids[#kids + 1] = c
    end
    local badChildren = CreateFrame("Frame", nil, capped)
    badChildren:SetFrameStrata("LOW")
    badChildren:SetFrameLevel(1)
    function badChildren:GetChildren() error("children boom") end
    local bar = CreateFrame("StatusBar", nil, capped)
    bar:SetFrameStrata("MEDIUM")
    bar:SetFrameLevel(50)
    capped.Health = bar
    local portraitHost = CreateFrame("Frame", nil, capped)
    portraitHost:SetFrameStrata("MEDIUM")
    portraitHost:SetFrameLevel(55)
    capped.Portrait = portraitHost:CreateTexture()
    DoesItDieDB.customHealthBar = "CappedTargetFrame.Health"
    DoesItDieDB.customIconAnchor = "CappedTargetFrame.Portrait"
""")
step("capped tree with throwing GetChildren still reaches Health and Texture portrait parent", lambda: (
    ns.reattach(), H.fire("UNIT_SPELLCAST_SUCCEEDED", "player", "cast-P4", 172), H.update(1.1)))
check("  marker placed above unwrapped portrait parent (MEDIUM/56)",
      (G.DoesItDieRemaining.strata, G.DoesItDieRemaining.level), ("MEDIUM", 56))
lua.execute("""
    DoesItDieDB.customHealthBar = "ElvUF_Target.Health"
    DoesItDieDB.customIconAnchor = ""
    local badStrata = CreateFrame("Frame", nil, ElvUF_Target)
    function badStrata:GetFrameStrata() error("strata boom") end
    BadStrataChild = badStrata
""")
step("throwing child GetFrameStrata does not error and triggers fallback floor", lambda: (
    ns.reattach(), H.update(1.1)))
check("  marker uses HIGH fallback on unreadable child strata",
      (G.DoesItDieRemaining.strata, G.DoesItDieRemaining.level >= 1041), ("HIGH", True))
lua.execute("BadStrataChild:Hide()")

# Focus marker reparents onto the focus bar out of combat, skips itself, and uses fallback floor on secret child.
lua.execute("""
    EllesmereUIUnitFrames_Focus = nil
    focusGuid = "Creature-0-1-2-3-3099-0000F1"
    savedFocusUnitName = UnitName
    function UnitName(unit) if unit == "focus" and focusGuid then return "FocusMob" end return savedFocusUnitName(unit) end
    function FocusFrame:GetChildren() return unpack(self.children) end
""")
step("focus marker hangs on BlizzardFocusBar out of combat", lambda: (
    H.fire("UNIT_SPELLCAST_SENT", "player", "FocusMob", "cast-FP1", 172),
    H.fire("UNIT_SPELLCAST_SUCCEEDED", "player", "cast-FP1", 172),
    H.update(1.1)))
focus_markers_p = markers_on(G.BlizzardFocusBar)
check("  focus marker parent is BlizzardFocusBar",
      same(focus_markers_p[0].parent, G.BlizzardFocusBar) if focus_markers_p else None, True)
check("  focus marker layer stays at MEDIUM/1006",
      (focus_markers_p[0].strata, focus_markers_p[0].level) if focus_markers_p else None, ("MEDIUM", 1006))

lua.execute("""
    function issecretvalue(v) return v == SECRET end
    FocusSecretChild = CreateFrame("Frame", nil, FocusFrame)
    function FocusSecretChild:GetFrameStrata() return SECRET end
    function FocusSecretChild:GetFrameLevel() return SECRET end
""")
step("focus visible child with secret strata triggers HIGH fallback", lambda: H.update(1.1))
check("  focus marker lifted to HIGH >= 2006",
      (focus_markers_p[0].strata, focus_markers_p[0].level >= 2006) if focus_markers_p else None, ("HIGH", True))
lua.execute("FocusSecretChild:Hide(); issecretvalue = nil")
step("hiding focus secret child drops back to MEDIUM/1006", lambda: H.update(1.1))
check("  focus marker back to MEDIUM/1006",
      (focus_markers_p[0].strata, focus_markers_p[0].level) if focus_markers_p else None, ("MEDIUM", 1006))

# Mid-combat focus bar swap keeps marker on previous bar with fallback floor, then reparents after combat.
G.combat = True
lua.execute("""
    BBFFocusCombatBar = CreateFrame("StatusBar", nil, FocusFrame)
    BBF = { HealthBar = function(frame) if frame == FocusFrame then return BBFFocusCombatBar end end }
""")
step("focus bar swaps during combat lockdown", lambda: H.update(1.1))
check("  focus marker parent stays on BlizzardFocusBar during combat",
      same(focus_markers_p[0].parent, G.BlizzardFocusBar) if focus_markers_p else None, True)
check("  focus marker lifted to HIGH fallback while stuck off-bar",
      (focus_markers_p[0].strata, focus_markers_p[0].level >= 2006) if focus_markers_p else None, ("HIGH", True))
G.combat = False
step("leaving combat moves focus marker onto BBFFocusCombatBar", lambda: H.update(1.1))
check("  focus marker parent moved to BBFFocusCombatBar",
      same(focus_markers_p[0].parent, G.BBFFocusCombatBar) if focus_markers_p else None, True)
check("  focus marker returns to MEDIUM/1006",
      (focus_markers_p[0].strata, focus_markers_p[0].level) if focus_markers_p else None, ("MEDIUM", 1006))

lua.execute("BBF, BBFFocusCombatBar = nil, nil; focusGuid = nil; UnitName = savedFocusUnitName; FocusFrame.GetChildren = nil")
G.targetGuid = None
G.combat = False
H.update(1.1)


def lua_quote(text):
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


# --dump-strings FILE: every text the window and messages above asked T for (Locale.lua), as a table to paste
# into a language file's STRINGS and fill in.
if "--dump-strings" in sys.argv:
    import re
    path = sys.argv[sys.argv.index("--dump-strings") + 1]
    seen = {k for k in ns.locale.seenStrings.keys() if isinstance(k, str)}
    # Plus every literal T("...") in the source: text only shown in states the run above didn't reach.
    for name in files:
        source = open(os.path.join(ADDON, name), encoding="utf-8").read()
        for literal in re.findall(r'\bT\("((?:[^"\\]|\\.)*)"\)', source):
            seen.add(literal.replace('\\"', '"').replace("\\n", "\n").replace("\\\\", "\\"))
    keys = sorted(seen)
    with open(path, "w", encoding="utf-8", newline="\n") as out:
        out.write("local STRINGS = {\n")
        for key in keys:
            out.write(f"    [{lua_quote(key)}] = \"\",\n")
        out.write("}\n")
    print(f"\n{len(keys)} strings written to {path}")

print(f"\n{'all passed' if not failures else str(failures) + ' FAILED'}")
sys.exit(1 if failures else 0)
