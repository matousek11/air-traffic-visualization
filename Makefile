.PHONY: test lint test-coverage check

lint:
	pylint .

test:
	PYTHONPATH=.:database-service pytest tests/

test-coverage:
	PYTHONPATH=.:database-service pytest --cov=. --cov-report=term --cov-config=.coveragerc

check: lint test test-coverage

manual-dataset-import:
	PYTHONPATH=. python3 -m dataset_stream.import_script


