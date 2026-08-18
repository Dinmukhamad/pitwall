.PHONY: install fixture run test up down

install:
	cd backend && pip install -r requirements-dev.txt

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
