# RoadWatch AI

RoadWatch AI is currently a Streamlit application backed by SQLite, with road-image analysis in Python.

## Project structure

```text
RoadWatch-AI/
├── frontend/
│   ├── src/
│   └── public/
├── backend/
│   ├── app.py
│   ├── ai.py
│   ├── db.py
│   ├── seed.py
│   ├── test_flow.py
│   └── requirements.txt
├── ai-model/
│   └── README.md
├── uploads/
├── reports.db
├── .streamlit/
├── Procfile
├── render.yaml
└── README.md
```

The existing Streamlit interface is in `backend/app.py`; `frontend/src/` and `frontend/public/` are reserved for a separate frontend and do not contain a React app yet. `backend/ai.py` handles inference; `ai-model/` is reserved for training notebooks and related assets.

The SQLite database and uploaded images remain at the project root so existing report and image paths continue to work.

## Run locally

From the project root, install the backend dependencies and start Streamlit:

```bash
pip install -r backend/requirements.txt
streamlit run backend/app.py
```

To run the existing end-to-end checks:

```bash
python backend/test_flow.py
```

To generate demo reports and images:

```bash
python backend/seed.py
```
