import asyncio
import json
import httpx
from capacities_mcp.server import _client
from capacities_mcp.config import settings

async def main():
    client = _client()
    space_id = "0baa9384-e3a6-48c3-8f46-a72e941debaa"
    collection_id = "3cec11ee-aaf3-42f1-9647-58cb4516ca2e" # Week Notes
    
    payload = {
        "spaceId": space_id,
        "structureId": "RootPage",
        "title": "Test Page via create-content",
        "content": "This is a test page created via /create-content.",
        "collectionId": collection_id
    }
    
    url = "https://api.capacities.io/create-content"
    headers = {
        "Authorization": f"Bearer {settings.capacities_api_token}",
        "Content-Type": "application/json"
    }
    
    print(f"Testing POST {url}...")
    async with httpx.AsyncClient() as http_client:
        response = await http_client.post(url, headers=headers, json=payload)
        print(f"Status: {response.status_code}")
        if response.status_code in {200, 201}:
            print("Success!")
            print(json.dumps(response.json(), indent=2))
        else:
            print(f"Failed: {response.text}")

if __name__ == "__main__":
    asyncio.run(main())
