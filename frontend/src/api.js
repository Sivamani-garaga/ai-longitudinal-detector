const API_BASE = "http://localhost:8000";

export async function addVisit(patientId, payload) {
  const res = await fetch(`${API_BASE}/patients/${encodeURIComponent(patientId)}/visits`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({}));
    throw new Error(error.detail || "Error adding visit");
  }

  return res.json();
}

export async function getPatient(patientId) {
  const res = await fetch(`${API_BASE}/patients/${encodeURIComponent(patientId)}`);
  if (!res.ok) {
    const error = await res.json().catch(() => ({}));
    throw new Error(error.detail || "Error fetching patient");
  }
  return res.json();
}
