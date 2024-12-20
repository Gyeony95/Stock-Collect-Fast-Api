.PHONY: venv install activate run

venv:
	python3 -m venv venv

install:
	pip install fastapi uvicorn dart-fss python-dotenv jinja2 python-multipart itsdangerous \
		sqlalchemy psycopg2-binary pandas plotly pymysql cryptography
	@if [ "$(shell uname)" = "Darwin" ]; then \
		brew install tmux; \
	elif [ "$(shell uname)" = "Linux" ]; then \
		sudo apt-get update && sudo apt-get install -y tmux; \
	fi

activate:
	. venv/bin/activate

run:
	uvicorn stock_collect:app --reload

# Windows 사용자를 위한 명령어
activate-win:
	.\venv\Scripts\activate 