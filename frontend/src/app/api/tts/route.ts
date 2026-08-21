import { NextRequest, NextResponse } from 'next/server';

export async function GET(request: NextRequest) {
  const text = request.nextUrl.searchParams.get('text') || '';
  if (!text.trim()) {
    return new NextResponse('Missing text parameter', { status: 400 });
  }

  const encodedText = encodeURIComponent(text.trim());
  const url = `https://translate.google.com/translate_tts?ie=UTF-8&q=${encodedText}&tl=vi&client=tw-ob`;

  try {
    const res = await fetch(url, {
      headers: {
        'User-Agent':
          'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
      }
    });

    if (!res.ok) {
      return new NextResponse('Failed to fetch TTS audio', { status: 502 });
    }

    const audioBuffer = await res.arrayBuffer();
    return new NextResponse(audioBuffer, {
      headers: {
        'Content-Type': 'audio/mpeg',
        'Cache-Control': 'public, max-age=86400',
        'Content-Disposition': 'inline; filename="tts.mp3"'
      }
    });
  } catch (error: any) {
    return new NextResponse(error.message || 'Internal TTS Error', { status: 500 });
  }
}
