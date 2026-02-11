"""
Moon AI - Local Connector
Runs on YOUR machine. Connects to the Render server, receives messages,
processes them with the AI brain, sends Lua to the MCP bridge, and
streams task progress back to the website.

Usage:
    python moon_connector.py
    (Make sure bridge.py is running first!)
"""

import asyncio
import json
import re
import aiohttp
import websockets

# ═══════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════

# Render server URL (change after deployment)
CLOUD_SERVER = "ws://localhost:3000/ws/connector"  # Local dev
# CLOUD_SERVER = "wss://moonai.onrender.com/ws/connector"  # Production

# Local MCP Bridge
BRIDGE_URL = "http://127.0.0.1:28199/mcp"


# ═══════════════════════════════════════
# AI BRAIN: Parses messages → generates Lua
# ═══════════════════════════════════════

TEMPLATES = {
    "cannon": {
        "keywords": ["cannon", "canon"],
        "description": "Génère un cannon",
        "lua": """
local cannon = Instance.new("Model"); cannon.Name = "Cannon"
local base = Instance.new("Part", cannon); base.Size = Vector3.new(4, 2, 6); base.Position = Vector3.new(0, 1, 0); base.Anchored = true; base.Color = Color3.fromRGB(50,50,50); base.Material = Enum.Material.Metal
local barrel = Instance.new("Part", cannon); barrel.Size = Vector3.new(2, 2, 8); barrel.Position = Vector3.new(0, 3, -4); barrel.Anchored = true; barrel.Color = Color3.fromRGB(30,30,30); barrel.Material = Enum.Material.Metal; barrel.Shape = Enum.PartType.Cylinder; barrel.Orientation = Vector3.new(0, 0, 90)
local w1 = Instance.new("Part", cannon); w1.Size = Vector3.new(1, 3, 3); w1.Position = Vector3.new(3, 1.5, 0); w1.Shape = Enum.PartType.Cylinder; w1.Anchored = true; w1.Color = Color3.fromRGB(80,50,20)
local w2 = w1:Clone(); w2.Position = Vector3.new(-3, 1.5, 0); w2.Parent = cannon
cannon.PrimaryPart = base; cannon.Parent = workspace
return "Cannon créé !"
"""
    },
    "house": {
        "keywords": ["maison", "house", "maisonnette", "cabane"],
        "description": "Génère une maison",
        "lua": """
local house = Instance.new("Model"); house.Name = "House"
local floor = Instance.new("Part", house); floor.Size = Vector3.new(16,1,16); floor.Position = Vector3.new(0,0.5,0); floor.Anchored = true; floor.Color = Color3.fromRGB(139,90,43); floor.Material = Enum.Material.Wood
local w1 = Instance.new("Part", house); w1.Size = Vector3.new(1,10,16); w1.Position = Vector3.new(7.5,6,0); w1.Anchored = true; w1.Color = Color3.fromRGB(200,200,200)
local w2 = w1:Clone(); w2.Position = Vector3.new(-7.5,6,0); w2.Parent = house
local w3 = Instance.new("Part", house); w3.Size = Vector3.new(14,10,1); w3.Position = Vector3.new(0,6,7.5); w3.Anchored = true; w3.Color = Color3.fromRGB(200,200,200)
local w4 = w3:Clone(); w4.Position = Vector3.new(0,6,-7.5); w4.Parent = house
local roof = Instance.new("WedgePart", house); roof.Size = Vector3.new(18,5,9); roof.Position = Vector3.new(0,13.5,4.5); roof.Anchored = true; roof.Color = Color3.fromRGB(150,50,50)
house.PrimaryPart = floor; house.Parent = workspace
return "Maison créée !"
"""
    },
    "npc": {
        "keywords": ["npc", "pnj", "personnage", "guide"],
        "description": "Génère un NPC",
        "lua": """
local npc = Instance.new("Model"); npc.Name = "NPC_Guide"
local torso = Instance.new("Part", npc); torso.Size = Vector3.new(2,2,1); torso.Position = Vector3.new(0,4,0); torso.Color = Color3.fromRGB(0,100,200); torso.Anchored = true
local head = Instance.new("Part", npc); head.Size = Vector3.new(1.2,1.2,1.2); head.Position = Vector3.new(0,5.6,0); head.Color = Color3.fromRGB(255,200,150); head.Anchored = true
local legs = Instance.new("Part", npc); legs.Size = Vector3.new(2,2,1); legs.Position = Vector3.new(0,2,0); legs.Color = Color3.fromRGB(30,30,30); legs.Anchored = true
npc.PrimaryPart = torso; npc.Parent = workspace
return "NPC créé !"
"""
    },
    "terrain": {
        "keywords": ["terrain", "herbe", "grass", "sol", "ground"],
        "description": "Génère du terrain",
        "lua": """
workspace.Terrain:Clear()
workspace.Terrain:FillBlock(CFrame.new(0,-10,0), Vector3.new(200,20,200), Enum.Material.Grass)
workspace.Terrain:FillBlock(CFrame.new(0,-25,0), Vector3.new(200,10,200), Enum.Material.Ground)
return "Terrain généré !"
"""
    },
    "vehicle": {
        "keywords": ["voiture", "vehicle", "car", "véhicule", "buggy"],
        "description": "Génère un véhicule",
        "lua": """
local car = Instance.new("Model"); car.Name = "Vehicle"
local body = Instance.new("Part", car); body.Size = Vector3.new(6,2,10); body.Position = Vector3.new(0,3,0); body.Anchored = true; body.Color = Color3.fromRGB(200,50,50); body.Material = Enum.Material.SmoothPlastic
local cabin = Instance.new("Part", car); cabin.Size = Vector3.new(5,2.5,4); cabin.Position = Vector3.new(0,5,1); cabin.Anchored = true; cabin.Color = Color3.fromRGB(150,200,255); cabin.Transparency = 0.3
for _,pos in ipairs({{-3,1.5,-3},{3,1.5,-3},{-3,1.5,3},{3,1.5,3}}) do
    local w = Instance.new("Part", car); w.Size = Vector3.new(1,3,3); w.Position = Vector3.new(pos[1],pos[2],pos[3]); w.Shape = Enum.PartType.Cylinder; w.Anchored = true; w.Color = Color3.fromRGB(30,30,30)
end
car.PrimaryPart = body; car.Parent = workspace
return "Véhicule créé !"
"""
    },
    "clear": {
        "keywords": ["clear", "nettoie", "supprime", "vide", "efface", "delete", "reset"],
        "description": "Nettoie le workspace",
        "lua": """
for _,c in ipairs(workspace:GetChildren()) do
    if c.Name ~= "Camera" and c.Name ~= "Terrain" then pcall(function() c:Destroy() end) end
end
workspace.Terrain:Clear()
return "Tout nettoyé !"
"""
    },
    "horror": {
        "keywords": ["horror", "horreur", "nuit", "dark", "sombre"],
        "description": "Ambiance horreur",
        "lua": """
local L = game.Lighting; L.Ambient = Color3.fromRGB(10,10,15); L.OutdoorAmbient = Color3.fromRGB(10,10,15)
L.Brightness = 0.2; L.ClockTime = 0; L.FogEnd = 150; L.FogColor = Color3.fromRGB(10,10,10)
return "Ambiance Horreur !"
"""
    },
    "day": {
        "keywords": ["jour", "day", "bright", "lumineux", "soleil"],
        "description": "Ambiance jour",
        "lua": """
local L = game.Lighting; L.Ambient = Color3.fromRGB(140,140,140); L.OutdoorAmbient = Color3.fromRGB(140,140,140)
L.Brightness = 2; L.ClockTime = 14; L.FogEnd = 100000
return "Ambiance Jour !"
"""
    },
    "tree": {
        "keywords": ["arbre", "tree", "forêt", "forest"],
        "description": "Génère un arbre",
        "lua": """
local tree = Instance.new("Model"); tree.Name = "Tree"
local trunk = Instance.new("Part", tree); trunk.Size = Vector3.new(2,8,2); trunk.Position = Vector3.new(0,4,0); trunk.Anchored = true; trunk.Color = Color3.fromRGB(100,60,20); trunk.Material = Enum.Material.Wood
local leaves = Instance.new("Part", tree); leaves.Size = Vector3.new(8,8,8); leaves.Position = Vector3.new(0,11,0); leaves.Shape = Enum.PartType.Ball; leaves.Anchored = true; leaves.Color = Color3.fromRGB(50,150,50); leaves.Material = Enum.Material.Grass
tree.PrimaryPart = trunk; tree.Parent = workspace
return "Arbre créé !"
"""
    },
    "tower": {
        "keywords": ["tour", "tower", "château", "castle"],
        "description": "Génère une tour",
        "lua": """
local tower = Instance.new("Model"); tower.Name = "Tower"
for i = 0, 8 do
    local b = Instance.new("Part", tower); b.Size = Vector3.new(8-i*0.3, 4, 8-i*0.3); b.Position = Vector3.new(0, 2+i*4, 0); b.Anchored = true; b.Color = Color3.fromRGB(150+i*10, 150+i*5, 140); b.Material = Enum.Material.Cobblestone
end
tower.PrimaryPart = tower:GetChildren()[1]; tower.Parent = workspace
return "Tour construite !"
"""
    },
    "part": {
        "keywords": ["part", "bloc", "block", "cube", "brique"],
        "description": "Crée un bloc",
        "lua": """
local p = Instance.new("Part"); p.Size = Vector3.new(4,4,4); p.Position = Vector3.new(0,4,0); p.Anchored = true; p.Color = Color3.fromRGB(math.random(50,255), math.random(50,255), math.random(50,255)); p.Parent = workspace
return "Bloc créé !"
"""
    },
    "spawn": {
        "keywords": ["spawn", "spawnpoint"],
        "description": "Ajoute un spawn",
        "lua": """
local sp = Instance.new("SpawnLocation"); sp.Size = Vector3.new(8,1,8); sp.Position = Vector3.new(0,1,0); sp.Anchored = true; sp.Parent = workspace
return "SpawnLocation ajouté !"
"""
    },
}


def parse_message(message: str) -> dict:
    """Parse a user message and find matching template."""
    msg = message.lower().strip()

    best_match = None
    best_score = 0
    for key, tmpl in TEMPLATES.items():
        for kw in tmpl["keywords"]:
            if kw in msg:
                score = len(kw)
                if score > best_score:
                    best_score = score
                    best_match = tmpl

    if best_match:
        return {
            "matched": True,
            "description": best_match["description"],
            "lua": best_match["lua"].strip()
        }

    # Fallback: create a Part with the name
    safe_name = re.sub(r'[^a-zA-Z0-9_ ]', '', message)[:30]
    return {
        "matched": False,
        "description": f"Création custom: {safe_name}",
        "lua": f'local p = Instance.new("Part"); p.Name = "{safe_name}"; p.Size = Vector3.new(4,4,4); p.Position = Vector3.new(0,4,0); p.Anchored = true; p.Color = Color3.fromRGB(math.random(50,255),math.random(50,255),math.random(50,255)); p.Parent = workspace; return "Objet \'{safe_name}\' créé !"'
    }


async def send_to_bridge(lua_code: str) -> dict:
    """Send Lua code to the MCP bridge for execution in Roblox Studio."""
    payload = {
        "command": "execute_lua",
        "data": {"code": lua_code}
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(BRIDGE_URL, json=payload, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    return {"success": False, "error": f"HTTP {resp.status}"}
    except Exception as e:
        return {"success": False, "error": f"Bridge non disponible: {str(e)}"}


async def process_message(ws, message: str):
    """Process a user message: parse → execute → report back."""

    # 1. Parse
    parsed = parse_message(message)

    # 2. Send task update
    await ws.send(json.dumps({
        "type": "task",
        "status": f"🔄 {parsed['description']}...",
        "description": parsed["description"]
    }))

    # 3. Execute via bridge
    result = await send_to_bridge(parsed["lua"])

    # 4. Report result
    if result.get("success", False):
        result_text = result.get("result", "Terminé !")
        await ws.send(json.dumps({
            "type": "result",
            "message": f"✅ {result_text}",
            "success": True
        }))
    else:
        error_text = result.get("error", "Erreur inconnue")
        await ws.send(json.dumps({
            "type": "error",
            "message": f"❌ {error_text}"
        }))


# ═══════════════════════════════════════
# MAIN LOOP
# ═══════════════════════════════════════

async def main():
    print("""
╔══════════════════════════════════════╗
║       🌙 Moon AI - Connector        ║
╠══════════════════════════════════════╣
║  Connecting to cloud server...      ║
╚══════════════════════════════════════╝
""")

    while True:
        try:
            async with websockets.connect(CLOUD_SERVER) as ws:
                print(f"✅ Connecté au serveur: {CLOUD_SERVER}")
                print("📡 En attente de messages des utilisateurs...\n")

                async for raw in ws:
                    data = json.loads(raw)
                    msg_type = data.get("type", "")

                    if msg_type == "ping":
                        await ws.send(json.dumps({"type": "pong"}))

                    elif msg_type == "user_message":
                        user_msg = data.get("message", "")
                        print(f"💬 Message reçu: {user_msg}")
                        await process_message(ws, user_msg)

        except (ConnectionRefusedError, OSError) as e:
            print(f"⚠️ Impossible de se connecter: {e}")
            print("   Réessai dans 5 secondes...")
            await asyncio.sleep(5)
        except websockets.exceptions.ConnectionClosed:
            print("🔌 Connexion perdue. Reconnexion dans 3 secondes...")
            await asyncio.sleep(3)
        except Exception as e:
            print(f"❌ Erreur: {e}")
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
