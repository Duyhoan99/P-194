import { NextRequest, NextResponse } from 'next/server';

function splitTextIntoChunks(text: string, maxLen = 140): string[] {
  const clean = text.trim();
  if (clean.length <= maxLen) return [clean];

  const sentences = clean.split(/(?<=[.,;?!:\n])\s+/);
  const chunks: string[] = [];
  let current = '';

  for (const s of sentences) {
    if ((current + ' ' + s).trim().length <= maxLen) {
      current = (current + ' ' + s).trim();
    } else {
      if (current) chunks.push(current);
      if (s.length <= maxLen) {
        current = s;
      } else {
        // Break long words if any single sentence > maxLen
        const words = s.split(' ');
        let wordChunk = '';
        for (const w of words) {
          if ((wordChunk + ' ' + w).trim().length <= maxLen) {
            wordChunk = (wordChunk + ' ' + w).trim();
          } else {
            if (wordChunk) chunks.push(wordChunk);
            wordChunk = w;
          }
        }
        current = wordChunk;
      }
    }
  }
  if (current) chunks.push(current);
  return chunks.filter(c => c.length > 0);
}

export async function GET(request: NextRequest) {
  const text = request.nextUrl.searchParams.get('text') || '';
  if (!text.trim()) {
    return new NextResponse('Missing text parameter', { status: 400 });
  }

  const chunks = splitTextIntoChunks(text, 140);
  const audioBuffers: ArrayBuffer[] = [];

  try {
    for (const chunk of chunks) {
      const encodedText = encodeURIComponent(chunk);
      const url = `https://translate.google.com/translate_tts?ie=UTF-8&q=${encodedText}&tl=vi&client=tw-ob`;

      const res = await fetch(url, {
        headers: {
          'User-Agent':
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
      });

      if (res.ok) {
        const buf = await res.arrayBuffer();
        audioBuffers.push(buf);
      }
    }

    if (audioBuffers.length === 0) {
      return new NextResponse('Failed to fetch TTS audio', { status: 502 });
    }

    // Concatenate all ArrayBuffers into single continuous MP3 stream
    const totalLength = audioBuffers.reduce((acc, b) => acc + b.byteLength, 0);
    const combined = new Uint8Array(totalLength);
    let offset = 0;
    for (const b of audioBuffers) {
      combined.set(new Uint8Array(b), offset);
      offset += b.byteLength;
    }

    return new NextResponse(combined.buffer, {
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
