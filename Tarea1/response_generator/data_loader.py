import csv
import logging
import os
from dataclasses import dataclass
from typing import Dict, List

logger = logging.getLogger(__name__)

ZONES: Dict[str, Dict[str, float]] = {
    "Z1": {"lat_min": -33.445, "lat_max": -33.420, "lon_min": -70.640, "lon_max": -70.600, "name": "Providencia"},
    "Z2": {"lat_min": -33.420, "lat_max": -33.390, "lon_min": -70.600, "lon_max": -70.550, "name": "Las Condes"},
    "Z3": {"lat_min": -33.530, "lat_max": -33.490, "lon_min": -70.790, "lon_max": -70.740, "name": "Maipú"},
    "Z4": {"lat_min": -33.460, "lat_max": -33.430, "lon_min": -70.670, "lon_max": -70.630, "name": "Santiago Centro"},
    "Z5": {"lat_min": -33.470, "lat_max": -33.430, "lon_min": -70.810, "lon_max": -70.760, "name": "Pudahuel"},
}


@dataclass(slots=True)
class Building:
    latitude: float
    longitude: float
    area: float       
    confidence: float


def _zone_area_km2(zone_id: str) -> float:
    z = ZONES[zone_id]
    import math
    lat_mid = (z["lat_min"] + z["lat_max"]) / 2
    dlat_km = (z["lat_max"] - z["lat_min"]) * 111.0
    dlon_km = (z["lon_max"] - z["lon_min"]) * 111.0 * math.cos(math.radians(lat_mid))
    return abs(dlat_km * dlon_km)


def _belongs_to_zone(lat: float, lon: float, zone_id: str) -> bool:
    z = ZONES[zone_id]
    return z["lat_min"] <= lat <= z["lat_max"] and z["lon_min"] <= lon <= z["lon_max"]


def load_dataset(csv_path: str) -> tuple[Dict[str, List[Building]], Dict[str, float]]:
    """
    Lee el CSV de Open Buildings y devuelve:
      - data:         {zone_id: [Building, ...]}
      - zone_areas:   {zone_id: area_km2}

    El CSV de Google Open Buildings tiene estas columnas relevantes:
      latitude, longitude, area_in_meters, confidence
    Si usas el CSV completo, puede tener otras columnas — las ignoramos.
    """
    if not os.path.exists(csv_path):
        logger.warning(
            "Dataset no encontrado en '%s'. Usando datos sintéticos de ejemplo.", csv_path
        )
        return _synthetic_dataset()

    data: Dict[str, List[Building]] = {z: [] for z in ZONES}
    total_rows = 0
    skipped = 0

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total_rows += 1
            try:
                lat = float(row["latitude"])
                lon = float(row["longitude"])
                area = float(row.get("area_in_meters", 0) or 0)
                conf = float(row.get("confidence", 0) or 0)
            except (ValueError, KeyError):
                skipped += 1
                continue

            for zone_id in ZONES:
                if _belongs_to_zone(lat, lon, zone_id):
                    data[zone_id].append(Building(lat, lon, area, conf))
                    break  

    zone_areas = {z: _zone_area_km2(z) for z in ZONES}

    for zone_id, buildings in data.items():
        logger.info(
            "Zona %s (%s): %d edificios cargados",
            zone_id, ZONES[zone_id]["name"], len(buildings)
        )

    logger.info("Total filas leídas: %d | omitidas: %d", total_rows, skipped)
    return data, zone_areas

def _synthetic_dataset() -> tuple[Dict[str, List[Building]], Dict[str, float]]:
    """
    Genera edificios aleatorios dentro de cada zona para poder
    desarrollar y testear sin el dataset real.
    """
    import random
    rng = random.Random(42)

    COUNTS = {"Z1": 3200, "Z2": 4100, "Z3": 5800, "Z4": 2900, "Z5": 3600}
    data: Dict[str, List[Building]] = {}

    for zone_id, z in ZONES.items():
        buildings = []
        for _ in range(COUNTS[zone_id]):
            lat = rng.uniform(z["lat_min"], z["lat_max"])
            lon = rng.uniform(z["lon_min"], z["lon_max"])
            area = rng.lognormvariate(4.5, 0.8)   
            conf = min(1.0, rng.betavariate(5, 2))
            buildings.append(Building(lat, lon, area, conf))
        data[zone_id] = buildings

    zone_areas = {z: _zone_area_km2(z) for z in ZONES}
    logger.info("Usando dataset sintético (%s edificios totales)", sum(COUNTS.values()))
    return data, zone_areas
