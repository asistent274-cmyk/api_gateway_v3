FROM python:3.11-slim

# Ollama-Binary direkt herunterladen und entpacken (robuster als das offizielle
# install.sh, das in minimalen Docker-Umgebungen oft fehlschlaegt).
# Ollama liefert das Paket aktuell als .tar.zst aus, daher wird zstd zum Entpacken benoetigt.
RUN apt-get update && apt-get install -y curl ca-certificates zstd tar && \
    curl -fsSL -o /tmp/ollama.tar.zst https://ollama.com/download/ollama-linux-amd64.tar.zst && \
    tar --zstd -C /usr -xf /tmp/ollama.tar.zst && \
    rm /tmp/ollama.tar.zst && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py main.py
COPY auth.py auth.py
COPY index.html index.html
COPY start.sh start.sh
RUN chmod +x start.sh

# Kleines Modell (ca. 1.3 GB), das im Container mitausgeliefert wird
ENV OLLAMA_MODEL=llama3.2:1b
ENV OLLAMA_HOST=0.0.0.0
EXPOSE 10000

CMD ["./start.sh"]
