'use client';

import { useEffect, useState } from 'react';
import { ArrowDown, ArrowUpRight, Pause, Play, Star } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { examples, repository } from '@/lib/gallery';

const words = ['edits', 'motion', 'stories', 'video'];

export function Hero() {
  const [index, setIndex] = useState(0);
  const [paused, setPaused] = useState(false);
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
    if (paused || reducedMotion) return;
    const interval = window.setInterval(
      () => setIndex((current) => (current + 1) % words.length),
      2900,
    );
    return () => window.clearInterval(interval);
  }, [paused, reducedMotion]);

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
            width="38"
            height="38"
          />
        </a>
        <a
          className="github-link"
          href={repository}
          target="_blank"
          rel="noreferrer"
        >
          <img src="/brand/github.svg" alt="" width="17" height="17" />
          <span>video-use</span>
          <span
            className="github-stars"
            aria-label={
              stars === null
                ? 'Star video-use on GitHub'
                : `${stars.toLocaleString()} GitHub stars`
            }
          >
            <Star size={13} />
            {stars === null
              ? 'Star'
              : new Intl.NumberFormat('en', {
                  notation: 'compact',
                  maximumFractionDigits: 1,
                }).format(stars)}
          </span>
          <ArrowUpRight size={15} />
        </a>
      </header>
      <section
        className={`hero ${paused ? 'motion-paused' : ''}`}
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
          <a
            className="hero-previews"
            href="#examples"
            aria-label="Explore the video gallery"
          >
            {[examples[0], examples[1], examples[8]].map((example, i) => (
              <span
                className={`floating-preview preview-${i}`}
                key={example.id}
              >
                <img src={example.poster} alt="" width="180" height="112" />
                <span className="preview-corner">
                  <Play size={9} fill="currentColor" />
                </span>
              </span>
            ))}
          </a>
        </div>
        <div className="hero-foot">
          <span>VIDEO-USE · OPEN SOURCE</span>
          <div className="hero-foot-right">
            {!reducedMotion && (
              <Button
                className="motion-toggle"
                variant="ghost"
                size="icon"
                aria-label={
                  paused ? 'Resume hero animation' : 'Pause hero animation'
                }
                onClick={() => setPaused(!paused)}
              >
                {paused ? <Play size={12} /> : <Pause size={12} />}
              </Button>
            )}
            <a href="#examples">
              A little inspiration goes a long way <ArrowDown size={15} />
            </a>
          </div>
        </div>
      </section>
    </>
  );
}
