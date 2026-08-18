FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/backend
# frontend is mounted/copied at compose level to /app/frontend
WORKDIR /app/backend

# Каталог контуров трасс: запасная геометрия (R-05) и трассы демо-режима.
# Шаг некритичен — сбой не должен ломать сборку образа.
RUN python scripts/fetch_circuits.py || true

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
