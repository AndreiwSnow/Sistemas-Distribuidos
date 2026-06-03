FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir fastapi uvicorn[standard]
COPY data_loader.py responder.py ./
CMD ["uvicorn", "responder:app", "--host", "0.0.0.0", "--port", "8001"]
