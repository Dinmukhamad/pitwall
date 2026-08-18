.PHONY: install data circuits run test up down

install:
	cd backend && pip install -r requirements-dev.txt

# Данные для локального запуска: контуры трасс (демо считается на лету)
data: circuits

circuits:
	cd backend && python scripts/fetch_circuits.py

run:
	cd backend && uvicorn app.main:app --reload

test:
	cd backend && pytest -q

up:
	docker compose up --build

down:
	docker compose down
