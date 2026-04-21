.PHONY: test lint test-coverage check

lint:
	pylint .

test:
	PYTHONPATH=.:database-service pytest tests/

test-coverage:
	PYTHONPATH=.:database-service pytest --cov=. --cov-report=term --cov-config=.coveragerc

check: lint test test-coverage

initial-startup:
	cd database-service && \
	    python3 -m venv .venv && \
	    .venv/bin/pip install -q -r requirements.txt && \
	    DB_USER=atm_user DB_PASS=atm_password DB_HOST=localhost DB_PORT=5432 DB_NAME=atm \
	    .venv/bin/alembic upgrade head
	PYTHONPATH=.:database-service \
	    DB_USER=atm_user DB_PASS=atm_password DB_HOST=localhost DB_PORT=5432 DB_NAME=atm \
	    python3 nm-b2b-structure-data/import_script/import_nm_b2b_data.py

start-flight-sync-script:
	cd database-service && \
	    python3 -m venv .venv && \
	    .venv/bin/pip install -q -r requirements.txt && \
	    DB_USER=atm_user DB_PASS=atm_password DB_HOST=localhost DB_PORT=5432 DB_NAME=atm \
	    RABBITMQ_HOST=localhost RABBITMQ_PORT=5672 RABBITMQ_USER=atm_user RABBITMQ_PASS=atm_password \
	    REDIS_HOST=localhost REDIS_PORT=6379 \
	    PYTHONPATH=..: \
	    .venv/bin/python3 sync_data.py

start-create-mtcd-pairs-script:
	cd database-service && \
	    python3 -m venv .venv && \
	    .venv/bin/pip install -q -r requirements.txt && \
	    DB_USER=atm_user DB_PASS=atm_password DB_HOST=localhost DB_PORT=5432 DB_NAME=atm \
	    RABBITMQ_HOST=localhost RABBITMQ_PORT=5672 RABBITMQ_USER=atm_user RABBITMQ_PASS=atm_password \
	    REDIS_HOST=localhost REDIS_PORT=6379 \
	    PYTHONPATH=..: \
	    .venv/bin/python3 create_mtcd_event_check.py
