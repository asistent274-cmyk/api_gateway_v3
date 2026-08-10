import os
import httpx
from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from auth import check_api_key

app = FastAPI(title="Mein Chatbot API Gateway")


# --- Schemas ---
class ChatRequest(BaseModel):
    message: str


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


@app.get("/me")
def me(key: dict = Depends(check_api_key)):
    """Einfacher Check, ob der Key gueltig ist."""
    return {"status": "ok", "note": "Key ist gueltig."}


@app.post("/chat")
async def chat(req: ChatRequest, key: dict = Depends(check_api_key)):
    """
    Nimmt eine Chat-Anfrage entgegen, prueft deinen Key und leitet sie an das
    selbstgehostete Ollama-Modell weiter -- kein externer Anbieter beteiligt.
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
