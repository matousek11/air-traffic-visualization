.PHONY: test lint test-coverage check

lint:
	pylint .

test:
	PYTHONPATH=.:database-service pytest tests/

test-coverage:
	PYTHONPATH=.:database-service pytest --cov=. --cov-report=term --cov-config=.coveragerc

check: lint test test-coverage

import-nmb2b:
	PYTHONPATH=.:database-service python3 test-data/structure_data/nmb2b/import_script/import_nm_b2b_data.py

manual-dataset-import:
	PYTHONPATH=.:database-service python3 -m dataset_stream.import_script


