FROM python:3.11-slim

# Ollama-Binary direkt herunterladen und entpacken (robuster als das offizielle
# install.sh, das in minimalen Docker-Umgebungen oft fehlschlaegt)
RUN apt-get update && apt-get install -y curl ca-certificates tar && \
    curl -fsSL -o /tmp/ollama.tgz https://ollama.com/download/ollama-linux-amd64.tgz && \
    tar -C /usr -xzf /tmp/ollama.tgz && \
    rm /tmp/ollama.tgz && \
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
