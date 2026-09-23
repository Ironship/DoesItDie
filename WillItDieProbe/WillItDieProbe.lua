-- WillItDie Probe
-- Answers: which of the values WillItDie needs can addon code actually use in combat?
-- Every API call is wrapped in pcall so a blocked/missing API is reported, never fatal.

local MAX_LOG_LINES = 1000
local MAX_EVENT_LOGS_PER_FIGHT = 8
local AUTO_SNAPSHOT_DELAY = 4

local log = {}
local eventCounts = {}
local fightLogged = 0

local function out(msg)
    table.insert(log, date("%H:%M:%S") .. " " .. msg)
    if #log > MAX_LOG_LINES then table.remove(log, 1) end
    DEFAULT_CHAT_FRAME:AddMessage("|cff66ccffWID|r " .. msg)
end

local function isSecret(v)
    if type(issecretvalue) ~= "function" then return false end
    local ok, r = pcall(issecretvalue, v)
    return ok and r or false
end

-- Describes a value and whether addon code can do maths / comparisons with it.
local function probe(v)
    if v == nil then return "nil" end
    local secret = isSecret(v)
    local shown = "<secret>"
    if not secret then
        local ok, s = pcall(tostring, v)
        shown = ok and s or "<tostring blocked>"
    end
    if type(v) ~= "number" and not secret then return shown end
    local mathOK = pcall(function() return v + 0 end)
    local cmpOK = pcall(function() return v < 1 end)
    return string.format("%s [secret=%s math=%s cmp=%s]", shown, tostring(secret),
        mathOK and "ok" or "BLOCKED", cmpOK and "ok" or "BLOCKED")
end

local function try(label, fn, ...)
    local ok, a, b, c, d = pcall(fn, ...)
    if not ok then
        out(label .. ": ERROR " .. tostring(a))
        return false
    end
    return true, a, b, c, d
end

local function exists(fnName)
    return type(_G[fnName]) == "function"
end

---------------------------------------------------------------------------
-- Kill-line test bar: target health fed secret values, plus a marker at N damage
---------------------------------------------------------------------------

local markDamage = nil

local markFrame = CreateFrame("Frame", nil, UIParent)
markFrame:SetSize(240, 22)
markFrame:SetPoint("CENTER", 0, -150)
markFrame:Hide()

local bg = markFrame:CreateTexture(nil, "BACKGROUND")
bg:SetAllPoints()
bg:SetColorTexture(0, 0, 0, 0.6)

local hpBar = CreateFrame("StatusBar", nil, markFrame)
hpBar:SetAllPoints()
hpBar:SetStatusBarTexture("Interface\\TargetingFrame\\UI-StatusBar")
hpBar:SetStatusBarColor(0.1, 0.8, 0.1)

local markBar = CreateFrame("StatusBar", nil, markFrame)
markBar:SetAllPoints()
markBar:SetFrameLevel(hpBar:GetFrameLevel() + 1)
markBar:SetStatusBarTexture("Interface\\Buttons\\WHITE8X8")
markBar:SetStatusBarColor(1, 0, 0, 0.25)

local markLine = markBar:CreateTexture(nil, "OVERLAY")
markLine:SetColorTexture(1, 1, 1, 1)
markLine:SetWidth(2)
markLine:SetPoint("TOP", markBar:GetStatusBarTexture(), "TOPRIGHT")
markLine:SetPoint("BOTTOM", markBar:GetStatusBarTexture(), "BOTTOMRIGHT")

local markLabel = markFrame:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
markLabel:SetPoint("BOTTOM", markFrame, "TOP", 0, 2)

local markErrorLogged = false
local elapsedSince = 0
markFrame:SetScript("OnUpdate", function(self, elapsed)
    elapsedSince = elapsedSince + elapsed
    if elapsedSince < 0.1 then return end
    elapsedSince = 0
    if not UnitExists("target") then return end
    local ok, err = pcall(function()
        local hpMax = UnitHealthMax("target")
        hpBar:SetMinMaxValues(0, hpMax)
        hpBar:SetValue(UnitHealth("target"))
        markBar:SetMinMaxValues(0, hpMax)
        markBar:SetValue(markDamage)
    end)
    if not ok and not markErrorLogged then
        markErrorLogged = true
        out("Kill-line bar update ERROR " .. tostring(err))
    end
end)

local function setMark(n)
    markDamage = n
    markErrorLogged = false
    if n then
        markLabel:SetText("WID test: kill line at " .. n .. " damage")
        markFrame:Show()
        out("Kill-line bar shown at " .. n .. " damage. Target something; /widprobe mark to hide.")
    else
        markFrame:Hide()
        out("Kill-line bar hidden.")
    end
end

---------------------------------------------------------------------------
-- Snapshot
---------------------------------------------------------------------------

local testBar = CreateFrame("StatusBar")
testBar:Hide()

local function probeAuras(filter, limit)
    if not (C_UnitAuras and C_UnitAuras.GetAuraDataByIndex) then
        out("  C_UnitAuras.GetAuraDataByIndex: missing")
        return
    end
    for i = 1, limit do
        local ok, aura = pcall(C_UnitAuras.GetAuraDataByIndex, "target", i, filter)
        if not ok then
            out(string.format("  [%s #%d] ERROR %s", filter, i, tostring(aura)))
            return
        end
        if not aura then
            if i == 1 then out("  [" .. filter .. "] none") end
            return
        end
        local fok, err = pcall(function()
            local pts = aura.points and aura.points[1]
            out(string.format("  [%s #%d] %s id=%s dur=%s exp=%s stacks=%s src=%s pts1=%s",
                filter, i, probe(aura.name), probe(aura.spellId), probe(aura.duration),
                probe(aura.expirationTime), probe(aura.applications),
                probe(aura.sourceUnit), probe(pts)))
        end)
        if not fok then out(string.format("  [%s #%d] field read ERROR %s", filter, i, tostring(err))) end
    end
end

local function snapshot(reason)
    out("===== SNAPSHOT (" .. reason .. ") =====")
    local _, build, _, iface = GetBuildInfo()
    local _, class = UnitClass("player")
    out(string.format("build=%s iface=%s class=%s level=%s inCombat=%s issecretvalue=%s",
        tostring(build), tostring(iface), tostring(class), tostring(UnitLevel("player")),
        tostring(UnitAffectingCombat("player")), tostring(exists("issecretvalue"))))

    if C_Secrets and C_Secrets.ShouldAurasBeSecret then
        local ok, r = pcall(C_Secrets.ShouldAurasBeSecret)
        out("C_Secrets.ShouldAurasBeSecret() = " .. (ok and tostring(r) or ("ERROR " .. tostring(r))))
    else
        out("C_Secrets.ShouldAurasBeSecret: missing")
    end

    -- 1. Player stats (needed to compute DoT damage ourselves)
    out("-- Player spell power by school (2=Holy 3=Fire 4=Nature 5=Frost 6=Shadow 7=Arcane)")
    if exists("GetSpellBonusDamage") then
        for school = 2, 7 do
            local ok, v = pcall(GetSpellBonusDamage, school)
            out(string.format("  school %d: %s", school, ok and probe(v) or ("ERROR " .. tostring(v))))
        end
    else
        out("  GetSpellBonusDamage: missing")
    end
    if exists("UnitAttackPower") then
        local ok, base, pos, neg = pcall(UnitAttackPower, "player")
        out("  UnitAttackPower: " .. (ok and (probe(base) .. " +" .. probe(pos)) or ("ERROR " .. tostring(base))))
    end

    -- 2. Event channels so far
    local names = {}
    for name, n in pairs(eventCounts) do table.insert(names, name .. "=" .. n) end
    table.sort(names)
    out("-- Events received since load: " .. (#names > 0 and table.concat(names, " ") or "none"))

    if not UnitExists("target") then
        out("-- No target. Target a mob and run /widprobe probe again.")
        return
    end

    -- 3. Target health
    out("-- Target: " .. probe(UnitName("target")))
    local okH, hp = try("UnitHealth", UnitHealth, "target")
    local okM, hpMax = try("UnitHealthMax", UnitHealthMax, "target")
    if okH then out("  UnitHealth    = " .. probe(hp)) end
    if okM then out("  UnitHealthMax = " .. probe(hpMax)) end
    if exists("UnitHealthPercent") then
        local ok, pct = pcall(UnitHealthPercent, "target")
        out("  UnitHealthPercent = " .. (ok and probe(pct) or ("ERROR " .. tostring(pct))))
    end

    -- 4. Can a StatusBar take the (possibly secret) health values? This is the overlay approach.
    if okM and okH then
        local s1, e1 = pcall(testBar.SetMinMaxValues, testBar, 0, hpMax)
        out("  StatusBar:SetMinMaxValues(0, hpMax): " .. (s1 and "ok" or ("BLOCKED " .. tostring(e1))))
        local s2, e2 = pcall(testBar.SetValue, testBar, hp)
        out("  StatusBar:SetValue(hp): " .. (s2 and "ok" or ("BLOCKED " .. tostring(e2))))
        local s3, e3 = pcall(testBar.SetValue, testBar, 1000)
        out("  StatusBar:SetValue(1000 plain) with secret max: " .. (s3 and "ok" or ("BLOCKED " .. tostring(e3))))
    end

    -- 5. Auras on the target
    out("-- Target debuffs cast by me")
    probeAuras("HARMFUL|PLAYER", 10)
    out("-- Target buffs")
    probeAuras("HELPFUL", 10)
end

---------------------------------------------------------------------------
-- Events
---------------------------------------------------------------------------

local f = CreateFrame("Frame")

-- COMBAT_LOG_EVENT_UNFILTERED is left out: registering it is suspected of raising the
-- "blocked from an action only available to the Blizzard UI" popup.
local registrations = {}
for _, event in ipairs({
    "ADDON_LOADED", "PLAYER_LOGOUT", "PLAYER_REGEN_DISABLED",
    "ADDON_ACTION_BLOCKED", "ADDON_ACTION_FORBIDDEN",
    "UNIT_COMBAT", "UNIT_SPELLCAST_SUCCEEDED", "UNIT_SPELLCAST_SENT",
    "UNIT_AURA", "UNIT_HEALTH",
}) do
    local ok, err = pcall(f.RegisterEvent, f, event)
    table.insert(registrations, event .. "=" .. (ok and "ok" or ("ERROR " .. tostring(err))))
end

local function spellInfo(spellID)
    local name, desc = "?", "?"
    if C_Spell and C_Spell.GetSpellName then
        local ok, n = pcall(C_Spell.GetSpellName, spellID); if ok then name = probe(n) end
    elseif exists("GetSpellInfo") then
        local ok, n = pcall(GetSpellInfo, spellID); if ok then name = probe(n) end
    end
    local descFn = (C_Spell and C_Spell.GetSpellDescription) or GetSpellDescription
    if descFn then
        local ok, d = pcall(descFn, spellID); if ok then desc = probe(d) end
    end
    return name, desc
end

f:SetScript("OnEvent", function(self, event, ...)
    eventCounts[event] = (eventCounts[event] or 0) + 1

    if event == "ADDON_LOADED" then
        if ... ~= "WillItDieProbe" then return end
        WillItDieProbeDB = WillItDieProbeDB or {}
        log = WillItDieProbeDB.log or log
        out("Loaded (session start, probe v2). Type /widprobe for help.")
        out("Event registrations: " .. table.concat(registrations, " "))

    elseif event == "PLAYER_LOGOUT" then
        WillItDieProbeDB.log = log

    elseif event == "ADDON_ACTION_BLOCKED" or event == "ADDON_ACTION_FORBIDDEN" then
        local addon, func = ...
        out(string.format("%s addon=%s function=%s", event, tostring(addon), tostring(func)))

    elseif event == "PLAYER_REGEN_DISABLED" then
        fightLogged = 0
        out("Entered combat. Auto-snapshot in " .. AUTO_SNAPSHOT_DELAY .. "s.")
        C_Timer.After(AUTO_SNAPSHOT_DELAY, function() snapshot("auto, in combat") end)

    elseif event == "UNIT_COMBAT" then
        local unit, action, flag, amount, school = ...
        if fightLogged < MAX_EVENT_LOGS_PER_FIGHT then
            fightLogged = fightLogged + 1
            out(string.format("UNIT_COMBAT unit=%s action=%s flag=%s amount=%s school=%s",
                probe(unit), probe(action), probe(flag), probe(amount), probe(school)))
        end

    elseif event == "UNIT_SPELLCAST_SUCCEEDED" then
        local unit, _, spellID = ...
        if unit ~= "player" then return end
        local name, desc = spellInfo(spellID)
        out(string.format("CAST %s id=%s time=%s desc=%s", name, probe(spellID), probe(GetTime()), desc))
    end
end)

---------------------------------------------------------------------------
-- Slash commands
---------------------------------------------------------------------------

SLASH_WILLITDIEPROBE1 = "/widprobe"
SlashCmdList.WILLITDIEPROBE = function(msg)
    msg = strlower(strtrim(msg or ""))
    local cmd, arg = msg:match("^(%S*)%s*(.-)$")
    if cmd == "probe" then
        snapshot("manual")
    elseif cmd == "mark" then
        setMark(tonumber(arg))
    elseif cmd == "clear" then
        wipe(log)
        out("Log cleared.")
    else
        out("/widprobe probe     - snapshot what addon code can read right now")
        out("/widprobe mark <n> - show test bar with a kill line at n damage (/widprobe mark to hide)")
        out("/widprobe clear - clear the saved log")
        out("Log is written to SavedVariables/WillItDieProbe.lua on /reload or logout.")
    end
end
