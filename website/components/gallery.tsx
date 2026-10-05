'use client';

/* oxlint-disable jsx-a11y/media-has-caption -- These are original published media, some silent and some with burned captions. Do not invent caption tracks for existing videos. */

import { useEffect, useRef, useState } from 'react';
import { Check, Copy, Maximize2, Search, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Disclosure } from '@/components/ui/disclosure';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from '@/components/ui/dialog';
import { DemoDetail } from '@/components/demo-detail';
import { McpFeature } from '@/components/mcp-feature';
import { FeaturedFilm } from '@/components/featured-film';
import { FeaturedCarousel } from '@/components/featured-carousel';
import { McpConnections } from '@/components/mcp-connections';
import { MasonryGallery } from '@/components/masonry-gallery';
import productLaunch from '@/data/product-launch.json';
import featuredWorkflows from '@/data/featured-workflows.json';
import { PreviewMedia } from '@/components/preview-media';
import { TechniqueIcon } from '@/components/technique-icon';
import cardStyles from '@/components/gallery-cards.module.css';
import {
  buildChatPrompt,
  categories,
  defaultFilters,
  examples,
  facetOptions,
  filterExamples,
  readGalleryQuery,
  techniqueLabel,
  techniqueOptions,
  writeGalleryQuery,
  type Filters,
  type GalleryExample,
} from '@/lib/gallery';

// Mix footage, product films and graphic work in the opening row without changing
// the source catalog or its provenance. Filters and deep links still use all films.
const openingIds = [
  'screen-demo-fuji-browser-tour',
  'useful-52-show-then-do',
  'useful-53-fold-zine-night',
  'useful-51-cloud-seafloor',
  'useful-55-solar-speedrun',
  'useful-54-not-done-yet',
  'cloud-edit-travel',
  'useful-08-refill-product',
  'cloud-edit-podcast',
  'useful-07-workshop-invite',
  'useful-09-cafe-promo',
  'useful-19-fulfilment-flow',
];
const wideOpeningIds = new Set([
  'useful-51-cloud-seafloor',
  'useful-55-solar-speedrun',
]);
const galleryExamples = [
  ...openingIds.flatMap((id) =>
    examples.filter((example) => example.id === id),
  ),
  ...examples.filter((example) => !openingIds.includes(example.id)),
];
// Featured captions describe the use case; each film keeps its own prompt and credits.
const featuredExamples = featuredWorkflows.flatMap((workflow) => {
  const example = examples.find((item) => item.id === workflow.exampleId);
  return example ? [{ ...workflow, example }] : [];
});

function VideoCard({
  example,
  open,
  copy,
  copied,
  suspended,
}: {
  example: GalleryExample;
  open: () => void;
  copy: () => void;
  copied: boolean;
  suspended: boolean;
}) {
  return (
    <article
      className={`video-card ${cardStyles.card}`}
      data-orientation={example.orientation}
      data-featured={
        example.id === 'screen-demo-fuji-browser-tour' || undefined
      }
      data-wide={wideOpeningIds.has(example.id) || undefined}
      aria-label={example.title}
    >
      <div className={cardStyles.media}>
        <button
          type="button"
          className={`video-frame ${example.orientation} ${cardStyles.frame}`}
          onClick={open}
          aria-label={'Watch ' + example.title + ' and view its prompt'}
        >
          <PreviewMedia
            src={example.video}
            poster={example.poster}
            orientation={example.orientation}
            suspended={suspended}
          />
        </button>
        <div className={cardStyles.overlay}>
          <div className={cardStyles.content}>
            <h3 className={cardStyles.title} title={example.title}>
              {example.title}
            </h3>
            <button
              className={`copy-card ${cardStyles.copy} ${copied ? 'copied' : ''}`}
              type="button"
              onClick={copy}
              aria-label={'Copy prompt for ' + example.title}
            >
              {copied ? <Check size={15} /> : <Copy size={15} />}
              {copied ? 'Copied' : 'Copy Prompt'}
            </button>
          </div>
        </div>
      </div>
    </article>
  );
}

export function Gallery() {
  const [filters, setFilters] = useState<Filters>(defaultFilters);
  const [selected, setSelected] = useState<GalleryExample | null>(null);
  const [copied, setCopied] = useState('');
  const [message, setMessage] = useState('');
  const [manualCopy, setManualCopy] = useState('');
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const manualText = useRef<HTMLTextAreaElement>(null);
  const visible = filterExamples(filters, galleryExamples);
  const filterCount =
    filters.audiences.length +
    filters.useCases.length +
    (filters.technique ? 1 : 0);
  const hasFilters =
    !!filterCount || !!filters.query || filters.category !== 'All examples';

  useEffect(() => {
    function syncLocation() {
      const state = readGalleryQuery(
        new URLSearchParams(window.location.search),
      );
      setFilters(state.filters);
      setSelected(state.example);
    }
    syncLocation();
    window.addEventListener('popstate', syncLocation);
    return () => {
      window.removeEventListener('popstate', syncLocation);
      if (timer.current) clearTimeout(timer.current);
    };
  }, []);
  useEffect(() => {
    if (manualCopy) manualText.current?.select();
  }, [manualCopy]);
  useEffect(() => {
    if (!selected && !manualCopy) return;
    window.dispatchEvent(new CustomEvent('videouse:overlay', { detail: true }));
    return () => {
      window.dispatchEvent(
        new CustomEvent('videouse:overlay', { detail: false }),
      );
    };
  }, [selected, manualCopy]);

  function writeLocation(
    nextFilters: Filters,
    exampleId: string | null,
    push = false,
  ) {
    const params = writeGalleryQuery(
      new URLSearchParams(window.location.search),
      nextFilters,
      exampleId,
    );
    const url =
      window.location.pathname +
      (params.size ? '?' + params.toString() : '') +
      window.location.hash;
    if (push) window.history.pushState({ videoUseExample: true }, '', url);
    else window.history.replaceState(window.history.state, '', url);
  }

  function updateFilters(update: Partial<Filters>) {
    const next = { ...filters, ...update };
    setFilters(next);
    writeLocation(next, selected?.id ?? null);
  }

  function toggleFacet(field: 'audiences' | 'useCases', value: string) {
    updateFilters({
      [field]: filters[field].includes(value)
        ? filters[field].filter((item) => item !== value)
        : [...filters[field], value],
    });
  }

  async function copyText(text: string, key: string, notice: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(key);
      setMessage(notice);
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => {
        setCopied('');
        setMessage('');
      }, 2600);
    } catch {
      setManualCopy(text);
    }
  }

  function openExample(example: GalleryExample) {
    setSelected(example);
    writeLocation(filters, example.id, true);
  }

  function closeExample() {
    setSelected(null);
    if (window.history.state?.videoUseExample) window.history.back();
    else writeLocation(filters, null);
  }

  return (
    <>
      <FeaturedCarousel>
        <McpFeature suspended={selected !== null || !!manualCopy} />
        <FeaturedFilm
          media={productLaunch}
          title="Product Launches"
          subtitle="Turn your product into a launch worth watching."
          suspended={selected !== null || !!manualCopy}
        />
        {featuredExamples.map(({ example, title, description, fit }) => (
          <article className="featured-card" key={example.id}>
            <button
              type="button"
              className={
                'featured-frame' +
                (fit === 'cover' ? ' featured-frame-fill' : '')
              }
              onClick={() => openExample(example)}
              aria-label={`Watch ${title}`}
            >
              <PreviewMedia
                src={example.video}
                poster={example.poster}
                orientation={example.orientation}
                suspended={selected !== null || !!manualCopy}
              />
              <span className="featured-watch">
                <Maximize2 size={18} />
              </span>
            </button>
            <div className="featured-caption">
              <button type="button" onClick={() => openExample(example)}>
                {title}
              </button>
              <span>{description}</span>
            </div>
          </article>
        ))}
      </FeaturedCarousel>
      <McpConnections />
      <section
        id="examples"
        className="gallery-section"
        aria-labelledby="library-heading"
      >
        <h2 id="library-heading" className="sr-only">
          Explore the video library
        </h2>
        <div className="library-toolbar">
          <fieldset className="filter-list" aria-label="Filter by category">
            {categories.map((item) => (
              <button
                key={item}
                type="button"
                className={
                  'filter-pill ' + (filters.category === item ? 'active' : '')
                }
                aria-pressed={filters.category === item}
                onClick={() => updateFilters({ category: item })}
              >
                {item === 'All examples' ? 'All' : item}
              </button>
            ))}
          </fieldset>
          <label className="library-search">
            <Search size={16} />
            <span className="sr-only">Search examples</span>
            <input
              type="search"
              placeholder="Search prompts"
              value={filters.query}
              maxLength={200}
              onChange={(event) => updateFilters({ query: event.target.value })}
            />
          </label>
        </div>
        <div className="library-layout">
          <aside
            id="library-filters"
            className="library-sidebar"
            aria-label="Refine examples"
          >
            <fieldset className="facet-group">
              <legend className="facet-heading">
                <span>Video type</span>
                {hasFilters && (
                  <button
                    type="button"
                    onClick={() => updateFilters(defaultFilters)}
                    aria-label="Reset all filters"
                  >
                    Reset
                  </button>
                )}
              </legend>
              {techniqueOptions.map((item) => {
                const count = filterExamples({
                  ...filters,
                  technique: item.value,
                }).length;
                return (
                  <label className="facet-option" key={item.value}>
                    <input
                      type="checkbox"
                      checked={filters.technique === item.value}
                      onChange={() =>
                        updateFilters({
                          technique:
                            filters.technique === item.value ? '' : item.value,
                        })
                      }
                      disabled={!count && filters.technique !== item.value}
                    />
                    <span className="facet-label">
                      <TechniqueIcon technique={item.value} />
                      {item.label}
                    </span>
                    <span className="facet-count">{count}</span>
                  </label>
                );
              })}
            </fieldset>
            {(['audiences', 'useCases'] as const).map((field) => {
              const options = (
                <fieldset className="facet-group">
                  <legend className="sr-only">
                    {field === 'audiences' ? 'By audience' : 'By use case'}
                  </legend>
                  {facetOptions(field).map((item) => {
                    const count = filterExamples({
                      ...filters,
                      [field]: [item],
                    }).length;
                    return (
                      <label className="facet-option" key={item}>
                        <input
                          type="checkbox"
                          checked={filters[field].includes(item)}
                          onChange={() => toggleFacet(field, item)}
                          disabled={!count && !filters[field].includes(item)}
                        />
                        <span>{item}</span>
                        <span className="facet-count">{count}</span>
                      </label>
                    );
                  })}
                </fieldset>
              );

              // Use cases stay expanded as a primary browsing control.
              return field === 'useCases' ? (
                <section
                  key={field}
                  className="facet-section"
                  aria-labelledby="use-case-heading"
                >
                  <h3 id="use-case-heading">Use case</h3>
                  {options}
                </section>
              ) : (
                <Disclosure
                  key={field}
                  label="Audience"
                  defaultOpen
                  className="facet-disclosure"
                >
                  {options}
                </Disclosure>
              );
            })}
          </aside>
          <div className="library-content">
            <p className="sr-only" aria-live="polite">
              {visible.length} examples
            </p>
            {filterCount > 0 && (
              <div className="active-filters" aria-label="Active filters">
                {filters.technique && (
                  <button
                    type="button"
                    onClick={() => updateFilters({ technique: '' })}
                  >
                    {techniqueLabel(filters.technique)}
                    <X size={11} />
                  </button>
                )}
                {(['audiences', 'useCases'] as const).flatMap((field) =>
                  filters[field].map((item) => (
                    <button
                      type="button"
                      key={field + item}
                      onClick={() => toggleFacet(field, item)}
                    >
                      {item}
                      <X size={11} />
                    </button>
                  )),
                )}
              </div>
            )}
            <MasonryGallery>
              {visible.map((example) => (
                <VideoCard
                  key={example.id}
                  example={example}
                  open={() => openExample(example)}
                  copy={() =>
                    copyText(
                      buildChatPrompt(example),
                      example.id,
                      'Prompt copied',
                    )
                  }
                  copied={copied === example.id}
                  suspended={selected !== null || !!manualCopy}
                />
              ))}
            </MasonryGallery>
            {!visible.length && (
              <div className="empty-results">
                <Search size={25} />
                <h3>No matches.</h3>
                <p>
                  Try fewer filters or a different search, like “product” or
                  “captions”.
                </p>
                <button
                  type="button"
                  className="primary-button"
                  onClick={() => updateFilters(defaultFilters)}
                >
                  Show all examples
                </button>
              </div>
            )}
          </div>
        </div>
      </section>
      <Dialog
        open={selected !== null}
        onOpenChange={(isOpen) => {
          if (!isOpen) closeExample();
        }}
      >
        {selected && (
          <DemoDetail
            key={selected.id}
            example={selected}
            copied={copied === selected.id}
            onCopy={() =>
              copyText(buildChatPrompt(selected), selected.id, 'Prompt copied')
            }
          />
        )}
      </Dialog>
      <Dialog
        open={!!manualCopy}
        onOpenChange={(isOpen) => {
          if (!isOpen) setManualCopy('');
        }}
      >
        <DialogContent className="manual-copy-dialog">
          <DialogTitle>Copy Prompt</DialogTitle>
          <DialogDescription>
            Your browser couldn’t copy automatically. Copy the selected text
            below.
          </DialogDescription>
          <textarea
            ref={manualText}
            value={manualCopy}
            readOnly
            aria-label="Text to copy"
            rows={8}
          />
          <Button onClick={() => setManualCopy('')}>Done</Button>
        </DialogContent>
      </Dialog>
      {message && <output className="toast-message">{message}</output>}
    </>
  );
}
