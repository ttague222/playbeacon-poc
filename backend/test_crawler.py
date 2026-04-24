"""
Test script for crawler endpoints
"""
import sys
sys.path.insert(0, '.')

import asyncio
import httpx
from app.db.firebase import initialize_firebase
from firebase_admin import auth

async def test_crawler_endpoints():
    """Test crawler endpoints with admin token"""

    # Initialize Firebase
    initialize_firebase()

    # Get admin user token
    user = auth.get_user_by_email('ttague222@gmail.com')
    token = auth.create_custom_token(user.uid).decode('utf-8')

    print(f"Testing crawler endpoints for user: {user.email}")
    print(f"User UID: {user.uid}")
    print()

    # Create HTTP client
    client = httpx.AsyncClient(timeout=30.0)
    base_url = "http://localhost:8000/api/crawler"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    try:
        # Test 1: Get crawler status
        print("=" * 60)
        print("Test 1: GET /api/crawler/status")
        print("=" * 60)
        response = await client.get(f"{base_url}/status", headers=headers)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        print()

        # Test 2: Enqueue a sample game
        print("=" * 60)
        print("Test 2: POST /api/crawler/enqueue")
        print("=" * 60)
        payload = {
            "universe_ids": [606849621],  # Jailbreak
            "source": "manual_test",
            "priority": 7
        }
        print(f"Payload: {payload}")
        response = await client.post(f"{base_url}/enqueue", headers=headers, json=payload)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        print()

        # Test 3: Get status again to see if queue increased
        print("=" * 60)
        print("Test 3: GET /api/crawler/status (after enqueue)")
        print("=" * 60)
        response = await client.get(f"{base_url}/status", headers=headers)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        print()

        # Test 4: Process a small batch
        print("=" * 60)
        print("Test 4: POST /api/crawler/process-batch?limit=1")
        print("=" * 60)
        response = await client.post(f"{base_url}/process-batch?limit=1", headers=headers)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        print()

        # Test 5: Get status to see results
        print("=" * 60)
        print("Test 5: GET /api/crawler/status (after processing)")
        print("=" * 60)
        response = await client.get(f"{base_url}/status", headers=headers)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        print()

        print("=" * 60)
        print("ALL TESTS COMPLETED SUCCESSFULLY!")
        print("=" * 60)

    except Exception as e:
        print(f"Error during testing: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.aclose()

if __name__ == "__main__":
    asyncio.run(test_crawler_endpoints())
