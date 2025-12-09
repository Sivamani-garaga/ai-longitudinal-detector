import React, { useState } from "react";
import { addVisit, getPatient } from "./api";

function formatDate(dateStr) {
  if (!dateStr) return "";
  try {
    const d = new Date(dateStr);
    return d.toISOString().slice(0, 10);
  } catch {
    return dateStr;
  }
}

export default function App() {
  const [patientId, setPatientId] = useState("");
  const [form, setForm] = useState({
    date: "",
    diagnosis: "",
    treatment: "",
    outcome_score: "",
    notes: ""
  });
  const [timeline, setTimeline] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleAddVisit = async (e) => {
    e.preventDefault();
    setError("");

    if (!patientId.trim()) {
      setError("Please enter a Patient ID.");
      return;
    }
    if (!form.date || !form.diagnosis || !form.treatment) {
      setError("Date, Diagnosis and Treatment are required.");
      return;
    }

    setLoading(true);
    try {
      const payload = {
        date: form.date,
        diagnosis: form.diagnosis,
        treatment: form.treatment,
        notes: form.notes || null
      };

      if (form.outcome_score !== "") {
        payload.outcome_score = parseFloat(form.outcome_score);
      }

      const data = await addVisit(patientId.trim(), payload);
      setTimeline(data);
    } catch (err) {
      setError(err.message || "Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  const handleFetchTimeline = async () => {
    setError("");
    if (!patientId.trim()) {
      setError("Please enter a Patient ID.");
      return;
    }
    setLoading(true);
    try {
      const data = await getPatient(patientId.trim());
      setTimeline(data);
    } catch (err) {
      setTimeline(null);
      setError(err.message || "Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-root">
      <header className="header">
        <h1>Patient Trajectory & Diagnosis Drift Detector (MVP)</h1>
        <p>Track longitudinal diagnoses and flag potential drifts or contradictions.</p>
      </header>

      <main className="main">
        <section className="card">
          <h2>1. Patient & Visit Entry</h2>

          <div className="field-group">
            <label>Patient ID</label>
            <input
              type="text"
              value={patientId}
              onChange={(e) => setPatientId(e.target.value)}
              placeholder="e.g. PAT-001"
            />
          </div>

          <form onSubmit={handleAddVisit} className="grid">
            <div className="field-group">
              <label>Date</label>
              <input
                type="date"
                name="date"
                value={form.date}
                onChange={handleChange}
              />
            </div>

            <div className="field-group">
              <label>Diagnosis</label>
              <input
                type="text"
                name="diagnosis"
                value={form.diagnosis}
                onChange={handleChange}
                placeholder="e.g. Prediabetes"
              />
            </div>

            <div className="field-group">
              <label>Treatment</label>
              <input
                type="text"
                name="treatment"
                value={form.treatment}
                onChange={handleChange}
                placeholder="e.g. Lifestyle modification"
              />
            </div>

            <div className="field-group">
              <label>Outcome Score (optional)</label>
              <input
                type="number"
                step="0.1"
                name="outcome_score"
                value={form.outcome_score}
                onChange={handleChange}
                placeholder="Higher = worse (e.g. A1C)"
              />
            </div>

            <div className="field-group field-notes">
              <label>Notes</label>
              <textarea
                name="notes"
                value={form.notes}
                onChange={handleChange}
                placeholder="Any extra clinical notes..."
                rows={2}
              />
            </div>

            <div className="actions">
              <button type="submit" disabled={loading}>
                {loading ? "Saving..." : "Add Visit & Analyze"}
              </button>
              <button type="button" onClick={handleFetchTimeline} disabled={loading}>
                {loading ? "Loading..." : "Fetch Existing Timeline"}
              </button>
            </div>
          </form>

          {error && <div className="error">{error}</div>}
        </section>

        <section className="card">
          <h2>2. Timeline & Drift Insights</h2>
          {!timeline && <p>No data yet. Add a visit or fetch an existing patient.</p>}

          {timeline && (
            <>
              <h3>Patient: {timeline.patient_id}</h3>
              <div className="timeline-table-wrapper">
                <table className="timeline-table">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Diagnosis</th>
                      <th>Treatment</th>
                      <th>Outcome Score</th>
                      <th>Notes</th>
                    </tr>
                  </thead>
                  <tbody>
                    {timeline.visits.map((v, idx) => (
                      <tr key={idx}>
                        <td>{formatDate(v.date)}</td>
                        <td>{v.diagnosis}</td>
                        <td>{v.treatment}</td>
                        <td>{v.outcome_score ?? "-"}</td>
                        <td>{v.notes || "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="issues">
                <h3>Flagged Issues</h3>
                {timeline.issues.length === 0 && (
                  <p className="ok">No drifts or contradictions detected by the current rules.</p>
                )}
                {timeline.issues.length > 0 && (
                  <ul>
                    {timeline.issues.map((issue, idx) => (
                      <li key={idx} className={`issue issue-${issue.type}`}>
                        <strong>{issue.type.replace("_", " ").toUpperCase()}</strong>
                        <span>{issue.message}</span>
                        {issue.related_dates?.length > 0 && (
                          <small>
                            Dates:{" "}
                            {issue.related_dates.map((d, i) => formatDate(d)).join(", ")}
                          </small>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </>
          )}
        </section>
      </main>

      <footer className="footer">
        <p>Temporary in-memory storage. Data resets when backend restarts.</p>
      </footer>
    </div>
  );
}
