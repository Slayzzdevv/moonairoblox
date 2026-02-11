/**
 * Moon AI - Frontend Client (Final)
 * AI-powered Roblox Studio control via chat
 */

let ws = null;
let token = null;
let reconnectAttempts = 0;

// Plugin code template
const PLUGIN_CODE = `--[[
    Moon AI - Roblox Studio Plugin
    Connecte ton Studio au cloud Moon AI
]]

local TOKEN = "TOKEN_PLACEHOLDER"
local SERVER_URL = "SERVER_PLACEHOLDER"

local HttpService = game:GetService("HttpService")
local POLL_URL = SERVER_URL .. "/plugin/poll/" .. TOKEN
local RESPONSE_URL = SERVER_URL .. "/plugin/response/" .. TOKEN
local POLL_INTERVAL = 1.5

-- ═══════════════════════════════════════
-- UI: Toolbar + Widget
-- ═══════════════════════════════════════

local toolbar = plugin:CreateToolbar("Moon AI")
local toggleBtn = toolbar:CreateButton("Moon AI", "Ouvrir Moon AI", "rbxassetid://4458901886")

local widgetInfo = DockWidgetPluginGuiInfo.new(Enum.InitialDockState.Float, true, false, 300, 160, 250, 120)
local widget = plugin:CreateDockWidgetPluginGui("MoonAIWidget", widgetInfo)
widget.Title = "Moon AI 🌙"

toggleBtn.Click:Connect(function() widget.Enabled = not widget.Enabled end)

local main = Instance.new("Frame")
main.Size = UDim2.new(1, 0, 1, 0)
main.BackgroundColor3 = Color3.fromRGB(15, 15, 30)
main.BorderSizePixel = 0
main.Parent = widget

local statusLabel = Instance.new("TextLabel")
statusLabel.Size = UDim2.new(1, -20, 0, 30)
statusLabel.Position = UDim2.new(0, 10, 0, 10)
statusLabel.BackgroundTransparency = 1
statusLabel.TextColor3 = Color3.fromRGB(74, 222, 128)
statusLabel.Font = Enum.Font.GothamBold
statusLabel.TextSize = 14
statusLabel.Text = "🌙 Status: Connecté"
statusLabel.TextXAlignment = Enum.TextXAlignment.Left
statusLabel.Parent = main

local cmdLabel = Instance.new("TextLabel")
cmdLabel.Size = UDim2.new(1, -20, 0, 60)
cmdLabel.Position = UDim2.new(0, 10, 0, 45)
cmdLabel.BackgroundTransparency = 1
cmdLabel.TextColor3 = Color3.fromRGB(200, 200, 220)
cmdLabel.Font = Enum.Font.Gotham
cmdLabel.TextSize = 12
cmdLabel.Text = "En attente de commandes..."
cmdLabel.TextWrapped = true
cmdLabel.TextXAlignment = Enum.TextXAlignment.Left
cmdLabel.TextYAlignment = Enum.TextYAlignment.Top
cmdLabel.Parent = main

local function exec(commandData)
    local code = commandData.data and commandData.data.code
    if not code then return false, "Pas de code" end
    local wrapped = "return (function() " .. code .. " end)()"
    local fn, err = loadstring(wrapped)
    if not fn then fn, err = loadstring(code) end
    if fn then
        local ok, ret = pcall(fn)
        return ok, tostring(ret or "Fait")
    end
    return false, tostring(err)
end

while true do
    pcall(function()
        local response = HttpService:GetAsync(POLL_URL)
        local data = HttpService:JSONDecode(response)
        if data.command and data.command ~= "none" then
            statusLabel.Text = "🌙 Exécution..."
            cmdLabel.Text = data.command
            local ok, res = exec(data)
            HttpService:PostAsync(RESPONSE_URL, 
                HttpService:JSONEncode({command_id=data.command_id, result={success=ok, result=res}}),
                Enum.HttpContentType.ApplicationJson)
            statusLabel.Text = ok and "🌙 Succès !" or "🌙 Erreur"
            cmdLabel.Text = tostring(res):sub(1, 100)
        end
    end)
    wait(POLL_INTERVAL)
end`;

// ─── DOM ───
const loadingScreen = document.getElementById('loading-screen');
const setupModal = document.getElementById('setup-modal');
const app = document.getElementById('app');
const messagesDiv = document.getElementById('messages');
const input = document.getElementById('message-input');
const sendBtn = document.getElementById('send-btn');
const statusDot = document.getElementById('status-dot');
const statusText = document.getElementById('status-text');
const taskList = document.getElementById('task-list');
const tokenDisplay = document.getElementById('token-display');
const copyTokenBtn = document.getElementById('copy-token');

// ─── INIT ───
async function init() {
      // Check if user already has a token
      token = localStorage.getItem('moonai_token');

      if (!token) {
            // First time: get token and show setup
            const res = await fetch('/api/session');
            const data = await res.json();
            token = data.token;
            localStorage.setItem('moonai_token', token);
            showSetup();
      } else {
            // Returning user: verify token still works, or get new one
            try {
                  const res = await fetch(`/api/plugin-status/${token}`);
                  if (!res.ok) throw new Error();
            } catch {
                  const res = await fetch('/api/session');
                  const data = await res.json();
                  token = data.token;
                  localStorage.setItem('moonai_token', token);
            }
            startApp();
      }

      // Hide loading
      setTimeout(() => {
            loadingScreen.classList.add('fade-out');
      }, 1000);
}

function showSetup() {
      setTimeout(() => {
            setupModal.classList.remove('hidden');

            document.getElementById('setup-token').textContent = token;

            document.getElementById('copy-setup-token').addEventListener('click', () => {
                  navigator.clipboard.writeText(token);
                  document.getElementById('copy-setup-token').textContent = '✅ Copié !';
                  setTimeout(() => { document.getElementById('copy-setup-token').textContent = '📋 Copier'; }, 2000);
            });

            document.getElementById('copy-plugin-btn').addEventListener('click', () => {
                  const serverUrl = window.location.origin;
                  const code = PLUGIN_CODE
                        .replace('TOKEN_PLACEHOLDER', token)
                        .replace('SERVER_PLACEHOLDER', serverUrl);
                  navigator.clipboard.writeText(code);
                  document.getElementById('copy-plugin-btn').textContent = '✅ Code copié !';
                  setTimeout(() => { document.getElementById('copy-plugin-btn').textContent = '📥 Copier le code du Plugin'; }, 2000);
            });

            document.getElementById('setup-done-btn').addEventListener('click', () => {
                  setupModal.classList.add('hidden');
                  startApp();
            });
      }, 1200);
}

function startApp() {
      app.classList.remove('hidden');
      tokenDisplay.textContent = token;
      connectWS();
      setInterval(checkPluginStatus, 4000);
}

// ─── WEBSOCKET ───
function connectWS() {
      const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
      ws = new WebSocket(`${protocol}//${location.host}/ws/browser`);

      ws.onopen = () => {
            reconnectAttempts = 0;
            statusText.textContent = 'Serveur connecté';
      };

      ws.onmessage = (event) => {
            handleMessage(JSON.parse(event.data));
      };

      ws.onclose = () => {
            statusDot.classList.remove('connected');
            statusText.textContent = 'Reconnexion...';
            const delay = Math.min(3000 * (reconnectAttempts + 1), 15000);
            reconnectAttempts++;
            setTimeout(connectWS, delay);
      };
}

// ─── HANDLE MESSAGES ───
function handleMessage(data) {
      switch (data.type) {
            case 'system':
                  addMessage(data.message, 'system');
                  break;
            case 'status':
                  if (data.connector_online) {
                        statusDot.classList.add('connected');
                        statusText.textContent = 'Plugin Roblox ✅';
                  } else {
                        statusDot.classList.remove('connected');
                        statusText.textContent = 'Plugin non détecté';
                  }
                  break;
            case 'user_echo':
                  addMessage(data.message, 'user');
                  addTyping();
                  break;
            case 'task':
                  removeTyping();
                  addMessage(data.status, 'task-msg');
                  addTask(data.description || data.status);
                  addTyping();
                  break;
            case 'result':
                  removeTyping();
                  addMessage(data.message || '✅ Terminé !', data.success !== false ? 'success-msg' : 'error-msg');
                  completeLastTask();
                  notify();
                  break;
            case 'error':
                  removeTyping();
                  addMessage(data.message, 'error-msg');
                  break;
            case 'warning':
                  addMessage(data.message, 'warning-msg');
                  break;
      }
}

// ─── SEND ───
function sendMessage() {
      const msg = input.value.trim();
      if (!msg || !ws || ws.readyState !== WebSocket.OPEN) return;
      ws.send(JSON.stringify({ message: msg }));
      input.value = '';
}

// ─── UI ───
function addMessage(text, cls) {
      const div = document.createElement('div');
      div.className = `message ${cls}`;
      div.textContent = text;
      messagesDiv.appendChild(div);
      messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function addTyping() {
      removeTyping();
      const div = document.createElement('div');
      div.className = 'typing-indicator';
      div.id = 'typing';
      div.innerHTML = '<span></span><span></span><span></span>';
      messagesDiv.appendChild(div);
      messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function removeTyping() {
      const el = document.getElementById('typing');
      if (el) el.remove();
}

function addTask(desc) {
      const empty = taskList.querySelector('.task-empty');
      if (empty) empty.remove();
      const div = document.createElement('div');
      div.className = 'task-item';
      div.innerHTML = `<span>🔄</span> ${esc(desc)}`;
      taskList.prepend(div);
}

function completeLastTask() {
      const tasks = taskList.querySelectorAll('.task-item:not(.done)');
      if (tasks.length > 0) {
            tasks[0].classList.add('done');
            tasks[0].innerHTML = tasks[0].innerHTML.replace('🔄', '✅');
      }
}

function notify() {
      const orig = document.title;
      document.title = '✅ Moon AI - Done!';
      setTimeout(() => { document.title = orig; }, 3000);
}

function esc(t) {
      const d = document.createElement('div');
      d.textContent = t;
      return d.innerHTML;
}

async function checkPluginStatus() {
      if (!token) return;
      try {
            const r = await fetch(`/api/plugin-status/${token}`);
            const d = await r.json();
            if (d.connected) {
                  statusDot.classList.add('connected');
                  statusText.textContent = 'Plugin Roblox ✅';
            }
      } catch { }
}

// ─── COPY TOKEN ───
copyTokenBtn.addEventListener('click', () => {
      navigator.clipboard.writeText(token);
      copyTokenBtn.textContent = '✅';
      setTimeout(() => { copyTokenBtn.textContent = '📋'; }, 1500);
});

// ─── CHIPS ───
document.querySelectorAll('.chip').forEach(c => {
      c.addEventListener('click', () => {
            input.value = c.dataset.cmd;
            sendMessage();
      });
});

// ─── EVENTS ───
sendBtn.addEventListener('click', sendMessage);
input.addEventListener('keydown', (e) => { if (e.key === 'Enter') sendMessage(); });

init();
