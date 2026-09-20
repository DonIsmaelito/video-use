'use client';

import { useEffect, useState } from 'react';
import { GettingStarted } from '@/components/getting-started';
import { repository } from '@/lib/gallery';

const words = ['edits', 'motion', 'stories', 'video'];
const wordTransitionMs = 500;
const wordHoldMs = 1200;

export function Hero() {
  const [step, setStep] = useState(0);
  const index = step % words.length;
  const [reducedMotion, setReducedMotion] = useState(true);
  const [stars, setStars] = useState<number | null>(null);

  useEffect(() => {
    const preference = window.matchMedia('(prefers-reduced-motion: reduce)');
    const sync = () => setReducedMotion(preference.matches);
    sync();
    preference.addEventListener('change', sync);
    return () => preference.removeEventListener('change', sync);
  }, []);

  useEffect(() => {
    if (reducedMotion) return;
    let timer = window.setTimeout(advance, wordHoldMs);
    function advance() {
      setStep((current) => current + 1);
      timer = window.setTimeout(advance, wordHoldMs + wordTransitionMs);
    }
    return () => window.clearTimeout(timer);
  }, [reducedMotion]);

  useEffect(() => {
    const controller = new AbortController();
    fetch('https://api.github.com/repos/browser-use/video-use', {
      signal: controller.signal,
    })
      .then((response) => (response.ok ? response.json() : Promise.reject()))
      .then((data: unknown) => {
        if (
          data &&
          typeof data === 'object' &&
          'stargazers_count' in data &&
          typeof data.stargazers_count === 'number' &&
          Number.isFinite(data.stargazers_count)
        )
          setStars(data.stargazers_count);
      })
      .catch(() => {});
    return () => controller.abort();
  }, []);

  return (
    <>
      <header className="site-header">
        <a href="/" aria-label="Video use home" className="brand">
          <img
            src="/brand/browser-use.svg"
            alt="Browser Use"
            width="56"
            height="56"
          />
        </a>
        <a
          className="github-link"
          aria-label={
            stars === null
              ? 'View video-use on GitHub'
              : `View video-use on GitHub · ${stars.toLocaleString()} stars`
          }
          href={repository}
          target="_blank"
          rel="noreferrer"
        >
          <span>GitHub</span>
          <span className="github-stars" aria-hidden="true">
            {stars === null
              ? '—'
              : new Intl.NumberFormat('en', {
                  notation: 'compact',
                  maximumFractionDigits: 1,
                }).format(stars)}
          </span>
        </a>
      </header>
      <section
        className="hero"
        aria-label="Make edits, motion, stories, and video with a prompt"
      >
        <div className="hero-composition">
          <h1>
            <span className="sr-only">
              Prompt edits, motion, stories, and video.
            </span>
            <span aria-hidden="true" className="hero-top">
              <span>prompt</span>
              <span className="hero-rule" />
              <span className="hero-amp">&</span>
            </span>
            <span aria-hidden="true" className="hero-bottom">
              <span className="hero-word-stage">
                {step > 0 && !reducedMotion && (
                  <span key={`out-${step}`} className="hero-word hero-word-out">
                    {words[(index + words.length - 1) % words.length]}
                  </span>
                )}
                <span
                  key={`in-${step}`}
                  className={`hero-word ${step > 0 && !reducedMotion ? 'hero-word-in' : ''}`}
                >
                  {words[index]}
                </span>
              </span>
            </span>
          </h1>
          <GettingStarted />
        </div>
      </section>
    </>
  );
}
