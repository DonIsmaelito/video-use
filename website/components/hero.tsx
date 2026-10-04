'use client';

import { ArrowDown, ArrowUpRight } from 'lucide-react';
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
          <span className="hero-index">CREATE. EDIT. MAKE IT YOURS.</span>
          <p>
            Good videos start with a useful idea. Find yours in a library of
            real edits, motion design, 3D, and explainers.
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
        <span>01</span>
        <p>
          <strong>Find a direction</strong>
          <span>Choose an example that does the job.</span>
        </p>
      </div>
      <span className="flow-arrow" aria-hidden="true">
        ↗
      </span>
      <div>
        <span>02</span>
        <p>
          <strong>Copy the prompt</strong>
          <span>The useful details are already there.</span>
        </p>
      </div>
      <span className="flow-arrow" aria-hidden="true">
        ↗
      </span>
      <div>
        <span>03</span>
        <p>
          <strong>Make it your own</strong>
          <span>Paste into your Video Use agent.</span>
        </p>
      </div>
    </div>
  );
}
