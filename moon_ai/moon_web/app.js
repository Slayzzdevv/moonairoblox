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
local SERVER = "SERVER_PLACEHOLDER"
local HttpService = game:GetService("HttpService")
local POLL_URL = SERVER .. "/plugin/poll/" .. TOKEN
local RESP_URL = SERVER .. "/plugin/response/" .. TOKEN

local toolbar = plugin:CreateToolbar("Moon AI")
local btn = toolbar:CreateButton("Moon AI", "Toggle Moon AI", "rbxassetid://4458901886")
local active = true
btn.Click:Connect(function() active = not active end)

local function exec(data)
    local code = data.data and data.data.code
    if not code then return false, "No code" end
    local fn, err = loadstring("return (function() " .. code .. " end)()")
    if fn then
        local ok, ret = pcall(fn)
        if ok then return true, tostring(ret or "Done")
        else return false, tostring(ret) end
    else
        local fn2, err2 = loadstring(code)
        if fn2 then
            local ok2, ret2 = pcall(fn2)
            return ok2, ok2 and tostring(ret2 or "Done") or tostring(ret2)
        end
        return false, tostring(err)
    end
end

while true do
    if active then
        pcall(function()
            local r = HttpService:GetAsync(POLL_URL)
            local d = HttpService:JSONDecode(r)
            if d.command and d.command ~= "none" then
                local ok, res = exec(d)
                HttpService:PostAsync(RESP_URL,
                    HttpService:JSONEncode({command_id=d.command_id, result={success=ok, result=res}}),
                    Enum.HttpContentType.ApplicationJson)
            end
        end)
    end
    wait(1.5)
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
