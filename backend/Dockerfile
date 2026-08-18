FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/backend
# frontend is mounted/copied at compose level to /app/frontend
WORKDIR /app/backend

# Артефакты данных: каталог трасс (запасная геометрия) и демо-сессия.
# Оба шага не критичны — сбой не должен ломать сборку образа.
RUN python scripts/fetch_circuits.py || true \
 && python scripts/generate_fixture.py || true

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
