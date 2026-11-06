FROM python:3.12-alpine

LABEL maintainer="BitChord Community"
LABEL description="BitChord Qobuz Source Addon for High Quality FLAC Streaming"

WORKDIR /app

# Create unprivileged user for security
RUN addgroup -S bitchord && adduser -S bitchord -G bitchord

# Copy application files
COPY server.py ./
COPY qobuz/ ./qobuz/
COPY addon/ ./addon/
COPY static/ ./static/
COPY config.example.json ./config.example.json

# Give write permissions for config persistence if mounted
RUN mkdir -p /app/data && chown -R bitchord:bitchord /app

USER bitchord

EXPOSE 8080

ENV BITCHORD_HOST="0.0.0.0"
ENV BITCHORD_PORT="8080"
ENV BITCHORD_CONFIG="/app/data/config.json"
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["python3", "server.py"]
CMD ["--config", "/app/data/config.json"]
