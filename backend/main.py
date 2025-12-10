from datetime import date
from typing import List, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(
    title="AI Longitudinal Patient Trajectory & Diagnosis Drift Detector",
    version="1.0",
    description="MVP backend using enhanced drift detection rules."
)

# Allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==========================================================
# Pydantic MODELS
# ==========================================================

class Visit(BaseModel):
    date: date
    diagnosis: str
    treatment: str
    outcome_score: Optional[float] = None
    notes: Optional[str] = None


class Issue(BaseModel):
    type: str
    message: str
    related_dates: List[date] = []


class PatientTimeline(BaseModel):
    patient_id: str
    visits: List[Visit] = []
    issues: List[Issue] = []


# In-memory store
PATIENT_STORE: Dict[str, List[Visit]] = {}


# ==========================================================
# SEVERITY MAPPING
# ==========================================================

def _severity_from_diagnosis(diagnosis: str) -> Optional[int]:
    d = diagnosis.lower().strip()

    if "diabetes type 3" in d:
        return 4
    if "diabetes type 2" in d:
        return 3
    if "diabetes type 1" in d:
        return 2
    if "prediabetes" in d:
        return 1

    if "advanced diabetic nephropathy" in d:
        return 5
    if "nephropathy" in d:
        return 4

    if "normal" in d:
        return 0

    return None


# ==========================================================
# MAIN ANALYSIS ENGINE
# ==========================================================

def _analyze_timeline(visits: List[Visit]) -> List[Issue]:
    issues = []
    if not visits:
        return issues

    visits_sorted = sorted(visits, key=lambda v: v.date)
    severities = [_severity_from_diagnosis(v.diagnosis) for v in visits_sorted]
    scores = [v.outcome_score for v in visits_sorted]

    # -------------------------------------------------------
    # 1. DIAGNOSIS DRIFT
    # -------------------------------------------------------
    for i in range(1, len(visits_sorted)):
        p, c = visits_sorted[i-1], visits_sorted[i]
        s_prev, s_curr = severities[i-1], severities[i]

        if s_prev is not None and s_curr is not None:
            if s_curr > s_prev:
                issues.append(
                    Issue(
                        type="diagnosis_drift",
                        message=f"Diagnosis worsened: {p.diagnosis} → {c.diagnosis}",
                        related_dates=[p.date, c.date]
                    )
                )
            if s_prev > s_curr:
                issues.append(
                    Issue(
                        type="diagnosis_drift",
                        message=f"Diagnosis improved: {p.diagnosis} → {c.diagnosis}",
                        related_dates=[p.date, c.date]
                    )
                )

    # -------------------------------------------------------
    # 2. MISSED PROGRESSION (dip → spike)
    # -------------------------------------------------------
    for i in range(1, len(visits_sorted) - 1):
        s_prev = severities[i - 1]
        s_mid = severities[i]
        s_next = severities[i + 1]

        if None not in (s_prev, s_mid, s_next):
            if s_prev > s_mid and s_next > s_prev + 1:
                issues.append(
                    Issue(
                        type="diagnosis_drift",
                        message="Possible missed progression: condition improved then worsened sharply.",
                        related_dates=[
                            visits_sorted[i-1].date,
                            visits_sorted[i].date,
                            visits_sorted[i+1].date
                        ]
                    )
                )

    # -------------------------------------------------------
    # 3. OUTCOME DETERIORATION
    # -------------------------------------------------------
    for i in range(1, len(visits_sorted)):
        prev, curr = scores[i-1], scores[i]
        if prev is not None and curr is not None:
            if curr < prev - 1:
                issues.append(
                    Issue(
                        type="outcome_reversal",
                        message=f"Outcome deterioration: {prev} → {curr}.",
                        related_dates=[visits_sorted[i - 1].date, visits_sorted[i].date]
                    )
                )

    # -------------------------------------------------------
    # 4. INVALID OUTCOME SCORE
    # -------------------------------------------------------
    for v in visits_sorted:
        if v.outcome_score is not None:
            if v.outcome_score < 0 or v.outcome_score > 10:
                issues.append(
                    Issue(
                        type="data_error",
                        message=f"Invalid outcome score {v.outcome_score}. Must be 0–10.",
                        related_dates=[v.date]
                    )
                )

    # -------------------------------------------------------
    # 5. TREATMENT CONTRADICTIONS
    # -------------------------------------------------------
    for v, sev in zip(visits_sorted, severities):
        treat = v.treatment.lower().strip()

        if sev is None:
            continue

        # Severe disease but mild treatment
        if sev >= 3 and ("lifestyle" in treat or "diet" in treat) and not any(
            m in treat for m in ["insulin", "metformin", "ace", "arb"]
        ):
            issues.append(
                Issue(
                    type="treatment_contradiction",
                    message=f"Severe diagnosis ({v.diagnosis}) but mild treatment ({v.treatment}).",
                    related_dates=[v.date]
                )
            )

        # High severity but NO treatment
        if sev >= 2 and treat in ["", "none", "no treatment", "stopped medication"]:
            issues.append(
                Issue(
                    type="treatment_contradiction",
                    message=f"No treatment documented for high-severity diagnosis {v.diagnosis}.",
                    related_dates=[v.date]
                )
            )

        # Mild disease but aggressive treatment
        if sev <= 1 and ("insulin" in treat):
            issues.append(
                Issue(
                    type="treatment_contradiction",
                    message=f"Mild diagnosis ({v.diagnosis}) but aggressive treatment ({v.treatment}).",
                    related_dates=[v.date]
                )
            )

    return issues


# ==========================================================
# API ROUTES
# ==========================================================

@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/patients", response_model=List[str])
def list_patients():
    return list(PATIENT_STORE.keys())


@app.get("/patients/{patient_id}", response_model=PatientTimeline)
def get_patient_timeline(patient_id: str):
    visits = PATIENT_STORE.get(patient_id)
    if visits is None:
        raise HTTPException(status_code=404, detail="Patient not found")

    issues = _analyze_timeline(visits)
    return PatientTimeline(
        patient_id=patient_id,
        visits=sorted(visits, key=lambda v: v.date),
        issues=issues,
    )


@app.post("/patients/{patient_id}/visits", response_model=PatientTimeline)
def add_visit(patient_id: str, visit: Visit):
    visits = PATIENT_STORE.setdefault(patient_id, [])
    visits.append(visit)

    issues = _analyze_timeline(visits)
    return PatientTimeline(
        patient_id=patient_id,
        visits=sorted(visits, key=lambda v: v.date),
        issues=issues,
    )


@app.delete("/patients/{patient_id}")
def delete_patient(patient_id: str):
    if patient_id not in PATIENT_STORE:
        raise HTTPException(status_code=404, detail="Patient not found")

    del PATIENT_STORE[patient_id]
    return {"status": "deleted", "patient_id": patient_id}


@app.delete("/reset")
def reset_all():
    PATIENT_STORE.clear()
    return {"status": "reset", "patients": 0}
