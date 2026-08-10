FROM python:3.11-slim

# Ollama installieren
RUN apt-get update && apt-get install -y curl && \
    curl -fsSL https://ollama.com/install.sh | sh && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY web ./web
COPY start.sh .
RUN chmod +x start.sh

# Kleines Modell (ca. 1.3 GB), das im Container mitausgeliefert wird
ENV OLLAMA_MODEL=llama3.2:1b
ENV OLLAMA_HOST=0.0.0.0
EXPOSE 10000

CMD ["./start.sh"]
