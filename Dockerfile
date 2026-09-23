FROM node:20-alpine AS frontend

WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir sqlalchemy psycopg2-binary alembic

COPY --from=frontend /app/frontend/dist ./frontend/dist

COPY . .

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head 2>/dev/null || true; python main.py serve --host 0.0.0.0"]