.PHONY: setup test api web build docker-up docker-down backup

setup:
	powershell -ExecutionPolicy Bypass -File scripts/setup.ps1

test:
	.\.venv\Scripts\python.exe -m pytest packages\rsagin-core\tests -q

api:
	.\.venv\Scripts\python.exe apps\api\main.py

web:
	pnpm --dir apps\web dev --host 127.0.0.1 --port 5174

build:
	pnpm --dir apps\web build

docker-up:
	docker compose up --build

docker-down:
	docker compose down

backup:
	powershell -ExecutionPolicy Bypass -File scripts/backup_local.ps1
