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
# STATE
# ═══════════════════════════════════════
sessions = {}          # token -> {commands: [], ws: WebSocket|None, ...}
browser_clients = []   # All connected browser WebSockets
task_log = deque(maxlen=30)

# AGENT QUEUE (For "Use Yourself as API" mode)
agent_queue = []       # List of {"id": str, "message": str, "status": "pending"|"processed", "result": dict}
agent_events = {}      # id -> asyncio.Event

@asynccontextmanager
async def lifespan(app):
    asyncio.create_task(cleanup_sessions())
    yield

app = FastAPI(title="Moon AI", lifespan=lifespan)


# ═══════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════
print(f"🚀 Moon AI Starting in AGENT CONTROLLED MODE")
# No AI config needed here - the Agent (IDE) provides the intelligence.

# ═══════════════════════════════════════
# AGENT API (For MCP / IDE)
# ═══════════════════════════════════════

@app.get("/api/agent/pending")
async def get_pending_tasks():
    """Retrieve pending messages for the IDE Agent."""
    pending = [t for t in agent_queue if t["status"] == "pending"]
    return {"tasks": pending}

@app.post("/api/agent/reply/{task_id}")
async def reply_to_task(task_id: str, result: dict):
    """Agent sends the solution (Lua code + Description)."""
    # Find task
    task = next((t for t in agent_queue if t["id"] == task_id), None)
    if not task:
        return JSONResponse({"success": False, "error": "Task not found"})
    
    task["result"] = result
    task["status"] = "processed"
    
    # Notify waiting websocket handler
    if task_id in agent_events:
        agent_events[task_id].set()
        
    return {"success": True}

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
        "message": "🌙 Mode AGENT activé. J'attends que l'IA (Antigravity) traite ton message..."
    })

    # Plugin status
    connected_plugins = sum(1 for s in sessions.values() if s["plugin_connected"])
    await websocket.send_json({
        "type": "status",
        "connector_online": connected_plugins > 0
    })

    try:
        while True:
            data = await websocket.receive_json()
            msg = data.get("message", "").strip()
            if not msg: continue

            # Check plugin
            active_sessions = [t for t, s in sessions.items() if s["plugin_connected"]]
            if not active_sessions:
                await websocket.send_json({"type": "warning", "message": "⚠️ Aucun plugin Roblox connecté."})
                continue

            # Echo user message
            await broadcast_to_browsers({"type": "user_echo", "message": msg})

            # 1. QUEUE THE TASK
            task_id = str(uuid.uuid4())[:8]
            task_entry = {
                "id": task_id,
                "message": msg,
                "status": "pending",
                "result": None
            }
            agent_queue.append(task_entry)
            agent_events[task_id] = asyncio.Event()

            # 2. NOTIFY USER
            await broadcast_to_browsers({
                "type": "task",
                "status": "⏳ En attente de l'Agent Antigravity...",
                "description": "Message transmis à l'IDE. En attente de traitement..."
            })
            
            # 3. WAIT FOR AGENT REPLY
            try:
                # Wait up to 600 seconds (10 mins) for the agent to notice and reply
                await asyncio.wait_for(agent_events[task_id].wait(), timeout=600.0)
                
                # Fetch result
                result = task_entry["result"]
                del agent_events[task_id]
                
                # 4. BROADCAST RESULT
                if not result.get("success", False):
                    err = {"type": "error", "message": f"❌ Erreur Agent: {result.get('error', 'Unknown')}"}
                    task_log.append(err)
                    await broadcast_to_browsers(err)
                    continue

                desc_msg = {
                    "type": "task",
                    "status": f"⚡ {result.get('description', 'Code généré')}",
                    "description": result.get("description", "Code généré")
                }
                task_log.append(desc_msg)
                await broadcast_to_browsers(desc_msg)

                # Queue to Roblox
                lua_code = result.get("lua", "")
                if lua_code:
                    cmd_id = f"cmd_{uuid.uuid4().hex[:6]}"
                    for token in active_sessions:
                        sessions[token]["commands"].append({
                            "command_id": cmd_id,
                            "command": "execute_lua",
                            "data": {"code": lua_code}
                        })
                    await broadcast_to_browsers({
                        "type": "task", 
                        "status": "🚀 Envoi vers Roblox...", 
                        "description": "L'agent a validé le code."
                    })

            except asyncio.TimeoutError:
                await broadcast_to_browsers({"type": "error", "message": "⏱️ L'agent n'a pas répondu à temps."})
                if task_id in agent_events: del agent_events[task_id]
            
            # Clean up queue (simple FIFO cleanup)
            if len(agent_queue) > 50: agent_queue.pop(0)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"Error in websocket: {e}")
    finally:
        if websocket in browser_clients:
            browser_clients.remove(websocket)


# ═══════════════════════════════════════
# PLUGIN ENDPOINTS
# ═══════════════════════════════════════

@app.get("/plugin/poll/{token}")
async def poll_commands_legacy(token: str):
    """Legacy polling for Roblox plugin (GET)."""
    try:
        sessions[token] = sessions.get(token, {"commands": [], "ws": None, "plugin_connected": True, "last_seen": time.time()})
        sessions[token]["last_seen"] = time.time()
        sessions[token]["plugin_connected"] = True
        
        cmds = sessions[token]["commands"]
        if not cmds:
             return {"command": "none"}
             
        # Pop one command (FIFO)
        cmd = cmds.pop(0)
        sessions[token]["commands"] = cmds # Update list
        
        return cmd # Return the command dict directly
        
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})

@app.post("/plugin/response/{token}")
async def plugin_response(token: str, request: Request):
    """Handle response from plugin execution."""
    try:
        data = await request.json()
        # Log or broadcast result if needed
        # For Agent mode, we might want to notify user
        # But currently the loop is: Agent -> Reply -> Queue -> Plugin -> Response
        # We can just log it for now.
        return {"success": True}
    except Exception:
        return {"success": False}

@app.post("/poll")
async def poll_commands(request: Request):
    """Roblox plugin polls for commands (POST version)."""
    try:
        data = await request.json()
        token = data.get("token")
        
        if not token:
            return JSONResponse({"success": False, "error": "No token"})
            
        sessions[token] = sessions.get(token, {"commands": [], "ws": None, "plugin_connected": True, "last_seen": time.time()})
        sessions[token]["last_seen"] = time.time()
        sessions[token]["plugin_connected"] = True
        
        cmds = sessions[token]["commands"]
        sessions[token]["commands"] = [] # Clear queue
        
        return {"commands": cmds}
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})

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
