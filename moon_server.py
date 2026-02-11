"""
Moon AI - Cloud Server with AI API
Users chat on the website → AI generates Lua → Plugin executes in Roblox Studio.
"""

import asyncio
import json
import uuid
import time
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from collections import deque
import aiohttp
from dotenv import load_dotenv

load_dotenv()

# ═══════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════
AI_API_KEY = os.environ.get("AI_API_KEY", "")
AI_API_URL = os.environ.get("AI_API_URL", "https://api.anthropic.com/v1/messages")
AI_MODEL = os.environ.get("AI_MODEL", "claude-3-5-sonnet-20240620")

SYSTEM_PROMPT = """Tu es Moon AI, un assistant expert en Roblox Studio.
Quand un utilisateur demande quelque chose, tu génères UNIQUEMENT du code Lua exécutable dans Roblox Studio.

RÈGLES STRICTES:
1. Réponds TOUJOURS avec un JSON: {"lua": "...code...", "description": "...ce que ça fait..."}
2. Le code Lua doit être complet et prêt à exécuter
3. Utilise Instance.new() pour créer des objets
4. Ancre toujours les parts (Anchored = true) sauf si c'est de la physique
5. workspace est la racine pour les objets visibles
6. Le code doit retourner un string de confirmation avec return "..."
7. Sois créatif et fais des modèles détaillés avec des couleurs et matériaux variés
8. Pour le terrain: workspace.Terrain:FillBlock() ou FillBall()
9. Pour nettoyer: détruire les enfants de workspace sauf Camera et Terrain
10. JAMAIS de texte en dehors du JSON. Juste le JSON brut."""

# ═══════════════════════════════════════
# STATE
# ═══════════════════════════════════════
sessions = {}          # token -> {commands: [], ws: WebSocket|None, ...}
browser_clients = []   # All connected browser WebSockets
task_log = deque(maxlen=30)


@asynccontextmanager
async def lifespan(app):
    asyncio.create_task(cleanup_sessions())
    yield

app = FastAPI(title="Moon AI", lifespan=lifespan)


# ═══════════════════════════════════════
# AI API CALL
# ═══════════════════════════════════════
async def call_ai(user_message: str) -> dict:
    """Call the Anthropic API to generate Lua code from a user message."""
    headers = {
        "x-api-key": AI_API_KEY,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json"
    }
    payload = {
        "model": AI_MODEL,
        "max_tokens": 2048,
        "system": SYSTEM_PROMPT,
        "messages": [
            {"role": "user", "content": user_message}
        ]
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(AI_API_URL, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=40)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    content = data["content"][0]["text"].strip()
                    
                    # Extraction du JSON
                    json_str = content
                    if json_str.startswith("```"):
                        lines = json_str.split("\n")
                        if lines[0].startswith("```"): lines = lines[1:]
                        if lines[-1].startswith("```"): lines = lines[:-1]
                        json_str = "\n".join(lines).strip()
                    
                    try:
                        parsed = json.loads(json_str)
                        return {
                            "success": True,
                            "lua": parsed.get("lua", ""),
                            "description": parsed.get("description", "Commande exécutée")
                        }
                    except:
                        return {
                            "success": True,
                            "lua": content,
                            "description": "Code généré"
                        }
                else:
                    error_text = await resp.text()
                    return {"success": False, "error": f"Claude API Error {resp.status}: {error_text[:200]}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ═══════════════════════════════════════
# PAGES
# ═══════════════════════════════════════

@app.get("/")
async def root():
    return FileResponse("moon_web/index.html")

@app.get("/api/session")
async def create_session():
    """Create a session token for a plugin."""
    token = str(uuid.uuid4())[:8]
    sessions[token] = {
        "commands": [],
        "responses": {},
        "last_seen": time.time(),
        "plugin_connected": False,
    }
    return {"token": token}

@app.get("/api/status")
async def get_status():
    connected_plugins = sum(1 for s in sessions.values() if s["plugin_connected"])
    return {
        "plugins_online": connected_plugins,
        "browsers": len(browser_clients),
        "sessions": len(sessions),
    }

@app.get("/api/plugin-status/{token}")
async def plugin_status(token: str):
    """Check if a specific plugin is connected."""
    if token not in sessions:
        return JSONResponse({"connected": False, "error": "Unknown token"})
    s = sessions[token]
    # Consider plugin connected if last seen within 10 seconds
    connected = s["plugin_connected"] and (time.time() - s["last_seen"]) < 10
    return {"connected": connected}


# ═══════════════════════════════════════
# PLUGIN ENDPOINTS (Roblox HttpService)
# ═══════════════════════════════════════

@app.get("/plugin/poll/{token}")
async def plugin_poll(token: str):
    """Plugin polls for Lua commands to execute."""
    if token not in sessions:
        # Auto-create session if it doesn't exist (e.g. after server restart)
        sessions[token] = {
            "commands": [],
            "responses": {},
            "last_seen": time.time(),
            "plugin_connected": True,
        }
        return JSONResponse({"command": "none", "status": "session_created"})

    sessions[token]["last_seen"] = time.time()
    sessions[token]["plugin_connected"] = True

    cmds = sessions[token]["commands"]
    if cmds:
        cmd = cmds.pop(0)
        return JSONResponse(cmd)
    return JSONResponse({"command": "none"})


@app.post("/plugin/response/{token}")
async def plugin_response(token: str, request: Request):
    """Plugin sends execution results back."""
    if token not in sessions:
        return JSONResponse({"success": False})

    data = await request.json()
    cmd_id = data.get("command_id")
    result = data.get("result", {})

    if cmd_id:
        sessions[token]["responses"][cmd_id] = result

    # Broadcast result to all browsers
    success = result.get("success", False) if isinstance(result, dict) else True
    result_text = result.get("result", str(result)) if isinstance(result, dict) else str(result)

    msg = {
        "type": "result",
        "message": f"✅ {result_text}" if success else f"❌ {result_text}",
        "success": success
    }
    task_log.append(msg)
    await broadcast_to_browsers(msg)

    return JSONResponse({"success": True})


# ═══════════════════════════════════════
# BROWSER WEBSOCKET
# ═══════════════════════════════════════

@app.websocket("/ws/browser")
async def browser_ws(websocket: WebSocket):
    await websocket.accept()
    browser_clients.append(websocket)

    # Welcome
    await websocket.send_json({
        "type": "system",
        "message": "🌙 Bienvenue sur Moon AI ! Tape une commande pour contrôler Roblox Studio."
    })

    # Plugin status
    connected_plugins = sum(1 for s in sessions.values() if s["plugin_connected"])
    await websocket.send_json({
        "type": "status",
        "connector_online": connected_plugins > 0
    })

    # Send recent history
    for entry in task_log:
        try:
            await websocket.send_json(entry)
        except Exception:
            pass

    try:
        while True:
            data = await websocket.receive_json()
            msg = data.get("message", "").strip()
            if not msg:
                continue

            # Check if any plugin is connected
            active_sessions = [t for t, s in sessions.items() if s["plugin_connected"]]
            if not active_sessions:
                await websocket.send_json({
                    "type": "warning",
                    "message": "⚠️ Aucun plugin Roblox connecté. Installe le plugin MoonAI dans Roblox Studio."
                })
                continue

            # Echo message to all browsers
            echo = {"type": "user_echo", "message": msg}
            task_log.append(echo)
            await broadcast_to_browsers(echo)

            # Call AI API to generate Lua
            task_msg = {"type": "task", "status": "🧠 L'IA réfléchit...", "description": msg}
            task_log.append(task_msg)
            await broadcast_to_browsers(task_msg)

            ai_result = await call_ai(msg)

            if not ai_result["success"]:
                err = {"type": "error", "message": f"❌ Erreur IA: {ai_result['error']}"}
                task_log.append(err)
                await broadcast_to_browsers(err)
                continue

            # AI responded with Lua code
            desc_msg = {
                "type": "task",
                "status": f"🔄 {ai_result['description']}",
                "description": ai_result["description"]
            }
            task_log.append(desc_msg)
            await broadcast_to_browsers(desc_msg)

            # Queue command to ALL connected plugins
            cmd_id = f"cmd_{uuid.uuid4().hex[:6]}"
            for token in active_sessions:
                sessions[token]["commands"].append({
                    "command_id": cmd_id,
                    "command": "execute_lua",
                    "data": {"code": ai_result["lua"]}
                })

    except WebSocketDisconnect:
        pass
    finally:
        if websocket in browser_clients:
            browser_clients.remove(websocket)


# ═══════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════

async def broadcast_to_browsers(data: dict):
    dead = []
    for ws in browser_clients:
        try:
            await ws.send_json(data)
        except Exception:
            dead.append(ws)
    for ws in dead:
        browser_clients.remove(ws)

async def cleanup_sessions():
    while True:
        now = time.time()
        stale = [t for t, s in sessions.items() if now - s["last_seen"] > 1800]
        for t in stale:
            del sessions[t]
        await asyncio.sleep(120)


# ═══════════════════════════════════════
# STATIC
# ═══════════════════════════════════════
app.mount("/static", StaticFiles(directory="moon_web"), name="static")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 3000))
    uvicorn.run(app, host="0.0.0.0", port=port)
