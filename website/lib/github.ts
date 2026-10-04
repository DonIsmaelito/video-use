import 'server-only';
import { repository } from '@/lib/gallery';

export async function getRepositoryStars(): Promise<number | null> {
  try {
    const response = await fetch(
      `https://api.github.com/repos${new URL(repository).pathname}`,
      {
        headers: {
          Accept: 'application/vnd.github+json',
          'X-GitHub-Api-Version': '2026-03-10',
        },
        next: { revalidate: 3600 },
        signal: AbortSignal.timeout(3000),
      },
    );
    if (!response.ok) return null;

    const data: { stargazers_count?: unknown } = await response.json();
    const count = data.stargazers_count;
    return typeof count === 'number' &&
      Number.isSafeInteger(count) &&
      count >= 0
      ? count
      : null;
  } catch {
    // Keep the repository link usable if GitHub is temporarily unavailable.
    return null;
  }
}
