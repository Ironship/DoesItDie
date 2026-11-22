-- DoesItDie execute kill icon: the player's execute ability (Execute, Hammer of Wrath, Shadow Word: Death,
-- Shadowburn) shown by the target frame when its hit would kill the target.
--
-- Target health is secret, so this uses the kill icon's trick (Display.lua): a very long invisible StatusBar
-- with max = the target's health and value = the ability's estimated hit, inside a small clipping frame. The
-- ability's icon rides the end of the fill and only shows when the fill reaches the end: hit >= health.
--
-- The hit is estimated low on purpose (a missing icon costs a GCD; a false one gets you killed):
--  * the tooltip's low end ("474 to 522" -> 474), which leaves out spell/attack power, times
--  * a ratio learned from the damage meter after each combat: that spell's total over the casts that landed in
--    it, compared with the tooltip's average. Crits are taken out with the crit chance (readable out of combat);
--    misses stay in, which only lowers the ratio.
--  * Execute adds its "each extra point of rage" damage when rage is readable (UnitPower); if not, the base.
-- C_Spell.IsSpellUsable, when readable, hides it while the ability can't be cast (Execute and Hammer of Wrath
-- above 20%, not enough rage). Unverified in-game.

local ADDON_NAME, ns = ...

local T = ns.locale.T
local BAR_LENGTH = 10000 -- the icon slides in over size / BAR_LENGTH of health short of lethal (0.3% at 32px)
local UPDATE_INTERVAL = 0.1
local LEARN_RATIO_MIN, LEARN_RATIO_MAX = 0.5, 3 -- a meter total outside this vs the tooltip: something got mixed in
local LEARN_WEIGHT_CAP = 10 -- older fights count as at most this many casts, so gear changes catch up
local METER_TRIES, METER_RETRY_SECONDS = 20, 0.5
local SPELL_CRIT_MULTIPLIER, MELEE_CRIT_MULTIPLIER = 1.5, 2
local RAGE = 1 -- Enum.PowerType.Rage
local DEFAULT_RAGE_COST = 15

-- Per class: the English name and Classic Era spell IDs, highest rank first (Shadow Word: Death is Forever's
-- own; its IDs are unknown, so it's found by name). school: the GetSpellCritChance school index.
local EXECUTES = {
    WARRIOR = { name = "Execute", ids = { 20662, 20661, 20660, 20658, 5308 }, melee = true, rage = true },
    PALADIN = { name = "Hammer of Wrath", ids = { 24239, 24274, 24275 }, school = 2 },
    PRIEST = { name = "Shadow Word: Death", ids = {}, school = 6 },
    WARLOCK = { name = "Shadowburn", ids = { 18871, 18870, 18869, 18868, 18867, 17877 }, school = 6 },
}

local db -- set on first use (ns.db is filled on ADDON_LOADED)

local function isSecret(v)
    if type(issecretvalue) ~= "function" then return false end
    local ok, r = pcall(issecretvalue, v)
    return ok and r or false
end

-- A plain value from fn(...), or nil if it errors, is secret or isn't of type `kind`.
local function readable(kind, fn, ...)
    if type(fn) ~= "function" then return nil end
    local ok, v = pcall(fn, ...)
    if ok and not isSecret(v) and type(v) == kind then return v end
end

---------------------------------------------------------------------------
-- The ability and its estimate
---------------------------------------------------------------------------

local ability -- { spellID, name, icon, info = EXECUTES entry } or nil (class has none, or not learned yet)

local function knows(spellID)
    if type(IsPlayerSpell) == "function" then return readable("boolean", IsPlayerSpell, spellID) == true end
    return readable("boolean", IsSpellKnown, spellID) == true
end

local function findAbility()
    local _, class = UnitClass("player")
    local info = EXECUTES[class]
    if not info then return nil end
    for _, id in ipairs(info.ids) do
        if knows(id) then return id, info end
    end
    -- By name: the English one, then the client's own name for the top rank (other languages).
    local names = { info.name }
    if info.ids[1] then names[2] = readable("string", C_Spell and C_Spell.GetSpellName, info.ids[1]) end
    for _, name in ipairs(names) do
        local spell = C_Spell and C_Spell.GetSpellInfo and readable("table", C_Spell.GetSpellInfo, name)
        local id = spell and spell.spellID
        if type(id) == "number" and not isSecret(id) and (knows(id) or not info.ids[1]) then return id, info end
    end
end

local function updateAbility()
    local id, info = findAbility()
    if id == (ability and ability.spellID) then return end
    if not id then
        ability = nil
        return
    end
    ability = { spellID = id, info = info,
        name = readable("string", C_Spell and C_Spell.GetSpellName, id) or info.name,
        icon = readable("number", C_Spell and C_Spell.GetSpellTexture, id)
            or readable("string", C_Spell and C_Spell.GetSpellTexture, id) or "Interface\\Icons\\INV_Sword_48" }
    ns.trace(string.format("EXEC watching %s (%d)", ability.name, id))
end

-- A tooltip's hit: low end, high end, damage per extra rage point (Execute). English first; in other languages
-- the first number (percentages left out) is the low end and a number right after it the high end.
local function parseHit(desc)
    if type(desc) ~= "string" or isSecret(desc) then return nil end
    local low, high = desc:match("(%d+) to (%d+)")
    if not low then low = desc:match("(%d+) damage") end
    local perRage = desc:match("each extra point of rage into (%d+)")
    if not low then
        local plain = desc:gsub("%d+%s*%%", "")
        low, high = plain:match("(%d+)[^%d]-(%d+)")
        local between = low and plain:match(low .. "([^%d]-)" .. high)
        if not between or #between > 8 then
            low, high = plain:match("(%d+)"), nil
        end
    end
    low = tonumber(low)
    if not low then return nil end
    return low, tonumber(high) or low, tonumber(perRage) or 0
end

local function hitOf(spellID)
    return parseHit(readable("string", C_Spell and C_Spell.GetSpellDescription, spellID))
end

-- Extra rage beyond Execute's cost, or nil when rage can't be read.
local function extraRage(spellID)
    local rage = readable("number", UnitPower, "player", RAGE)
    if not rage then return nil end
    local cost = DEFAULT_RAGE_COST
    local costs = C_Spell and readable("table", C_Spell.GetSpellPowerCost, spellID)
    for _, c in ipairs(costs or {}) do
        if not isSecret(c.type) and c.type == RAGE and not isSecret(c.cost) and type(c.cost) == "number" then
            cost = c.cost
        end
    end
    return math.max(0, rage - cost)
end

local function learnedRatio(spellID)
    local saved = db.execRatios and db.execRatios[spellID]
    return saved and saved.ratio or 1
end

-- The hit to compare with the target's health, and how it was made (for the log), or nil.
local function estimate()
    if not ability then return nil end
    local low, _, perRage = hitOf(ability.spellID)
    if not low then return nil end
    local extra = perRage > 0 and extraRage(ability.spellID) or 0
    local ratio = learnedRatio(ability.spellID)
    local hit = (low + perRage * (extra or 0)) * ratio
    return hit, string.format("%s: %d%s x %.2f learned = %d", ability.name, low,
        perRage > 0 and string.format(" + %d rage x %d", extra or 0, perRage) or "", ratio, hit)
end

---------------------------------------------------------------------------
-- Learning from the damage meter
---------------------------------------------------------------------------

-- This combat: spellID -> { casts, expected (the tooltip's average hit, summed per cast), unclear }
local tally = {}
local rageAtSend = {} -- castGUID -> extra rage when the cast was sent (spent by the time it succeeds)

local function onCastSent(castGUID, spellID)
    if not ability or spellID ~= ability.spellID or not ability.info.rage then return end
    if castGUID and not isSecret(castGUID) then rageAtSend[castGUID] = extraRage(spellID) or false end
end

local function onCastSucceeded(castGUID, spellID)
    if not ability or isSecret(spellID) or spellID ~= ability.spellID then return end
    local low, high, perRage = hitOf(spellID)
    if not low then return end
    local t = tally[spellID] or { casts = 0, expected = 0 }
    tally[spellID] = t
    local extra = 0
    if perRage > 0 then
        extra = castGUID and not isSecret(castGUID) and rageAtSend[castGUID]
        if castGUID and not isSecret(castGUID) then rageAtSend[castGUID] = nil end
        if not extra then t.unclear = true end -- the meter's total has rage in it that wasn't counted
    end
    t.casts = t.casts + 1
    t.expected = t.expected + (low + high) / 2 + perRage * (extra or 0)
end

-- How much crits add to an average hit: 1 + chance x (multiplier - 1). Read out of combat (after it).
local function critFactor(info)
    local chance
    if info.melee then
        chance = readable("number", GetCritChance)
    else
        chance = readable("number", GetSpellCritChance, info.school)
    end
    local multiplier = info.melee and MELEE_CRIT_MULTIPLIER or SPELL_CRIT_MULTIPLIER
    return 1 + math.max(0, math.min(100, chance or 0)) / 100 * (multiplier - 1), chance
end

-- spells: the damage meter's rows for the combat that just ended ({ spellID, totalAmount }); counted: that combat's
-- tally. Returns how many ratios were learned.
local function learn(spells, counted)
    db.execRatios = db.execRatios or {}
    local totals = {}
    for _, sp in ipairs(spells or {}) do
        if not isSecret(sp.spellID) and not isSecret(sp.totalAmount) and type(sp.totalAmount) == "number" then
            totals[sp.spellID] = sp.totalAmount
        end
    end
    local learned = 0
    for spellID, t in pairs(counted) do
        local name = readable("string", C_Spell and C_Spell.GetSpellName, spellID) or tostring(spellID)
        local total = totals[spellID]
        if t.unclear then
            ns.trace(string.format("EXEC LEARN %s skipped: rage wasn't readable at a cast", name))
        elseif not total or total <= 0 then
            ns.trace(string.format("EXEC LEARN %s skipped: no damage meter total (%d cast(s), all missed?)", name,
                t.casts))
        else
            local factor, chance = critFactor(ability and ability.info or {})
            local ratio = total / factor / t.expected
            if ratio < LEARN_RATIO_MIN or ratio > LEARN_RATIO_MAX then
                ns.trace(string.format("EXEC LEARN %s skipped: meter %d over %d cast(s) is %.2fx the tooltip", name,
                    total, t.casts, ratio))
            else
                local old = db.execRatios[spellID]
                local weight = old and math.min(old.weight or 0, LEARN_WEIGHT_CAP) or 0
                local blended = ((old and old.ratio or 0) * weight + ratio * t.casts) / (weight + t.casts)
                db.execRatios[spellID] = { ratio = math.floor(blended * 1000 + 0.5) / 1000, weight = weight + t.casts }
                learned = learned + 1
                ns.trace(string.format("EXEC LEARN %s: meter %d over %d cast(s), crit %s%% (x%.2f) = %.2fx the "
                    .. "tooltip, saved %.3f", name, total, t.casts, chance and string.format("%.1f", chance) or "?",
                    factor, ratio, db.execRatios[spellID].ratio))
            end
        end
    end
    return learned
end

local function learnAfterCombat(counted, triesLeft)
    if InCombatLockdown() then
        ns.trace("EXEC LEARN skipped: a new fight started before the damage meter could be read")
        return
    end
    local spells, why = ns.readDamageMeter()
    if not spells and why == "wait" and triesLeft > 0 then
        C_Timer.After(METER_RETRY_SECONDS, function() learnAfterCombat(counted, triesLeft - 1) end)
        return
    end
    if not spells then
        ns.trace("EXEC LEARN skipped: damage meter " .. (why == "wait" and "still empty or hidden" or tostring(why)))
        return
    end
    learn(spells, counted)
end

---------------------------------------------------------------------------
-- The icon
---------------------------------------------------------------------------

local window = CreateFrame("Frame", "DoesItDieExecute", UIParent)
window:SetClipsChildren(true)
window:SetFrameStrata("HIGH")
window:Hide()

local bar = CreateFrame("StatusBar", nil, window)
bar:SetPoint("RIGHT", window, "RIGHT")
bar:SetStatusBarTexture("Interface\\Buttons\\WHITE8X8")
bar:SetStatusBarColor(0, 0, 0, 0)

local icon = bar:CreateTexture(nil, "OVERLAY")
icon:SetPoint("RIGHT", bar:GetStatusBarTexture(), "RIGHT")

local pulse = icon:CreateAnimationGroup()
pulse:SetLooping("BOUNCE")
do
    local fade = pulse:CreateAnimation("Alpha")
    fade:SetFromAlpha(1)
    fade:SetToAlpha(0.5)
    fade:SetDuration(0.6)
    fade:SetSmoothing("IN_OUT")
end

local testUntil -- /did exec shows it for a few seconds
local lastAnchor, lastSize, lastX, lastY, lastIcon

local function place(anchor)
    local size = db.execSize
    if anchor == lastAnchor and size == lastSize and db.execOffsetX == lastX and db.execOffsetY == lastY
        and ability.icon == lastIcon then
        return
    end
    lastAnchor, lastSize, lastX, lastY, lastIcon = anchor, size, db.execOffsetX, db.execOffsetY, ability.icon
    window:SetSize(size, size)
    bar:SetSize(BAR_LENGTH, size)
    icon:SetSize(size, size)
    icon:SetTexture(ability.icon)
    window:ClearAllPoints()
    window:SetPoint("BOTTOM", anchor, "TOP", db.execOffsetX, db.execOffsetY)
    pulse:Play()
end

local function targetDead()
    local dead = readable("boolean", UnitIsDead, "target")
    return dead == true
end

-- false only when the game plainly says it can't be cast now (Execute above 20%, no rage); unknown counts as usable.
local function usable()
    if not (C_Spell and C_Spell.IsSpellUsable) then return true end
    return readable("boolean", C_Spell.IsSpellUsable, ability.spellID) ~= false
end

local lastTraced
local function update()
    local anchor, visibilityFrame, preview = ns.display.killIconAnchor()
    if not (db.execShow and ability and anchor) then return window:Hide() end
    place(anchor)
    -- Options window preview, and /did exec: always shown, to place and size it.
    if preview or (testUntil and GetTime() < testUntil) then
        bar:SetMinMaxValues(0, 1)
        bar:SetValue(1)
        return window:Show()
    end
    if not UnitExists("target") or targetDead() or readable("boolean", UnitCanAttack, "player", "target") == false then
        return window:Hide()
    end
    if visibilityFrame and readable("boolean", visibilityFrame.IsVisible, visibilityFrame) == false then
        return window:Hide()
    end
    local hit, how = estimate()
    if not hit or not usable() then return window:Hide() end
    if how ~= lastTraced then
        lastTraced = how
        ns.trace("EXEC estimate " .. how)
    end
    local ok = pcall(function()
        bar:SetMinMaxValues(0, UnitHealth("target"))
        bar:SetValue(hit)
    end)
    window:SetShown(ok)
end

local events = CreateFrame("Frame")
events:RegisterEvent("PLAYER_LOGIN")
events:RegisterEvent("SPELLS_CHANGED")
events:RegisterEvent("PLAYER_REGEN_ENABLED")
events:RegisterUnitEvent("UNIT_SPELLCAST_SENT", "player")
events:RegisterUnitEvent("UNIT_SPELLCAST_SUCCEEDED", "player")
events:SetScript("OnEvent", function(self, event, ...)
    db = ns.db
    if not db then return end
    if event == "PLAYER_LOGIN" or event == "SPELLS_CHANGED" then
        updateAbility()
    elseif event == "UNIT_SPELLCAST_SENT" then
        local _, _, castGUID, spellID = ...
        onCastSent(castGUID, spellID)
    elseif event == "UNIT_SPELLCAST_SUCCEEDED" then
        local _, castGUID, spellID = ...
        onCastSucceeded(castGUID, spellID)
    elseif event == "PLAYER_REGEN_ENABLED" then
        local counted = tally
        tally, rageAtSend = {}, {}
        if next(counted) == nil then return end
        C_Timer.After(METER_RETRY_SECONDS, function() learnAfterCombat(counted, METER_TRIES) end)
    end
end)

local sinceUpdate = 0
events:SetScript("OnUpdate", function(self, elapsed)
    sinceUpdate = sinceUpdate + elapsed
    if sinceUpdate < UPDATE_INTERVAL then return end
    sinceUpdate = 0
    db = ns.db
    if not db then return end
    local ok, err = pcall(update)
    if not ok then
        window:Hide()
        if err ~= lastTraced then
            lastTraced = err
            ns.trace("EXEC error: " .. tostring(err))
        end
    end
end)

-- /did exec: what's watched and estimated, and the icon shown for 5 seconds to check where it is.
function ns.executeCommand()
    db = ns.db
    updateAbility()
    if not ability then
        ns.print(T("No execute ability found (Execute, Hammer of Wrath, Shadow Word: Death or Shadowburn)."))
        return
    end
    local hit, how = estimate()
    ns.print(how or string.format(T("%s: its tooltip has no damage number this addon can read."), ability.name))
    if not db.execShow then ns.print(T("The execute icon is switched off (options, Kill icon tab).")) end
    testUntil = GetTime() + 5
    ns.trace("EXEC test: " .. tostring(how))
end

function ns.forgetExecuteLearning()
    if ns.db and ns.db.execRatios then wipe(ns.db.execRatios) end
end

-- For tests.
ns.execute = { parseHit = parseHit, learn = learn, estimate = estimate, updateAbility = updateAbility,
    takeTally = function() local t = tally; tally = {}; return t end }
