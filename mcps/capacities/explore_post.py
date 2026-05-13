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
        "spaceId": space_id,
        "structureId": "RootPage",
        "title": "Test Page Exploration",
        "content": "Test content",
        "collectionId": collection_id
    }
    
    endpoints = [
        "/save-page",
        "/create-page",
        "/save-object",
        "/create-object",
        "/objects",
        "/v1/objects",
        "/v1/pages",
        "/v2/objects",
        "/v2/pages",
        "/save-content",
        "/save-structured-note",
    ]
    
    async with httpx.AsyncClient() as client:
        for ep in endpoints:
            url = f"https://api.capacities.io{ep}"
            print(f"Testing POST {url}...")
            try:
                r = await client.post(url, headers=headers, json=payload)
                print(f"Status: {r.status_code}")
                if r.status_code < 400:
                    print(f"SUCCESS with {ep}!")
                    print(r.text)
                    return
            except Exception as e:
                print(f"Error with {ep}: {e}")

if __name__ == "__main__":
    asyncio.run(main())
