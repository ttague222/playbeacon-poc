# Pinecone Integration Setup Guide

This guide will help you set up Pinecone for vector similarity search in the Roblox Discovery application.

## What is Pinecone?

Pinecone is a vector database that enables fast similarity search. Instead of storing embeddings in Firestore, we store them in Pinecone for efficient querying and recommendations.

## Architecture

- **Firebase Firestore**: Stores game metadata (title, description, stats, etc.)
- **Pinecone**: Stores vector embeddings for similarity search
- **OpenAI**: Generates embeddings from game descriptions

## Setup Steps

### 1. Create a Pinecone Account

1. Go to [https://www.pinecone.io/](https://www.pinecone.io/)
2. Sign up for a free account (free tier includes 1 million vectors)
3. Verify your email

### 2. Create a Pinecone Index

1. Log in to the Pinecone console
2. Click "Create Index"
3. Configure the index:
   - **Name**: `roblox-games` (or your preferred name)
   - **Dimensions**: `1536` (matches OpenAI's text-embedding-3-small)
   - **Metric**: `cosine`
   - **Cloud Provider**: AWS (recommended)
   - **Region**: `us-east-1` (or closest to you)
4. Click "Create Index"

### 3. Get Your API Key

1. In the Pinecone console, go to "API Keys"
2. Copy your API key
3. Note your environment (e.g., `us-east-1`)

### 4. Update Your .env File

Add the following to your `.env` file:

```env
# Pinecone Configuration
PINECONE_API_KEY=your-api-key-here
PINECONE_ENVIRONMENT=us-east-1
PINECONE_INDEX_NAME=roblox-games
```

Replace:
- `your-api-key-here` with your actual Pinecone API key
- `us-east-1` with your Pinecone environment
- `roblox-games` with your index name if different

### 5. Test the Integration

Run the test script:

```bash
python test_pinecone.py
```

This will:
1. Verify Pinecone connection
2. Check for games in Firestore
3. Generate a test embedding
4. Store it in Pinecone
5. Display index statistics

## Using the Pinecone-Enabled API

### Start the Server

```bash
python -m uvicorn main_pinecone:app --host 127.0.0.1 --port 8000
```

Or run directly:

```bash
python main_pinecone.py
```

### API Endpoints

#### 1. Generate Embeddings

Generate embeddings for all games and store in Pinecone:

```bash
POST http://127.0.0.1:8000/api/generate-embeddings
```

#### 2. Get Similar Games

Find games similar to a specific game:

```bash
GET http://127.0.0.1:8000/api/games/{universe_id}/similar?limit=10
```

#### 3. Search by Text

Search for games using natural language:

```bash
POST http://127.0.0.1:8000/api/search
Body: {
  "query": "adventure games with magic",
  "limit": 10
}
```

#### 4. Personalized Recommendations

Get recommendations based on user preferences:

```bash
POST http://127.0.0.1:8000/api/queue
Body: {
  "user_id": "user123",
  "limit": 10
}
```

#### 5. Check Pinecone Stats

View index statistics:

```bash
GET http://127.0.0.1:8000/api/pinecone/stats
```

## Files Created for Pinecone Integration

### Core Services

1. **app/services/pinecone_service.py**
   - Manages Pinecone client and index
   - Handles vector upsert, query, and deletion

2. **app/services/embedding_service_pinecone.py**
   - Generates embeddings using OpenAI
   - Stores embeddings in Pinecone with metadata

3. **app/services/recommendation_service_pinecone.py**
   - Queries Pinecone for similar games
   - Provides text-based search
   - Generates personalized recommendations

### API Layer

4. **app/api/routes_pinecone.py**
   - FastAPI routes using Pinecone services
   - Includes similarity, search, and recommendation endpoints

5. **main_pinecone.py**
   - Main application file with Pinecone integration

### Testing & Documentation

6. **test_pinecone.py**
   - Test script to verify Pinecone integration

7. **PINECONE_SETUP.md** (this file)
   - Setup guide and documentation

## How It Works

### 1. Embedding Generation

```python
# Generate embedding for a game
embedding_service = EmbeddingService()
embedding_service.generate_game_embedding(universe_id)
```

This:
1. Fetches game data from Firestore
2. Creates a text representation (title + description + genre + creator)
3. Generates a 1536-dimension vector using OpenAI
4. Stores the vector in Pinecone with metadata

### 2. Similarity Search

```python
# Find similar games
rec_service = RecommendationService()
similar_games = rec_service.get_similar_games(universe_id, top_k=10)
```

This:
1. Generates an embedding for the query game
2. Queries Pinecone for similar vectors
3. Returns games with highest cosine similarity

### 3. Text Search

```python
# Search by description
games = rec_service.get_recommendations_by_text(
    "adventure games with parkour",
    top_k=10
)
```

This:
1. Generates an embedding from the search text
2. Queries Pinecone for matching game vectors
3. Returns the most similar games

## Metadata Stored in Pinecone

Each vector in Pinecone includes metadata:

```python
{
    "id": "universe_id",
    "values": [1536-dimensional vector],
    "metadata": {
        "title": "Game Title",
        "genre": "Adventure",
        "creator_name": "Creator",
        "visits": 1000000,
        "active_players": 500
    }
}
```

## Pinecone Free Tier Limits

- **Vectors**: Up to 1 million vectors
- **Dimensions**: Up to 2048 dimensions per vector
- **Queries**: Unlimited
- **Storage**: Included

This is sufficient for storing embeddings for hundreds of thousands of games.

## Troubleshooting

### "PINECONE_API_KEY not set"

Make sure you've added your API key to the `.env` file.

### "Index not found"

Verify that:
1. You've created an index in the Pinecone console
2. The index name in `.env` matches the console
3. The index dimensions are set to 1536

### OpenAI Quota Errors

If you see `429` errors when generating embeddings:
1. Check your OpenAI account has credits
2. Add credits at [https://platform.openai.com/account/billing](https://platform.openai.com/account/billing)

### Connection Errors

If Pinecone connection fails:
1. Verify your API key is correct
2. Check your internet connection
3. Ensure the environment matches your index location

## Next Steps

1. ✅ Set up Pinecone account
2. ✅ Create index with correct dimensions
3. ✅ Add API key to `.env`
4. Run `python test_pinecone.py` to verify setup
5. Generate embeddings for your games
6. Test similarity search and recommendations
7. Integrate with your frontend application

## API Documentation

Once the server is running, visit:

- **Interactive Docs**: http://127.0.0.1:8000/docs
- **OpenAPI Schema**: http://127.0.0.1:8000/openapi.json

## Support

For issues:
- Pinecone: [https://docs.pinecone.io/](https://docs.pinecone.io/)
- OpenAI: [https://platform.openai.com/docs](https://platform.openai.com/docs)
- Firebase: [https://firebase.google.com/docs](https://firebase.google.com/docs)
