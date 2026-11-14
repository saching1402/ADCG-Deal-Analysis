# Mindari / Deal Analysis — single Railway service: React frontend built into the Django backend.
# Connect the repo on the Railway canvas; no Root Directory needed.

# ── Stage 1: build the React app ──────────────────────────────────────────────
FROM node:20-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
ARG VITE_API_URL=
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# ── Stage 2: Django API + the built app ───────────────────────────────────────
FROM python:3.11-slim-bookworm
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DJANGO_SETTINGS_MODULE=mindari.settings.production
WORKDIR /app

# File reading: poppler (render PDF pages to images for scans / broken text layers) and LibreOffice
# (PowerPoint/Word/legacy Office → PDF, Excel recalculation). Fonts keep converted layouts faithful.
RUN apt-get update \
    && apt-get install -y --no-install-recommends poppler-utils fonts-dejavu-core fonts-liberation2 \
        fonts-crosextra-carlito fonts-crosextra-caladea \
    && (apt-get install -y --no-install-recommends libreoffice-writer-nogui libreoffice-calc-nogui libreoffice-impress-nogui \
        || apt-get install -y --no-install-recommends libreoffice-writer libreoffice-calc libreoffice-impress) \
    && soffice --version && pdftoppm -v \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./
COPY --from=web /web/dist ./frontend_dist
RUN python manage.py collectstatic --noinput

# Runs as root so a Railway Volume mounted at /data is writable without extra setup.
EXPOSE 8000
CMD ["sh", "/app/start.sh"]
