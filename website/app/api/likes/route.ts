import { NextRequest, NextResponse } from 'next/server';
import { examples } from '@/lib/gallery';
import {
  likesDatabase,
  visitorCookie,
  visitorIdentity,
} from '@/lib/likes-server';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const exampleIds = examples.map((example) => example.id);
const allowed = new Set(exampleIds);
type LikeRow = { example_id: string; like_count: number; liked: boolean };

function responseFor(
  data: unknown,
  visitor: ReturnType<typeof visitorIdentity>,
) {
  const response = NextResponse.json(data, {
    headers: { 'Cache-Control': 'private, no-store' },
  });
  if (visitor.isNew)
    response.cookies.set(visitorCookie, visitor.cookie, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      maxAge: 60 * 60 * 24 * 365,
      path: '/',
    });
  return response;
}

export async function GET(request: NextRequest) {
  try {
    const visitor = visitorIdentity(request.cookies.get(visitorCookie)?.value);
    const { data, error } = await likesDatabase().rpc('get_video_likes', {
      example_ids: exampleIds,
      viewer_hash: visitor.hash,
    });
    if (error) throw error;
    const likes = Object.fromEntries(
      (data as LikeRow[]).map((row) => [
        row.example_id,
        {
          count: Number(row.like_count),
          liked: row.liked,
        },
      ]),
    );
    return responseFor({ likes }, visitor);
  } catch {
    return NextResponse.json(
      { error: 'Likes are temporarily unavailable' },
      { status: 503 },
    );
  }
}

export async function POST(request: NextRequest) {
  // Keep cookie-backed mutations same-origin; the caller never supplies an identity.
  const origin = request.headers.get('origin');
  let sameOrigin = !origin;
  if (origin) {
    try {
      const source = new URL(origin);
      // Next can normalize request.url to localhost or a deployment hostname.
      // The incoming Host preserves the browser-facing origin, including its port.
      sameOrigin =
        ['http:', 'https:'].includes(source.protocol) &&
        (source.host === request.headers.get('host') ||
          source.origin === process.env.SITE_URL);
    } catch {
      sameOrigin = false;
    }
  }
  if (request.headers.get('sec-fetch-site') === 'cross-site' || !sameOrigin) {
    return NextResponse.json({ error: 'Invalid origin' }, { status: 403 });
  }
  if (!request.headers.get('content-type')?.startsWith('application/json')) {
    return NextResponse.json({ error: 'Expected JSON' }, { status: 415 });
  }
  let payload: unknown;
  try {
    const body = await request.text();
    if (body.length > 512)
      return NextResponse.json({ error: 'Request too large' }, { status: 413 });
    payload = JSON.parse(body);
  } catch {
    return NextResponse.json({ error: 'Invalid request' }, { status: 400 });
  }
  if (
    !payload ||
    typeof payload !== 'object' ||
    !('id' in payload) ||
    !('liked' in payload) ||
    typeof payload.id !== 'string' ||
    !allowed.has(payload.id) ||
    typeof payload.liked !== 'boolean'
  ) {
    return NextResponse.json(
      { error: 'Invalid example or like state' },
      { status: 400 },
    );
  }
  try {
    const visitor = visitorIdentity(request.cookies.get(visitorCookie)?.value);
    const { data, error } = await likesDatabase().rpc('set_video_like', {
      target_id: payload.id,
      viewer_hash: visitor.hash,
      is_liked: payload.liked,
    });
    if (error) throw error;
    const [saved] = data as LikeRow[];
    return responseFor(
      { count: Number(saved.like_count), liked: saved.liked },
      visitor,
    );
  } catch {
    return NextResponse.json(
      { error: 'Could not save your like' },
      { status: 503 },
    );
  }
}
