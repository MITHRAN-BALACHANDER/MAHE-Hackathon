"""Configuration constants for the connectivity-aware routing model."""

from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
MODEL_DIR = Path(__file__).resolve().parent
DATA_DIR = MODEL_DIR / "data"
WEIGHTS_DIR = MODEL_DIR / "weights"
WEIGHTS_PATH = WEIGHTS_DIR / "best_model.pt"
SCALER_PATH = WEIGHTS_DIR / "scaler.pt"

# ---------------------------------------------------------------------------
# Geography (Bangalore metro area)
# ---------------------------------------------------------------------------
EARTH_RADIUS_KM = 6371.0
LAT_RANGE = (12.78, 13.15)
LNG_RANGE = (77.45, 77.82)
MOBILE_HEIGHT_M = 1.5  # vehicle-mounted antenna

# ---------------------------------------------------------------------------
# Telecom (Indian carriers)
# ---------------------------------------------------------------------------
OPERATORS = ["Jio", "Airtel", "Vi", "BSNL"]
FREQUENCY_BANDS_MHZ = [700, 850, 900, 1800, 2100, 2300, 3500]
TYPICAL_TX_POWER_DBM = 43.0

# ---------------------------------------------------------------------------
# Zone definitions -- 20 Bangalore zones with realistic properties
#   terrain: "highway" | "urban_main" | "suburban" | "residential"
#   environment: maps to propagation model environment parameter
# ---------------------------------------------------------------------------
ZONES = {
    "MG Road":          {"center": (12.9716, 77.5946), "radius_km": 1.5, "density": "high",   "terrain": "urban_main",  "building_height_m": 35},
    "Koramangala":      {"center": (12.9279, 77.6271), "radius_km": 2.0, "density": "high",   "terrain": "urban_main",  "building_height_m": 30},
    "Indiranagar":      {"center": (12.9784, 77.6408), "radius_km": 1.5, "density": "high",   "terrain": "urban_main",  "building_height_m": 28},
    "Jayanagar":        {"center": (12.9250, 77.5840), "radius_km": 1.5, "density": "high",   "terrain": "residential", "building_height_m": 15},
    "Rajajinagar":      {"center": (12.9910, 77.5550), "radius_km": 1.5, "density": "high",   "terrain": "urban_main",  "building_height_m": 25},
    "BTM Layout":       {"center": (12.9166, 77.6101), "radius_km": 1.2, "density": "high",   "terrain": "residential", "building_height_m": 18},
    "HSR Layout":       {"center": (12.9116, 77.6389), "radius_km": 1.2, "density": "high",   "terrain": "residential", "building_height_m": 18},
    "Electronic City":  {"center": (12.8399, 77.6670), "radius_km": 2.5, "density": "medium", "terrain": "suburban",    "building_height_m": 20},
    "Whitefield":       {"center": (12.9698, 77.7499), "radius_km": 2.0, "density": "medium", "terrain": "suburban",    "building_height_m": 22},
    "Marathahalli":     {"center": (12.9591, 77.6974), "radius_km": 1.5, "density": "medium", "terrain": "urban_main",  "building_height_m": 24},
    "Hebbal":           {"center": (13.0358, 77.5970), "radius_km": 1.5, "density": "medium", "terrain": "highway",     "building_height_m": 10},
    "KR Puram":         {"center": (12.9956, 77.6969), "radius_km": 1.5, "density": "low",    "terrain": "urban_main",  "building_height_m": 18},
    "Yelahanka":        {"center": (13.1007, 77.5963), "radius_km": 2.0, "density": "low",    "terrain": "suburban",    "building_height_m": 12},
    "Bannerghatta":     {"center": (12.8010, 77.5775), "radius_km": 2.5, "density": "low",    "terrain": "suburban",    "building_height_m": 10},
    "Hosur Road":       {"center": (12.8700, 77.6400), "radius_km": 1.0, "density": "medium", "terrain": "highway",     "building_height_m": 8},
    "Tumkur Road":      {"center": (13.0500, 77.5500), "radius_km": 1.5, "density": "low",    "terrain": "highway",     "building_height_m": 8},
    "Bellary Road":     {"center": (13.0600, 77.5800), "radius_km": 1.5, "density": "low",    "terrain": "highway",     "building_height_m": 8},
    "Silk Board":       {"center": (12.9172, 77.6225), "radius_km": 0.8, "density": "medium", "terrain": "urban_main",  "building_height_m": 20},
    "Peenya":           {"center": (13.0290, 77.5180), "radius_km": 2.0, "density": "low",    "terrain": "suburban",    "building_height_m": 12},
    "Sarjapur Road":    {"center": (12.9100, 77.6800), "radius_km": 1.5, "density": "medium", "terrain": "suburban",    "building_height_m": 18},
    "Devanahalli":      {"center": (13.2088, 77.7107), "radius_km": 3.0, "density": "low",    "terrain": "suburban",    "building_height_m": 8},
    "Kempegowda Airport": {"center": (13.1979, 77.7063), "radius_km": 2.5, "density": "low",  "terrain": "suburban",    "building_height_m": 10},
    "Bommanahalli":     {"center": (12.8952, 77.6340), "radius_km": 1.2, "density": "medium", "terrain": "residential", "building_height_m": 15},
    "JP Nagar":         {"center": (12.9081, 77.5856), "radius_km": 1.5, "density": "high",   "terrain": "residential", "building_height_m": 18},
    "Banashankari":     {"center": (12.9255, 77.5468), "radius_km": 1.5, "density": "high",   "terrain": "residential", "building_height_m": 16},
}

TERRAIN_CODE = {"highway": 0, "urban_main": 1, "suburban": 2, "residential": 3}
TERRAIN_TO_ENV = {"highway": "suburban", "urban_main": "urban", "suburban": "suburban", "residential": "urban"}

# ---------------------------------------------------------------------------
# Edge-case zones (tunnels, underpasses, urban canyons)
# ---------------------------------------------------------------------------
EDGE_ZONES = [
    {"name": "Hebbal Flyover Underpass",       "center": (13.0350, 77.5965), "radius_km": 0.30, "type": "underpass",    "penalty_db": 25, "structure": "concrete"},
    {"name": "KR Puram Railway Underpass",     "center": (12.9960, 77.6975), "radius_km": 0.20, "type": "underpass",    "penalty_db": 22, "structure": "concrete"},
    {"name": "Silk Board Underpass",           "center": (12.9175, 77.6230), "radius_km": 0.25, "type": "underpass",    "penalty_db": 20, "structure": "concrete"},
    {"name": "Namma Metro Tunnel MG Road",     "center": (12.9750, 77.5960), "radius_km": 0.40, "type": "tunnel",       "penalty_db": 45, "structure": "concrete"},
    {"name": "Namma Metro Tunnel Indiranagar", "center": (12.9784, 77.6408), "radius_km": 0.30, "type": "tunnel",       "penalty_db": 45, "structure": "concrete"},
    {"name": "Namma Metro Tunnel Rajajinagar", "center": (12.9910, 77.5550), "radius_km": 0.35, "type": "tunnel",       "penalty_db": 45, "structure": "concrete"},
    {"name": "Yeshwanthpur Railway Underpass",  "center": (13.0220, 77.5510), "radius_km": 0.20, "type": "underpass",    "penalty_db": 22, "structure": "concrete"},
    {"name": "Mysore Road Flyover Underpass",   "center": (12.9580, 77.5420), "radius_km": 0.25, "type": "underpass",    "penalty_db": 20, "structure": "concrete"},
    {"name": "Commercial Street Canyon",       "center": (12.9815, 77.6080), "radius_km": 0.30, "type": "urban_canyon", "penalty_db": 12, "structure": "dense_urban"},
    {"name": "Chickpet Market Canyon",         "center": (12.9672, 77.5760), "radius_km": 0.25, "type": "urban_canyon", "penalty_db": 10, "structure": "dense_urban"},
    {"name": "Brigade Road Canyon",            "center": (12.9725, 77.6070), "radius_km": 0.20, "type": "urban_canyon", "penalty_db": 11, "structure": "dense_urban"},
    {"name": "Avenue Road Canyon",             "center": (12.9700, 77.5780), "radius_km": 0.20, "type": "urban_canyon", "penalty_db": 10, "structure": "dense_urban"},
]

EDGE_TYPE_TO_TERRAIN = {"tunnel": 4, "underpass": 5, "urban_canyon": 6}

# ---------------------------------------------------------------------------
# Model hyperparameters -- ResidualSignalNet
# ---------------------------------------------------------------------------
INPUT_DIM = 22
HIDDEN_DIM = 256          # projection width
RESIDUAL_BLOCKS = 4       # number of residual blocks
BOTTLENECK_DIM = 64       # final bottleneck before heads
HEAD_HIDDEN = 32          # hidden dim in each output head
DROPOUT = 0.12

# Keep HIDDEN_DIMS for backward compat with inference.py signature
HIDDEN_DIMS = [HIDDEN_DIM, HIDDEN_DIM, BOTTLENECK_DIM]

# Training
LEARNING_RATE = 3e-4
LR = LEARNING_RATE
WEIGHT_DECAY = 1e-5
BATCH_SIZE = 1024
EPOCHS = 300
WARMUP_EPOCHS = 10
TRAIN_SPLIT = 0.70
VAL_SPLIT = 0.15
TEST_SPLIT = 0.15
SEED = 42
GRAD_CLIP = 1.0
LABEL_SMOOTHING = 0.02

# Loss weights (multi-task)
LOSS_WEIGHT_SIGNAL = 1.0
LOSS_WEIGHT_DROP = 0.6
LOSS_WEIGHT_HANDOFF = 0.4

# ---------------------------------------------------------------------------
# Scoring thresholds
# ---------------------------------------------------------------------------
SIGNAL_STRONG = 70
SIGNAL_MEDIUM = 40
SIGNAL_WEAK = 20
BAD_ZONE_THRESHOLD = 30
MAX_ETA_RATIO = 1.5

# ---------------------------------------------------------------------------
# Data generation
# ---------------------------------------------------------------------------
N_TOWERS = 500
N_SAMPLES = 100_000
SAMPLE_SPLIT = {"random": 0.55, "along_roads": 0.20, "edge_zones": 0.15, "sparse": 0.10}
