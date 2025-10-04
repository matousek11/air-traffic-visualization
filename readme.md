# Medium-term Collision Detection heatmap visualization
This software is visualizing places where collision predictions occurs frequently above Europe.


# Installation
- install libraries `pip install -r requirements.txt`

## Web UI server
1. install python libraries `pip install -r requirements.txt`
2. cd `web-server`
3. install node modules `yarn install` 
4. build ts files and bundle node modules `yarn build`
5. run python server `fastapi dev main.py`

## Flight simulation backend
1. Run BlueSky simulation with `fastapi dev main.py` in `flight-simulation-server` folder

## Install PostgreSQL and TimescaleDB extension

## Workers

# Dev tools
- linter `pylint .`
- tests `pytest tests/`
- code coverage `pytest --cov=. --cov-report=term --cov-config=.coveragerc`
