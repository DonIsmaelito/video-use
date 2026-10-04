'use client';

import { ArrowDown, ArrowUpRight, Copy, Play, Sparkles } from 'lucide-react';
import Image from 'next/image';
import { SiteHeader } from '@/components/site-header';
import { GettingStarted } from '@/components/getting-started';
import { examples, repository } from '@/lib/gallery';

export function Hero() {
  return (
    <>
      <SiteHeader />
      <section className="hero" aria-labelledby="hero-title">
        <div className="hero-main">
          <span className="eyebrow">
            <span className="status-dot" /> The open-source video toolkit
          </span>
          <h1 id="hero-title">
            A prompt.
            <br />
            <em>Something useful.</em>
          </h1>
          <div className="hero-actions">
            <a
              href={repository}
              target="_blank"
              rel="noreferrer"
              className="primary-button"
            >
              <Image
                src="/brand/github.svg"
                className="github-button-mark"
                alt=""
                width={16}
                height={16}
              />{' '}
              Get Video Use <ArrowUpRight size={16} />
            </a>
            <a href="#examples" className="text-link">
              Explore the library <ArrowDown size={15} />
            </a>
          </div>
        </div>
        <div className="hero-aside">
          <p>
            Real videos. Open-source tools.
            <br />
            Your next idea starts here.
          </p>
          <GettingStarted />
          <div className="hero-footnote">
            <span>{examples.length} examples to explore</span>
            <span>Free prompts, always</span>
          </div>
        </div>
      </section>
    </>
  );
}

export function HowItWorks() {
  return (
    <div className="how-it-works" aria-label="How to use this library">
      <div>
        <span className="step-icon">
          <Play size={16} />
        </span>
        <p>
          <strong>Find a video</strong>
        </p>
      </div>
      <span className="flow-arrow" aria-hidden="true">
        ↗
      </span>
      <div>
        <span className="step-icon">
          <Copy size={16} />
        </span>
        <p>
          <strong>Copy its prompt</strong>
        </p>
      </div>
      <span className="flow-arrow" aria-hidden="true">
        ↗
      </span>
      <div>
        <span className="step-icon">
          <Sparkles size={16} />
        </span>
        <p>
          <strong>Make it your own</strong>
        </p>
      </div>
    </div>
  );
}
