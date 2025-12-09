from datetime import date
from typing import List, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(
    title="AI Longitudinal Patient Trajectory & Diagnosis Drift Detector",
    version="0.1.0",
    description="MVP backend using in-memory storage and rule-based analysis."
)

# Allow local dev frontends (Vite/CRA etc.)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For local development only; tighten for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Visit(BaseModel):
    date: date
    diagnosis: str
    treatment: str
    outcome_score: Optional[float] = None
    notes: Optional[str] = None




from typing import List
from datetime import date
from pydantic import BaseModel, Field

class Issue(BaseModel):
    type: str = Field(..., description="Issue category")
    message: str = Field(..., description="Explanation of issue")
    related_dates: List[date] = Field(default_factory=list, description="Dates relevant to analysis")



class PatientTimeline(BaseModel):
    patient_id: str
    visits: List[Visit] = []
    issues: List[Issue] = []



# ---- In-memory "temporary" storage ----
# This will be reset every time you restart the backend.
PATIENT_STORE: Dict[str, List[Visit]] = {}


def _severity_from_diagnosis(diagnosis: str) -> Optional[int]:
    """
    Very simple rule-based mapping just for the MVP demo.
    You can extend this mapping for your use-case.
    """
    diag = diagnosis.lower()

    # Example: diabetes-related progression
    if "advanced diabetic nephropathy" in diag:
        return 4
    if "nephropathy" in diag:
        return 3
    if "diabetes" in diag or "diabetic" in diag:
        # generic diabetes
        if "pre" in diag:  # "prediabetes"
            return 1
        return 2
    if "prediabetes" in diag:
        return 1
    if "normal" in diag:
        return 0

    # Unknown / not mapped
    return None


def _analyze_timeline(visits: List[Visit]) -> List[Issue]:
    """
    Core rule-based analysis:
    - Diagnosis drift
    - Treatment contradictions
    - Outcome reversals
    """
    issues: List[Issue] = []

    if not visits:
        return issues

    # Ensure visits are sorted by date
    visits_sorted = sorted(visits, key=lambda v: v.date)

    # Precompute severities & scores
    severities = [_severity_from_diagnosis(v.diagnosis) for v in visits_sorted]
    scores = [v.outcome_score for v in visits_sorted]

    # --- Diagnosis drift / missed progression ---
    # 1) Sudden jumps in severity between consecutive visits
    for i in range(1, len(visits_sorted)):
        s_prev, s_curr = severities[i - 1], severities[i]
        if s_prev is not None and s_curr is not None:
            if abs(s_curr - s_prev) >= 2:
                issues.append(
                    Issue(
                        type="diagnosis_drift",
                        message=(
                            f"Sudden diagnosis severity change from {visits_sorted[i-1].diagnosis!r} "
                            f"to {visits_sorted[i].diagnosis!r}. Possible missed progression or mislabeling."
                        ),
                        related_dates=[visits_sorted[i - 1].date, visits_sorted[i].date],
                    )
                )

    # 2) "Dip then spike" pattern like: Prediabetes -> Normal -> Advanced Nephropathy
    for i in range(1, len(visits_sorted) - 1):
        s_prev, s_mid, s_next = severities[i - 1], severities[i], severities[i + 1]
        if None not in (s_prev, s_mid, s_next):
            if s_prev > s_mid and s_next >= s_prev + 1:
                issues.append(
                    Issue(
                        type="diagnosis_drift",
                        message=(
                            "Potential missed progression: diagnosis improved and then worsened sharply. "
                            "Review middle visit for possible misclassification or under-diagnosis."
                        ),
                        related_dates=[
                            visits_sorted[i - 1].date,
                            visits_sorted[i].date,
                            visits_sorted[i + 1].date,
                        ],
                    )
                )

    # --- Treatment contradictions ---
    for v, sev in zip(visits_sorted, severities):
        treat = v.treatment.lower()

        if sev is None:
            continue

        # High severity but very mild treatment
        if sev >= 3 and any(keyword in treat for keyword in ["diet", "lifestyle", "exercise"]) \
                and not any(keyword in treat for keyword in ["insulin", "metformin", "ace inhibitor", "arb"]):
            issues.append(
                Issue(
                    type="treatment_contradiction",
                    message=(
                        f"High-severity diagnosis ({v.diagnosis!r}) but treatment looks mild ({v.treatment!r}). "
                        "Check if escalation of therapy is needed."
                    ),
                    related_dates=[v.date],
                )
            )

        # Moderate / high severity but 'no treatment' documented
        if sev >= 2 and (treat.strip() == "" or "no treatment" in treat or "none" in treat):
            issues.append(
                Issue(
                    type="treatment_contradiction",
                    message=(
                        f"Diagnosis {v.diagnosis!r} has no clear treatment documented. "
                        "Verify if treatment is missing from the record."
                    ),
                    related_dates=[v.date],
                )
            )

        # Low severity but very aggressive treatment (toy rule)
        if sev <= 1 and any(keyword in treat for keyword in ["insulin", "dialysis"]):
            issues.append(
                Issue(
                    type="treatment_contradiction",
                    message=(
                        f"Low-severity diagnosis ({v.diagnosis!r}) with aggressive treatment ({v.treatment!r}). "
                        "Check if diagnosis severity or treatment plan is documented correctly."
                    ),
                    related_dates=[v.date],
                )
            )

    # --- Outcome reversals / prognosis instability ---
    # Look for outcome score getting worse despite "improved/controlled" terms in diagnosis
    for i in range(1, len(visits_sorted)):
        prev_score = scores[i - 1]
        curr_score = scores[i]
        diag_text = visits_sorted[i].diagnosis.lower()

        if prev_score is not None and curr_score is not None:
            # Outcome got worse by a significant margin (arbitrary threshold)
            if curr_score - prev_score >= 1.0 and any(
                kw in diag_text for kw in ["improved", "controlled", "resolved"]
            ):
                issues.append(
                    Issue(
                        type="outcome_reversal",
                        message=(
                            "Outcome score worsened but diagnosis text suggests improvement "
                            f"({visits_sorted[i].diagnosis!r}). Possible label-outcome mismatch."
                        ),
                        related_dates=[visits_sorted[i - 1].date, visits_sorted[i].date],
                    )
                )

    return issues


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
    """
    Clear all in-memory data. Useful during development/demo.
    """
    PATIENT_STORE.clear()
    return {"status": "reset", "patients": 0}
