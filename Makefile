BACKEND_DIR=backend
FRONTEND_DIR=frontend

.PHONY: backend-install frontend-install install backend dev-frontend dev test build

backend-install:
	python3 -m pip install -r requirements.txt

frontend-install:
	cd $(FRONTEND_DIR) && npm install

install: backend-install frontend-install

backend:
	uvicorn app.main:app --reload --app-dir $(BACKEND_DIR)

dev-frontend:
	cd $(FRONTEND_DIR) && npm run dev

test:
	PYTHONPATH=$(BACKEND_DIR) pytest $(BACKEND_DIR)/app/tests --capture=sys

build:
	cd $(FRONTEND_DIR) && npm run build
