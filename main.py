import os
import httpx
from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.responses import FileResponse
from pydantic import BaseModel

from auth import check_api_key
from database import init_db, get_user_by_email, create_user, set_tier, TIER_LIMITS

app = FastAPI(title="Mein Chatbot API Gateway")


@app.on_event("startup")
def startup():
    init_db()
    owner_email = os.environ.get("OWNER_EMAIL")
    if owner_email and not get_user_by_email(owner_email):
        create_user(owner_email, tier="owner")


# --- Schemas ---
class ChatRequest(BaseModel):
    message: str


class SignupRequest(BaseModel):
    email: str


class SetTierRequest(BaseModel):
    email: str
    tier: str  # "free" | "plus" | "pro"


# --- Ollama-Aufruf (selbstgehostetes Modell, laeuft im selben Render-Dienst) ---
async def _call_ollama(message: str, client: httpx.AsyncClient) -> str:
    ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    ollama_model = os.environ.get("OLLAMA_MODEL", "llama3.2:1b")

    try:
        resp = await client.post(
            f"{ollama_url}/api/chat",
            json={
                "model": ollama_model,
                "messages": [{"role": "user", "content": message}],
                "stream": False,
            },
        )
        resp.raise_for_status()
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="Ollama nicht erreichbar. Laeuft der Ollama-Prozess im Container?",
        )
    data = resp.json()
    return data.get("message", {}).get("content", "")


@app.post("/signup")
def signup(req: SignupRequest):
    """
    Legt einen neuen Nutzer mit Free-Tarif an und gibt seinen API-Key zurueck.
    Ausnahme: die als OWNER_EMAIL hinterlegte Adresse wird beim Serverstart
    automatisch angelegt -- ruft der Owner /signup mit genau dieser E-Mail auf,
    bekommt er stattdessen seinen bereits bestehenden Key zurueck.
    """
    existing = get_user_by_email(req.email)
    if existing:
        owner_email = os.environ.get("OWNER_EMAIL")
        if owner_email and req.email == owner_email and existing["tier"] == "owner":
            return {
                "email": existing["email"],
                "api_key": existing["api_key"],
                "tier": existing["tier"],
                "daily_limit": TIER_LIMITS[existing["tier"]],
            }
        raise HTTPException(status_code=400, detail="E-Mail bereits registriert")
    user = create_user(req.email, tier="free")
    return {
        "email": user["email"],
        "api_key": user["api_key"],
        "tier": user["tier"],
        "daily_limit": TIER_LIMITS[user["tier"]],
    }


@app.post("/admin/set-tier")
def admin_set_tier(req: SetTierRequest, x_admin_key: str = Header(..., alias="X-Admin-Key")):
    """
    Setzt den Tarif eines Nutzers manuell (spaeter durch Stripe-Webhook ersetzbar).
    Geschuetzt durch einen separaten Admin-Key (Umgebungsvariable ADMIN_KEY).
    """
    admin_key = os.environ.get("ADMIN_KEY")
    if not admin_key or x_admin_key != admin_key:
        raise HTTPException(status_code=401, detail="Ungueltiger Admin-Key")
    if not get_user_by_email(req.email):
        raise HTTPException(status_code=404, detail="Nutzer nicht gefunden")
    try:
        set_tier(req.email, req.tier)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"email": req.email, "new_tier": req.tier}


@app.get("/me")
def me(user: dict = Depends(check_api_key)):
    """Zeigt Tarif und verbleibende Anfragen des eigenen Keys."""
    limit = TIER_LIMITS.get(user["tier"])
    return {
        "email": user["email"],
        "tier": user["tier"],
        "requests_used": user["requests_used"],
        "daily_limit": limit,
        "remaining": None if limit is None else max(0, limit - user["requests_used"]),
    }


@app.post("/chat")
async def chat(req: ChatRequest, user: dict = Depends(check_api_key)):
    """
    Nimmt eine Chat-Anfrage entgegen, prueft deinen Key + Tarif-Limit und leitet
    sie an das selbstgehostete Ollama-Modell weiter -- kein externer Anbieter beteiligt.
    """
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            reply = await _call_ollama(req.message, client)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Ollama-Fehler: {e}")

    return {"reply": reply}


# --- Web-UI ---
@app.get("/")
def root():
    return FileResponse("index.html")
    
