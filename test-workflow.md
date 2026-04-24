# Testing the Local Server

Your Roblox Discovery local test server is now running on **http://localhost:5001**!

## Current Status

✅ **Server Running**: Mock mode (in-memory data, no Firebase required)
✅ **OpenAI API**: Configured and ready
✅ **Pinecone Index**: Created with 1536 dimensions
✅ **All 6 Endpoints**: Operational

## Available Endpoints

All endpoints accept JSON and return JSON responses:

### 1. GET / - Health Check
```bash
curl http://localhost:5001/
```

### 2. POST /crawlGames - Fetch Roblox Games
```bash
curl -X POST http://localhost:5001/crawlGames \
  -H "Content-Type: application/json" \
  -d "{\"keywords\": [\"adventure\", \"tycoon\"], \"limit\": 10}"
```
**Note**: Roblox API endpoint may have changed. You might need to update the API URL or use mock data for testing.

### 3. POST /generateEmbeddings - Create OpenAI Embeddings
```bash
curl -X POST http://localhost:5001/generateEmbeddings \
  -H "Content-Type: application/json" \
  -d "{}"
```
Generates embeddings for games without them and uploads to Pinecone.

### 4. POST /submitFeedback - Record User Feedback
```bash
curl -X POST http://localhost:5001/submitFeedback \
  -H "Content-Type: application/json" \
  -d "{\"user_id\": \"test_user_123\", \"universe_id\": \"GAME_ID\", \"feedback\": 1}"
```
Feedback values:
- `1` = Like (updates user profile with game embedding)
- `0` = Skip
- `-1` = Dislike (filtered from future recommendations)

### 5. POST /getQueue - Get Personalized Recommendations
```bash
curl -X POST http://localhost:5001/getQueue \
  -H "Content-Type: application/json" \
  -d "{\"user_id\": \"test_user_123\", \"limit\": 10}"
```
Returns popular games for new users, personalized recommendations for users with liked games.

### 6. POST /resetUserProfile - Clear User Data
```bash
curl -X POST http://localhost:5001/resetUserProfile \
  -H "Content-Type: application/json" \
  -d "{\"user_id\": \"test_user_123\"}"
```

### 7. POST /getStats - System Statistics
```bash
curl -X POST http://localhost:5001/getStats \
  -H "Content-Type: application/json" \
  -d "{}"
```

## Test Workflow

Since the Roblox Games API might not be accessible, here's how to test with manual data:

1. **Add mock games to test** - You would need to manually add some game data
2. **Generate embeddings** - Test OpenAI integration
3. **Submit feedback** - Test user profiling
4. **Get recommendations** - Test Pinecone similarity search

## Integration with Frontend

To connect your frontend (running on http://localhost:3000), update the API base URL:

In your frontend code, change:
```javascript
const API_BASE = "http://localhost:5001";
```

Then all your Cloud Function calls will go to the local test server instead of Firebase.

## Next Steps

### For Full Firebase Deployment:

1. **Install Java** (for Firebase emulators)
2. **Run `firebase login`** manually in terminal
3. **Deploy**: `firebase deploy`

### For Now (Local Testing):

1. Server is running in mock mode ✅
2. Test the endpoints with curl or Postman
3. Integrate with frontend by updating API URL
4. Data is stored in memory (resets on server restart)

## Important Notes

- **Data is temporary**: All data is stored in memory and will be lost when the server restarts
- **Roblox API**: The games API endpoint may have changed. You might need to find an updated endpoint or use alternative data sources
- **Pinecone**: Connected to real Pinecone index (data persists in Pinecone)
- **OpenAI**: Using real OpenAI API (costs apply for embedding generation)

## Server Logs

Check the terminal where the server is running to see detailed logs for each request.
