FROM python:3.12-slim

WORKDIR /app
COPY server ./server
COPY web ./web

RUN useradd --create-home --uid 10001 studyagent \
    && mkdir -p /app/data \
    && chown -R studyagent:studyagent /app

USER studyagent
ENV STUDY_AGENT_HOST=0.0.0.0 \
    STUDY_AGENT_PORT=8765 \
    STUDY_AGENT_DATA_DIR=/app/data

EXPOSE 8765
VOLUME ["/app/data"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/api/health', timeout=3)"]
CMD ["python", "-m", "server.app", "--host", "0.0.0.0", "--port", "8765"]
