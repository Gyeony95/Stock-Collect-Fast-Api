.PHONY: venv install activate run

venv:
	python3 -m venv venv

install:
	pip install fastapi uvicorn dart-fss apscheduler

activate:
	. venv/bin/activate

run:
	uvicorn test:app --reload

# Windows 사용자를 위한 명령어
activate-win:
	.\venv\Scripts\activate 