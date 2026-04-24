"""
Quick test script to verify API is working
"""
import requests
import json

BASE_URL = "http://localhost:8000"

def test_endpoint(name, url):
    """Test an API endpoint"""
    try:
        response = requests.get(url, timeout=30)
        print(f"\n[{name}]")
        print(f"  Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"  Response: {json.dumps(data, indent=2)}")
            return True
        else:
            print(f"  Error: {response.text}")
            return False
    except Exception as e:
        print(f"\n[{name}]")
        print(f"  Error: {e}")
        return False

print("=" * 60)
print("Testing Roblox Discovery API (Firestore)")
print("=" * 60)

# Test root endpoint
test_endpoint("Root Endpoint", f"{BASE_URL}/")

# Test health check
test_endpoint("Health Check", f"{BASE_URL}/api/health")

# Test games endpoint
test_endpoint("Games List", f"{BASE_URL}/api/games?limit=5")

print("\n" + "=" * 60)
print("API Test Complete!")
print("=" * 60)
print("\nAPI Documentation available at: http://localhost:8000/docs")
