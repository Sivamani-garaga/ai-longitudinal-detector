# AI Longitudinal Patient Trajectory & Diagnosis Drift Detector 

This project demonstrates a minimal full-stack implementation:

- **Backend**: FastAPI with in-memory storage and simple rule-based analysis
- **Frontend**: React (Vite) single-page app for entering visits and visualizing flags

## Run backend

```bash
cd backend
python -m venv venv
# activate venv...
pip install -r requirements.txt
uvicorn main:app --reload
```

## Run frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 in your browser.
