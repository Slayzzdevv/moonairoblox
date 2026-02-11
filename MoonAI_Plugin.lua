--[[
    ╔══════════════════════════════════════════════╗
    ║          Moon AI - Roblox Studio Plugin       ║
    ║  Connects your Studio to the Moon AI cloud    ║
    ╚══════════════════════════════════════════════╝
    
    INSTRUCTIONS:
    1. Copy this entire file
    2. In Roblox Studio: View → Script Editor
    3. File → New → Plugin (choose "Plugin" not Script)
    4. Paste this code
    5. Change YOUR_TOKEN below to your token from moonai.onrender.com
    6. Save & Activate the plugin
    
    The plugin will automatically poll the server for commands.
]]

-- ═══════════════════════════════════════
-- CONFIGURATION
-- ═══════════════════════════════════════
local TOKEN = "YOUR_TOKEN" -- ← Replace with your Moon AI token
local SERVER_URL = "https://moonai.onrender.com"

-- ═══════════════════════════════════════
-- DO NOT MODIFY BELOW THIS LINE
-- ═══════════════════════════════════════

local HttpService = game:GetService("HttpService")

local POLL_URL = SERVER_URL .. "/plugin/poll/" .. TOKEN
local RESPONSE_URL = SERVER_URL .. "/plugin/response/" .. TOKEN
local POLL_INTERVAL = 1.5

-- ═══════════════════════════════════════
-- UI: Toolbar + Widget
-- ═══════════════════════════════════════

local toolbar = plugin:CreateToolbar("Moon AI")
local toggleBtn = toolbar:CreateButton(
    "Moon AI",
    "Ouvrir/Fermer Moon AI",
    "rbxassetid://4458901886"
)

-- Widget (Enabled = true so it shows on first install!)
local widgetInfo = DockWidgetPluginGuiInfo.new(
    Enum.InitialDockState.Float,  -- Float so it's always visible
    true,   -- ← ENABLED by default (this was false before!)
    false,  -- Override previous state
    320,    -- Default width
    180,    -- Default height
    250,    -- Min width
    120     -- Min height
)

local widget = plugin:CreateDockWidgetPluginGui("MoonAIWidget", widgetInfo)
widget.Title = "Moon AI"

-- Toggle widget visibility from toolbar button
toggleBtn.Click:Connect(function()
    widget.Enabled = not widget.Enabled
end)

-- ═══════════════════════════════════════
-- UI: Build the widget content
-- ═══════════════════════════════════════

-- Main frame
local mainFrame = Instance.new("Frame")
mainFrame.Size = UDim2.new(1, 0, 1, 0)
mainFrame.BackgroundColor3 = Color3.fromRGB(15, 15, 30)
mainFrame.BorderSizePixel = 0
mainFrame.Parent = widget

-- Title bar
local titleBar = Instance.new("Frame")
titleBar.Size = UDim2.new(1, 0, 0, 36)
titleBar.BackgroundColor3 = Color3.fromRGB(20, 20, 45)
titleBar.BorderSizePixel = 0
titleBar.Parent = mainFrame

local titleLabel = Instance.new("TextLabel")
titleLabel.Size = UDim2.new(1, -16, 1, 0)
titleLabel.Position = UDim2.new(0, 12, 0, 0)
titleLabel.BackgroundTransparency = 1
titleLabel.TextColor3 = Color3.fromRGB(124, 92, 252)
titleLabel.Font = Enum.Font.GothamBold
titleLabel.TextSize = 16
titleLabel.Text = "Moon AI"
titleLabel.TextXAlignment = Enum.TextXAlignment.Left
titleLabel.Parent = titleBar

-- Status indicator
local statusFrame = Instance.new("Frame")
statusFrame.Size = UDim2.new(1, -24, 0, 40)
statusFrame.Position = UDim2.new(0, 12, 0, 46)
statusFrame.BackgroundColor3 = Color3.fromRGB(25, 25, 50)
statusFrame.BorderSizePixel = 0
statusFrame.Parent = mainFrame

local statusCorner = Instance.new("UICorner")
statusCorner.CornerRadius = UDim.new(0, 8)
statusCorner.Parent = statusFrame

local statusDot = Instance.new("Frame")
statusDot.Size = UDim2.new(0, 10, 0, 10)
statusDot.Position = UDim2.new(0, 10, 0.5, -5)
statusDot.BackgroundColor3 = Color3.fromRGB(74, 222, 128)
statusDot.BorderSizePixel = 0
statusDot.Parent = statusFrame

local dotCorner = Instance.new("UICorner")
dotCorner.CornerRadius = UDim.new(1, 0)
dotCorner.Parent = statusDot

local statusLabel = Instance.new("TextLabel")
statusLabel.Size = UDim2.new(1, -35, 1, 0)
statusLabel.Position = UDim2.new(0, 28, 0, 0)
statusLabel.BackgroundTransparency = 1
statusLabel.TextColor3 = Color3.fromRGB(200, 200, 220)
statusLabel.Font = Enum.Font.Gotham
statusLabel.TextSize = 13
statusLabel.Text = "Connexion..."
statusLabel.TextXAlignment = Enum.TextXAlignment.Left
statusLabel.TextTruncate = Enum.TextTruncate.AtEnd
statusLabel.Parent = statusFrame

-- Last command display
local cmdFrame = Instance.new("Frame")
cmdFrame.Size = UDim2.new(1, -24, 0, 50)
cmdFrame.Position = UDim2.new(0, 12, 0, 96)
cmdFrame.BackgroundColor3 = Color3.fromRGB(25, 25, 50)
cmdFrame.BorderSizePixel = 0
cmdFrame.Parent = mainFrame

local cmdCorner = Instance.new("UICorner")
cmdCorner.CornerRadius = UDim.new(0, 8)
cmdCorner.Parent = cmdFrame

local cmdTitle = Instance.new("TextLabel")
cmdTitle.Size = UDim2.new(1, -16, 0, 18)
cmdTitle.Position = UDim2.new(0, 10, 0, 4)
cmdTitle.BackgroundTransparency = 1
cmdTitle.TextColor3 = Color3.fromRGB(100, 100, 140)
cmdTitle.Font = Enum.Font.Gotham
cmdTitle.TextSize = 10
cmdTitle.Text = "DERNIERE COMMANDE"
cmdTitle.TextXAlignment = Enum.TextXAlignment.Left
cmdTitle.Parent = cmdFrame

local cmdLabel = Instance.new("TextLabel")
cmdLabel.Size = UDim2.new(1, -16, 0, 22)
cmdLabel.Position = UDim2.new(0, 10, 0, 24)
cmdLabel.BackgroundTransparency = 1
cmdLabel.TextColor3 = Color3.fromRGB(200, 200, 220)
cmdLabel.Font = Enum.Font.GothamMedium
cmdLabel.TextSize = 12
cmdLabel.Text = "Aucune"
cmdLabel.TextXAlignment = Enum.TextXAlignment.Left
cmdLabel.TextTruncate = Enum.TextTruncate.AtEnd
cmdLabel.Parent = cmdFrame

-- Token display at bottom
local tokenLabel = Instance.new("TextLabel")
tokenLabel.Size = UDim2.new(1, -24, 0, 20)
tokenLabel.Position = UDim2.new(0, 12, 1, -28)
tokenLabel.BackgroundTransparency = 1
tokenLabel.TextColor3 = Color3.fromRGB(80, 80, 110)
tokenLabel.Font = Enum.Font.GothamMedium
tokenLabel.TextSize = 10
tokenLabel.Text = "Token: " .. TOKEN:sub(1, 4) .. "..."
tokenLabel.TextXAlignment = Enum.TextXAlignment.Left
tokenLabel.Parent = mainFrame


-- ═══════════════════════════════════════
-- COMMAND EXECUTION
-- ═══════════════════════════════════════

local isActive = true
local commandCount = 0

local function setStatus(text, color)
    statusLabel.Text = text
    statusDot.BackgroundColor3 = color
end

local function executeCommand(commandData)
    local command = commandData.command
    local data = commandData.data or {}
    local commandId = commandData.command_id

    local success, result = false, "Unknown command"

    if command == "execute_lua" then
        local code = data.code
        if code then
            local wrappedCode = "return (function() " .. code .. " end)()"
            local fn, compileErr = loadstring(wrappedCode)
            if fn then
                local ok, ret = pcall(fn)
                if ok then
                    success = true
                    result = tostring(ret or "Done")
                else
                    success = false
                    result = "Runtime error: " .. tostring(ret)
                end
            else
                local fn2, err2 = loadstring(code)
                if fn2 then
                    local ok2, ret2 = pcall(fn2)
                    success = ok2
                    result = ok2 and tostring(ret2 or "Done") or ("Runtime: " .. tostring(ret2))
                else
                    success = false
                    result = "Compile error: " .. tostring(compileErr)
                end
            end
        end
    else
        result = "Unknown command: " .. tostring(command)
    end

    -- Send response back
    local responsePayload = HttpService:JSONEncode({
        command_id = commandId,
        result = {
            success = success,
            result = result
        }
    })

    pcall(function()
        HttpService:PostAsync(RESPONSE_URL, responsePayload, Enum.HttpContentType.ApplicationJson)
    end)

    return success, result
end


-- ═══════════════════════════════════════
-- POLLING LOOP
-- ═══════════════════════════════════════

local function poll()
    if not isActive then return end

    local ok, response = pcall(function()
        return HttpService:GetAsync(POLL_URL)
    end)

    if ok and response then
        local data = HttpService:JSONDecode(response)

        if data.command and data.command ~= "none" then
            commandCount = commandCount + 1
            setStatus("Execution...", Color3.fromRGB(251, 191, 36))
            cmdLabel.Text = tostring(data.command)

            local success, result = executeCommand(data)

            if success then
                setStatus("OK: " .. tostring(result):sub(1, 30), Color3.fromRGB(74, 222, 128))
                cmdLabel.Text = "✅ " .. tostring(result):sub(1, 35)
            else
                setStatus("Erreur", Color3.fromRGB(248, 113, 113))
                cmdLabel.Text = "❌ " .. tostring(result):sub(1, 35)
            end
        end
    end
end

-- Start
setStatus("Actif (" .. commandCount .. " cmds)", Color3.fromRGB(74, 222, 128))

while true do
    poll()
    wait(POLL_INTERVAL)
end
