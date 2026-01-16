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

# Dev tools
## Python codebase
- linter `pylint .`
- tests `pytest tests/`
- code coverage `pytest --cov=. --cov-report=term --cov-config=.coveragerc`

## Javascript codebase
- linter `cd web-server && npx eslint .`
- formatter `cd web-server/static/js && npx prettier --check .`
  - apply `cd web-server/static/js && npx prettier --write .`