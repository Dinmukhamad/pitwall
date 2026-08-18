.PHONY: install data circuits fixture run test up down

install:
	cd backend && pip install -r requirements-dev.txt

# Данные для локального запуска: контуры трасс + демо-сессия
data: circuits fixture

circuits:
	cd backend && python scripts/fetch_circuits.py

fixture:
	cd backend && python scripts/generate_fixture.py

run:
	cd backend && uvicorn app.main:app --reload

test:
	cd backend && pytest -q

up:
	docker compose up --build

down:
	docker compose down
