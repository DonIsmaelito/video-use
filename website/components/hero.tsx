'use client';

import { useEffect, useState } from 'react';
import { ArrowDown } from 'lucide-react';
import { repository } from '@/lib/gallery';

const words = ['edits', 'motion', 'stories', 'video'];

export function Hero() {
  const [index, setIndex] = useState(0);
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
    const interval = window.setInterval(
      () => setIndex((current) => (current + 1) % words.length),
      2900,
    );
    return () => window.clearInterval(interval);
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
            width="46"
            height="46"
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
          <img src="/brand/github.svg" alt="" width="22" height="22" />
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
              <span key={index} className="hero-word">
                {words[index].split('').map((letter, i) => (
                  <span key={i} style={{ animationDelay: `${i * 40}ms` }}>
                    {letter}
                  </span>
                ))}
              </span>
            </span>
          </h1>
        </div>
        <div className="hero-foot">
          <div className="hero-foot-right">
            <a
              href="#examples"
              aria-label="Explore video examples"
              className="scroll-cue"
            >
              <ArrowDown size={20} />
            </a>
          </div>
        </div>
      </section>
    </>
  );
}
