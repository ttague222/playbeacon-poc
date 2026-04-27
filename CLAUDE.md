# RobloxDiscovery (playbeacon-poc)

**Proof of concept** — AI-powered Roblox game discovery using vector search. Validates the recommendation engine that became the foundation for PlayBeacon.

- **GitHub:** https://github.com/ttague222/playbeacon-poc

## Structure

```
RobloxDiscovery/
├── backend/         # Python FastAPI + pgvector/Pinecone/Firebase
│   ├── app/         # API routes
│   └── scripts/     # Crawlers and data ingestion
└── frontend/        # Vite + JavaScript UI
    └── src/
```

## Tech Stack
- **Backend:** Python, FastAPI, Pinecone (vector search), OpenAI embeddings, Firebase Firestore
- **Frontend:** Vite, JavaScript
- **Infrastructure:** Firebase

## Key Notes
- This is the technical prototype that preceded PlayBeacon
- Contains multiple backend variants: `main_pinecone.py` (vector search), `main_firestore.py` (Firebase), `main.py` (combined)
- Never commit `.env` or `serviceAccountKey.json`
