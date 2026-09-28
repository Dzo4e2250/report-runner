FROM python:3.12-slim

ENV TZ=Europe/Ljubljana

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY report_runner.py .
COPY config.example.yaml ./config.yaml
COPY demo/ ./demo/

RUN python demo/make_demo_db.py

# Privzeto: notranji razporejevalec. Konfiguracijo in baze prikljuci kot volume.
CMD ["python", "report_runner.py", "serve"]
