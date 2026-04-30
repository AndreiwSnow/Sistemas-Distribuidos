import logging
import os
import time
from contextlib import asynccontextmanager
from statistics import mean
from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from data_loader import ZONES, load_dataset

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DATA: Dict = {}
ZONE_AREAS: Dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global DATA, ZONE_AREAS
    csv_path = os.getenv("DATASET_PATH", "/data/open_buildings_rm.csv")
    logger.info("Cargando dataset desde %s ...", csv_path)
    DATA, ZONE_AREAS = load_dataset(csv_path)
    logger.info("Dataset listo. Zonas: %s", {z: len(DATA[z]) for z in DATA})
    yield


app = FastAPI(title="Response Generator", lifespan=lifespan)


class QueryRequest(BaseModel):
    query_type: str          
    zone_id: str             
    confidence_min: float = 0.0
    zone_id_b: str = ""      
    bins: int = 5            


class QueryResponse(BaseModel):
    query_type: str
    zone_id: str
    result: Any
    processing_time_ms: float


def q1_count(zone_id: str, confidence_min: float) -> int:
    return sum(1 for b in DATA[zone_id] if b.confidence >= confidence_min)


def q2_area(zone_id: str, confidence_min: float) -> Dict:
    areas = [b.area for b in DATA[zone_id] if b.confidence >= confidence_min]
    if not areas:
        return {"avg_area": 0, "total_area": 0, "n": 0}
    return {"avg_area": mean(areas), "total_area": sum(areas), "n": len(areas)}


def q3_density(zone_id: str, confidence_min: float) -> float:
    count = q1_count(zone_id, confidence_min)
    return count / ZONE_AREAS[zone_id]


def q4_compare(zone_a: str, zone_b: str, confidence_min: float) -> Dict:
    da = q3_density(zone_a, confidence_min)
    db = q3_density(zone_b, confidence_min)
    return {
        "zone_a": {"id": zone_a, "name": ZONES[zone_a]["name"], "density": da},
        "zone_b": {"id": zone_b, "name": ZONES[zone_b]["name"], "density": db},
        "winner": zone_a if da >= db else zone_b,
    }


def q5_confidence_dist(zone_id: str, bins: int) -> list:
    scores = [b.confidence for b in DATA[zone_id]]
    if not scores:
        return []
    step = 1.0 / bins
    result = []
    for i in range(bins):
        lo = i * step
        hi = (i + 1) * step
        count = sum(1 for s in scores if lo <= s < hi)
        result.append({"bucket": i, "min": round(lo, 4), "max": round(hi, 4), "count": count})
    return result


QUERY_HANDLERS = {
    "Q1": lambda req: q1_count(req.zone_id, req.confidence_min),
    "Q2": lambda req: q2_area(req.zone_id, req.confidence_min),
    "Q3": lambda req: q3_density(req.zone_id, req.confidence_min),
    "Q4": lambda req: q4_compare(req.zone_id, req.zone_id_b, req.confidence_min),
    "Q5": lambda req: q5_confidence_dist(req.zone_id, req.bins),
}

@app.get("/health")
def health():
    return {"status": "ok", "zones_loaded": {z: len(DATA.get(z, [])) for z in ZONES}}


@app.post("/query", response_model=QueryResponse)
def handle_query(req: QueryRequest):
    if req.zone_id not in ZONES:
        raise HTTPException(status_code=400, detail=f"Zona inválida: {req.zone_id}")
    if req.query_type not in QUERY_HANDLERS:
        raise HTTPException(status_code=400, detail=f"Tipo de consulta inválido: {req.query_type}")
    if req.query_type == "Q4" and req.zone_id_b not in ZONES:
        raise HTTPException(status_code=400, detail="Q4 requiere zone_id_b válido")

    t0 = time.perf_counter()
    result = QUERY_HANDLERS[req.query_type](req)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    return QueryResponse(
        query_type=req.query_type,
        zone_id=req.zone_id,
        result=result,
        processing_time_ms=round(elapsed_ms, 3),
    )
