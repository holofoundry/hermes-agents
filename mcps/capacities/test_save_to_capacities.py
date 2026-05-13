import asyncio
import httpx
from capacities_mcp.config import settings

async def main():
    space_id = "0baa9384-e3a6-48c3-8f46-a72e941debaa"
    collection_id = "3cec11ee-aaf3-42f1-9647-58cb4516ca2e"
    
    headers = {
        "Authorization": f"Bearer {settings.capacities_api_token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "properties": {
            "title": "Test Page via save-to-capacities"
        },
        "structureId": "RootPage", # I'll try RootPage based on my space-info
        "collectionId": collection_id,
        "content": [
            {
                "type": "text",
                "text": "This is a test page created via /save-to-capacities."
            }
        ]
    }
    
    url = "https://api.capacities.io/save-to-capacities"
    print(f"Testing POST {url}...")
    async with httpx.AsyncClient() as client:
        r = await client.post(url, headers=headers, json=payload)
        print(f"Status: {r.status_code}")
        print(r.text)

if __name__ == "__main__":
    asyncio.run(main())
