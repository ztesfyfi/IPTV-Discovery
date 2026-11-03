FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates curl unzip && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY source.zip /tmp/source.zip
RUN unzip -q /tmp/source.zip -d /app && rm /tmp/source.zip && mkdir -p /data/database /data/imports /data/output && useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /app /data
USER appuser
EXPOSE 18787
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","18787"]
