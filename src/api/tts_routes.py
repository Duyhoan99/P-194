import httpx
from fastapi import APIRouter, HTTPException, Query, Response

router = APIRouter(prefix="/api/v1/tts", tags=["TTS"])


@router.get("")
async def get_tts_audio(text: str = Query(..., min_length=1, max_length=1000)):
    """Fetch natural Vietnamese TTS audio mp3 stream."""
    try:
        url = "https://translate.google.com/translate_tts"
        params = {
            "ie": "UTF-8",
            "q": text,
            "tl": "vi",
            "client": "tw-ob"
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params, headers=headers)
            if resp.status_code != 200:
                raise HTTPException(status_code=502, detail="TTS service error")
            return Response(
                content=resp.content,
                media_type="audio/mpeg",
                headers={
                    "Cache-Control": "public, max-age=86400",
                    "Content-Disposition": "inline; filename=tts.mp3"
                }
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
