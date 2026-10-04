import 'server-only';

import {
  createHash,
  createHmac,
  randomUUID,
  timingSafeEqual,
} from 'node:crypto';
import { createAdminClient } from '@insforge/sdk';

export const visitorCookie = 'video_use_visitor';

function signingKey() {
  const key = process.env.LIKES_COOKIE_SECRET;
  if (!key || key.length < 32)
    throw new Error('Likes signing key is not configured');
  return key;
}

function signature(id: string) {
  return createHmac('sha256', signingKey()).update(id).digest('hex');
}

/** Only a signed, opaque browser ID reaches the database, as a one-way hash. */
export function visitorIdentity(cookie?: string) {
  const [id = '', supplied = ''] = (cookie ?? '').split('.');
  const validFormat =
    /^[0-9a-f-]{36}$/.test(id) && /^[0-9a-f]{64}$/.test(supplied);
  const valid =
    validFormat &&
    timingSafeEqual(
      Buffer.from(supplied, 'hex'),
      Buffer.from(signature(id), 'hex'),
    );
  const identity = valid ? id : randomUUID();
  return {
    hash: createHash('sha256').update(identity).digest('hex'),
    cookie: `${identity}.${signature(identity)}`,
    isNew: !valid,
  };
}

export function likesDatabase() {
  const baseUrl = process.env.INSFORGE_URL;
  const apiKey = process.env.INSFORGE_API_KEY;
  if (!baseUrl || !apiKey) throw new Error('Likes database is not configured');
  return createAdminClient({ baseUrl, apiKey }).database;
}
