.PHONY: help install run dev up down logs test test-unit test-contract lint clean

help:
	@echo "Targets:"
	@echo "  install        - cria venv e instala dependências"
	@echo "  dev            - roda uvicorn com --reload (.venv necessário)"
	@echo "  up             - docker compose up -d --build"
	@echo "  down           - docker compose down"
	@echo "  logs           - docker compose logs -f api"
	@echo "  test           - unit tests + contract script"
	@echo "  test-unit      - pytest"
	@echo "  test-contract  - bash scripts/test_contract.sh"
	@echo "  clean          - remove caches"

install:
	python3 -m venv .venv
	./.venv/bin/pip install --upgrade pip
	./.venv/bin/pip install -r requirements.txt

dev:
	./.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f api

test: test-unit test-contract

test-unit:
	./.venv/bin/pytest -q

test-contract:
	./scripts/test_contract.sh

clean:
	rm -rf .pytest_cache __pycache__ */__pycache__ */*/__pycache__ */*/*/__pycache__
