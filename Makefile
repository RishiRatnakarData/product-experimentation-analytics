.PHONY: install test lint sample full
install:
	python -m pip install -r requirements.txt
test:
	pytest -q
lint:
	ruff check src tests
sample:
	python -m src.pipeline --sample
full:
	python -m src.pipeline --users 20000 --days 180 --seed 42
