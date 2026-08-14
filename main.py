import os
import asyncio
import httpx
from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from auth import check_api_key
from database import (
    init_db, get_account, get_or_create_account,
    list_keys, create_key, delete_key,
)

app = FastAPI(title="Mein Chatbot API Gateway")

KEEP_ALIVE_INTERVAL = 15  # Sekunden


async def _keep_ollama_warm():
    """
    Laeuft dauerhaft im Hintergrund und stupst Ollama alle 15 Sekunden an,
    damit das Modell nicht aus dem Speicher entladen wird (Standard: Ollama
    entlaedt nach 5 Min. Inaktivitaet, was die naechste echte Anfrage verlangsamt).
    """
    ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    ollama_model = os.environ.get("OLLAMA_MODEL", "llama3.2:1b")
    async with httpx.AsyncClient(timeout=30.0) as client:
        while True:
            try:
                await client.post(
                    f"{ollama_url}/api/generate",
                    json={"model": ollama_model, "prompt": "", "keep_alive": "10m"},
                )
            except Exception:
                pass  # Ollama evtl. noch nicht bereit -- naechster Versuch in 15s
            await asyncio.sleep(KEEP_ALIVE_INTERVAL)


@app.on_event("startup")
def startup():
    init_db()
    owner_email = os.environ.get("OWNER_EMAIL")
    if owner_email:
        get_or_create_account(owner_email)
        if not list_keys(owner_email):
            create_key(owner_email, "Owner-Key")
    asyncio.create_task(_keep_ollama_warm())


# --- Schemas ---
class ChatRequest(BaseModel):
    message: str


class LoginRequest(BaseModel):
    email: str


class CreateKeyRequest(BaseModel):
    email: str
    name: str


class DeleteKeyRequest(BaseModel):
    email: str
    api_key: str


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


# --- Account & Key-Verwaltung (keine Limits/Tarife mehr, jeder Key unbegrenzt) ---
@app.post("/account/login")
def login(req: LoginRequest):
    """Meldet einen Nutzer an (legt Account automatisch an, falls neu) und gibt alle bisherigen Keys zurueck."""
    email = req.email.strip().lower()
    acc = get_or_create_account(email)
    keys = list_keys(email)
    return {
        "email": acc["email"],
        "requests_used": acc["requests_used"],
        "keys": [{"name": k["name"], "api_key": k["api_key"]} for k in keys],
    }


@app.post("/account/keys/create")
def create_new_key(req: CreateKeyRequest):
    """Legt einen weiteren, benannten Key fuer einen bestehenden Account an."""
    email = req.email.strip().lower()
    if not get_account(email):
        raise HTTPException(status_code=404, detail="Account nicht gefunden -- zuerst einloggen")
    name = req.name.strip() or "Key"
    key = create_key(email, name)
    return key


@app.post("/account/keys/delete")
def remove_key(req: DeleteKeyRequest):
    """Loescht einen Key eines Accounts."""
    email = req.email.strip().lower()
    ok = delete_key(email, req.api_key)
    if not ok:
        raise HTTPException(status_code=404, detail="Key nicht gefunden")
    return {"deleted": True}


@app.get("/me")
def me(account: dict = Depends(check_api_key)):
    return {"email": account["email"], "requests_used": account["requests_used"]}


@app.post("/chat")
async def chat(req: ChatRequest, account: dict = Depends(check_api_key)):
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
    
