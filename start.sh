#!/bin/sh
set -e

# Ollama im Hintergrund starten
ollama serve &
OLLAMA_PID=$!

# Warten, bis Ollama bereit ist
until curl -s http://localhost:11434 > /dev/null; do
  echo "Warte auf Ollama..."
  sleep 1
done

# Modell laden (nur beim allerersten Start noetig, danach gecacht -- falls kein
# persistenter Datenspeicher gemountet ist, passiert das bei jedem Neustart)
ollama pull "${OLLAMA_MODEL:-llama3.2:1b}"

# FastAPI-Server starten (Render gibt den Port ueber $PORT vor)
uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-10000}"
