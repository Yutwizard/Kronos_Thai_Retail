.PHONY: build build-gpu verify notebook notebook-gpu download

build:
	docker compose build notebook

build-gpu:
	docker compose build notebook-gpu

## Run the offline data layer tests (no network required)
verify:
	docker compose run --rm notebook python verify_data_layer.py

## Launch JupyterLab on CPU (all platforms) → http://localhost:8888
notebook:
	docker compose up notebook

## Launch JupyterLab on GPU (Windows WSL2 / Linux only) → http://localhost:8888
notebook-gpu:
	docker compose up notebook-gpu

## Download the full 51-ticker universe (requires network / Yahoo Finance access)
download:
	docker compose run --rm notebook python -c "\
from kth.data.loader import download_universe; \
from kth.data.universe import get_all_tickers; \
download_universe(get_all_tickers(), period='10y', cache_dir='./data/raw')"
