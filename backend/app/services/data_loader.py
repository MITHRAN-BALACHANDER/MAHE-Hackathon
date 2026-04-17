import json
from functools import lru_cache
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[3]
DATASET_DIR = ROOT_DIR / "datasets"


@lru_cache(maxsize=1)
def load_signal_zones() -> list[dict]:
    with (DATASET_DIR / "bangalore_signal_mock.json").open("r", encoding="utf-8") as file:
        data = json.load(file)
    return data["zones"]


@lru_cache(maxsize=1)
def load_routes_seed() -> list[dict]:
    with (DATASET_DIR / "routes_seed.json").open("r", encoding="utf-8") as file:
        data = json.load(file)
    return data["routes"]


@lru_cache(maxsize=1)
def load_tower_data() -> pd.DataFrame:
    return pd.read_csv(DATASET_DIR / "towers_mock.csv")
