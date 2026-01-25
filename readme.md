# Medium-term Collision Detection heatmap visualization
This software is visualizing places where collision predictions occurs frequently above Europe.


# Installation
- install libraries `pip install -r requirements.txt`

## Web UI server
1. install python libraries `pip install -r requirements.txt`
2. cd `web-server`
3. install node modules `yarn install` 
4. build ts files and bundle node modules `yarn build`
5. run python server `fastapi dev main.py --port 8000`

## Flight simulation backend
1. Run BlueSky simulation with `fastapi dev main.py --port 8001` in `flight-simulation-server` folder

## Install PostgreSQL and TimescaleDB extension

## Workers

## Flight data synchronization
1. `docker compose up -D`
2. `cd database-service`
3. `python3 -m venv venv`
4. `source venv/bin/activate`
5. `python3 -m pip install -r requirements.txt`
6. `alembic upgrade head`
7. `cd ..`
8. `PYTHONPATH=. python3 database-service/sync_data.py`

## Conflict check jobs creation
1. be in root of project
2. `PYTHONPATH=. python3 database-service/create_mtcd_event_check.py`

# Dev tools
## Python codebase
- linter `pylint --rcfile=pylint.rc .`
- tests `pytest tests/`
- code coverage `pytest --cov=. --cov-report=term --cov-config=.coveragerc`

## Javascript codebase
- linter `cd web-server && npx eslint .`
- formatter `cd web-server/static/js && npx prettier --check .`
  - apply `cd web-server/static/js && npx prettier --write .`