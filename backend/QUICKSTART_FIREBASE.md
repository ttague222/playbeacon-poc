# Firebase Quick Start Guide

## Setup (5 minutes)

### 1. Get Firebase Credentials
1. Go to [Firebase Console](https://console.firebase.google.com/) → Your Project → ⚙️ Settings → Service Accounts
2. Click "Generate new private key"
3. Save as `serviceAccountKey.json` in the `backend` folder

### 2. Configure Environment
```bash
cd backend
cp .env.example .env
```

Edit `.env`:
```env
FIREBASE_CREDENTIALS_PATH=serviceAccountKey.json
FIREBASE_PROJECT_ID=your-project-id
OPENAI_API_KEY=sk-your-key-here
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Deploy Firestore Rules
```bash
cd ..
firebase deploy --only firestore:rules
```

## Run the Application

### Start Backend
```bash
cd backend
python main_firestore.py
```

Server runs at: http://localhost:8000

### Populate Database
```bash
python sample_crawl_firestore.py
```

This crawls ~200 games and generates embeddings (takes 5-10 minutes).

### Start Frontend
```bash
cd ../frontend
npm run dev
```

App runs at: http://localhost:5173

## Verify It's Working

1. **Check API**: Visit http://localhost:8000/docs
2. **Check Firestore**: Firebase Console → Firestore Database
   - Should see `games`, `user_profiles`, `user_feedback` collections
3. **Check Crawler**: Look for games in Firestore after running `sample_crawl_firestore.py`

## Key Files

- `backend/main_firestore.py` - Start server
- `backend/sample_crawl_firestore.py` - Populate database
- `backend/serviceAccountKey.json` - Your credentials (DON'T COMMIT!)
- `backend/.env` - Environment variables (DON'T COMMIT!)

## Common Issues

**"Firebase credentials file not found"**
→ Make sure `serviceAccountKey.json` is in the `backend` folder

**"Permission denied"**
→ Run `firebase deploy --only firestore:rules`

**"Module 'firebase_admin' not found"**
→ Run `pip install -r requirements.txt`

## Need More Help?

See [FIREBASE_BACKEND_SETUP.md](../FIREBASE_BACKEND_SETUP.md) for detailed instructions.
