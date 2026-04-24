# PlayBeacon PoC — AI Game Recommendation Engine

> Proof of concept that validated the core recommendation engine powering PlayBeacon.

Before committing to a full product architecture, this prototype tested whether AI-powered personalized game discovery was feasible at scale using vector similarity search. It was — and became the technical foundation for [PlayBeacon](https://github.com/ttague222/PlayBeacon-Mobile).

---

## What This Validates

- **pgvector similarity search** produces relevant, fast game recommendations
- **OpenAI embeddings** effectively capture game "feel" from titles and descriptions
- A **Steam-style discovery queue UX** translates naturally to the Roblox context
- The full pipeline — crawl → embed → store → recommend — can run end-to-end

---

## Architecture

```
playbeacon-poc/
├── backend/
│   ├── crawler/     # Indexes Roblox games by keyword
│   ├── embeddings/  # OpenAI embedding pipeline → pgvector storage
│   └── api/         # FastAPI recommendation endpoints
└── frontend/        # React swipe interface (discovery queue)
```

---

## Tech Stack

![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat&logo=fastapi)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=flat&logo=postgresql&logoColor=white)
![OpenAI](https://img.shields.io/badge/OpenAI-412991?style=flat&logo=openai&logoColor=white)
![React](https://img.shields.io/badge/React-20232A?style=flat&logo=react&logoColor=61DAFB)
![Docker](https://img.shields.io/badge/Docker-2CA5E0?style=flat&logo=docker&logoColor=white)

---

## Key Components

- **Game Crawler** — automatically indexes Roblox games by keyword
- **Embedding Pipeline** — OpenAI embeddings stored in PostgreSQL via pgvector
- **Recommendation API** — FastAPI + cosine similarity search for personalized results
- **Discovery UI** — React swipe interface modeling Steam's discovery queue

---

## What Came Next

This PoC graduated into **[PlayBeacon](https://github.com/ttague222/PlayBeacon-Mobile)** — a full production app for families, live on iOS and Android.

---

Built by [Watchlight Interactive](https://watchlightinteractive.com)
