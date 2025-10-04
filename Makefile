.PHONY: test lint

lint:
	pylint .

test:
	pytest tests/

test-coverage:
	pytest --cov=. --cov-report=term --cov-config=.coveragerc

check: lint test test-coverage


