import asyncio
import httpx
from capacities_mcp.config import settings

async def main():
    space_id = "0baa9384-e3a6-48c3-8f46-a72e941debaa"
    headers = {
        "Authorization": f"Bearer {settings.capacities_api_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "spaceId": space_id,
        "title": "Test v1 Create",
        "structureId": "RootPage",
        "content": "Test content"
    }
    
    url = "https://api.capacities.io/v1/create-content"
    print(f"Testing POST {url}...")
    async with httpx.AsyncClient() as client:
        r = await client.post(url, headers=headers, json=payload)
        print(f"Status: {r.status_code}")
        print(r.text)

if __name__ == "__main__":
    asyncio.run(main())
