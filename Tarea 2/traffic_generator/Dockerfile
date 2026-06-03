FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir httpx numpy kafka-python
COPY queries.py generator.py ./
CMD ["python", "generator.py"]
