import httpx
from fastapi import APIRouter, Query
from fastapi.responses import Response

router = APIRouter(tags=["proxy"])

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            follow_redirects=True,
            timeout=15.0,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            },
        )
    return _client


@router.get("/proxy-image")
async def proxy_image(url: str = Query(..., description="External image URL to proxy")):
    """
    Proxy external images to bypass CORS restrictions.
    Fetches the image server-side and returns it with proper headers.
    """
    client = _get_client()
    try:
        resp = await client.get(url)
        if resp.status_code != 200:
            return Response(status_code=resp.status_code)

        content_type = resp.headers.get("content-type", "image/jpeg")
        return Response(
            content=resp.content,
            media_type=content_type,
            headers={
                "Cache-Control": "public, max-age=86400",
                "Access-Control-Allow-Origin": "*",
            },
        )
    except httpx.HTTPError:
        return Response(status_code=502)
