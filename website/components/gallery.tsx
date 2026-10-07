'use client';

/* oxlint-disable jsx-a11y/media-has-caption -- These are original published media, some silent and some with burned captions. Do not invent caption tracks for existing videos. */

import { Fragment, useEffect, useMemo, useRef, useState } from 'react';
import {
  Check,
  Copy,
  Maximize2,
  Search,
  SlidersHorizontal,
  X,
} from 'lucide-react';
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
import { McpDots } from '@/components/mcp-dots';
import { MasonryGallery } from '@/components/masonry-gallery';
import { GallerySector } from '@/components/gallery-sector';
import {
  getSectorExamples,
  getSectorPreview,
  sectors,
  type SectorId,
} from '@/lib/sectors';
import productLaunch from '@/data/product-launch.json';
import featuredWorkflows from '@/data/featured-workflows.json';
import { PreviewMedia } from '@/components/preview-media';
import { TechniqueIcon } from '@/components/technique-icon';
import cardStyles from '@/components/gallery-cards.module.css';
import libraryStyles from '@/components/gallery-library.module.css';
import {
  buildChatPrompt,
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
  'useful-83-spiderman-panels',
  'useful-85-rumi-double-life',
  'useful-82-curry-locked-in',
  'useful-81-speed-fast-travel',
  'useful-84-wednesday-deadpan',
  'useful-73-pacu-poster',
  'useful-74-drew-editorial',
  'useful-72-era-swap',
  'useful-71-whiskey',
  'useful-75-leah-glambot',
  'useful-79-dubai-chocolate',
  'useful-76-doc-hudson',
  'useful-77-muzan-panel',
  'useful-78-routine-rhythm',
  'useful-80-han-toy-car',
  'useful-66-tank-workout',
  'useful-65-andrew-amelia',
  'useful-61-druski-entrance',
  'useful-70-pocket-4p',
  'useful-63-quenlin-verdict',
  'useful-64-billie-finneas',
  'useful-62-speed-shaolin',
  'useful-68-speed-kai-chained',
  'useful-67-holloway-ten-seconds',
  'useful-69-meta-muse-glasses',
  'cloud-edit-travel',
  'useful-08-refill-product',
  'cloud-edit-podcast',
  'useful-07-workshop-invite',
  'useful-09-cafe-promo',
  'useful-19-fulfilment-flow',
];
const wideOpeningIds = new Set([
  'useful-83-spiderman-panels',
  'useful-85-rumi-double-life',
  'useful-82-curry-locked-in',
  'useful-81-speed-fast-travel',
  'useful-84-wednesday-deadpan',
  'useful-71-whiskey',
  'useful-72-era-swap',
  'useful-76-doc-hudson',
  'useful-77-muzan-panel',
  'useful-78-routine-rhythm',
  'useful-80-han-toy-car',
  'useful-61-druski-entrance',
  'useful-62-speed-shaolin',
  'useful-67-holloway-ten-seconds',
  'useful-68-speed-kai-chained',
  'useful-69-meta-muse-glasses',
  'useful-70-pocket-4p',
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
  preview = false,
}: {
  example: GalleryExample;
  open: () => void;
  copy: () => void;
  copied: boolean;
  suspended: boolean;
  preview?: boolean;
}) {
  return (
    <article
      className={`video-card ${cardStyles.card}`}
      data-orientation={example.orientation}
      data-featured={
        (!preview && example.id === 'screen-demo-fuji-browser-tour') ||
        undefined
      }
      data-wide={(!preview && wideOpeningIds.has(example.id)) || undefined}
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

export function Gallery({
  sector,
  browse = false,
}: {
  sector?: SectorId;
  browse?: boolean;
}) {
  const [filters, setFilters] = useState<Filters>(defaultFilters);
  const [selected, setSelected] = useState<GalleryExample | null>(null);
  const [copied, setCopied] = useState('');
  const [message, setMessage] = useState('');
  const [manualCopy, setManualCopy] = useState('');
  const [showFilters, setShowFilters] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const manualText = useRef<HTMLTextAreaElement>(null);
  const source = useMemo(
    () =>
      sector ? getSectorExamples(sector, galleryExamples) : galleryExamples,
    [sector],
  );
  const visible = filterExamples(filters, source);
  const availableTechniques = techniqueOptions.filter((item) =>
    source.some((example) => example.technique === item.value),
  );
  const filterCount =
    filters.audiences.length +
    filters.useCases.length +
    (filters.technique ? 1 : 0) +
    (filters.category !== 'All examples' ? 1 : 0);
  const hasFilters =
    !!filterCount || !!filters.query || filters.category !== 'All examples';
  const showLibrary = browse || !!sector || hasFilters;

  useEffect(() => {
    function syncLocation() {
      const state = readGalleryQuery(
        new URLSearchParams(window.location.search),
      );
      setFilters(state.filters);
      setSelected(
        state.example &&
          source.some((example) => example.id === state.example?.id)
          ? state.example
          : null,
      );
    }
    syncLocation();
    window.addEventListener('popstate', syncLocation);
    return () => {
      window.removeEventListener('popstate', syncLocation);
      if (timer.current) clearTimeout(timer.current);
    };
  }, [source]);
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
      {!showLibrary && (
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
                  ambient={
                    example.orientation === 'portrait' && fit !== 'cover'
                  }
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
      )}
      {!showLibrary && (
        <div id="examples">
          {sectors.map((collection) => (
            <Fragment key={collection.id}>
              {collection.id === 'video-creation' && <McpConnections />}
              {collection.id === '3d-visuals' && <McpDots />}
              <GallerySector
                sector={collection}
                count={getSectorExamples(collection.id, galleryExamples).length}
              >
                <MasonryGallery>
                  {getSectorPreview(collection.id, galleryExamples).map(
                    (example) => (
                      <VideoCard
                        key={example.id}
                        example={example}
                        preview
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
                    ),
                  )}
                </MasonryGallery>
              </GallerySector>
            </Fragment>
          ))}
        </div>
      )}
      {showLibrary && (
        <section
          id="examples"
          className={`gallery-section ${libraryStyles.library}`}
          aria-labelledby="library-heading"
        >
          <h2 id="library-heading" className="sr-only">
            Explore the video library
          </h2>
          <div className="library-toolbar">
            <fieldset className="filter-list" aria-label="Filter by video type">
              <button
                type="button"
                className={
                  'filter-pill ' +
                  (!filters.technique && filters.category === 'All examples'
                    ? 'active'
                    : '')
                }
                aria-pressed={
                  !filters.technique && filters.category === 'All examples'
                }
                onClick={() =>
                  updateFilters({ technique: '', category: 'All examples' })
                }
              >
                {sector === 'video-editing'
                  ? 'All edits'
                  : sector === 'video-creation'
                    ? 'All creations'
                    : sector === '3d-visuals'
                      ? 'All 3D visuals'
                      : 'All styles'}
              </button>
              {availableTechniques.length > 1 &&
                availableTechniques.map((item) => (
                  <button
                    key={item.value}
                    type="button"
                    className={
                      'filter-pill ' +
                      (filters.technique === item.value ? 'active' : '')
                    }
                    aria-pressed={filters.technique === item.value}
                    onClick={() =>
                      updateFilters({
                        technique: item.value,
                        category: 'All examples',
                      })
                    }
                  >
                    {item.label}
                  </button>
                ))}
            </fieldset>
            <label className="library-search">
              <Search size={16} />
              <span className="sr-only">Search examples</span>
              <input
                type="search"
                placeholder="Search videos and prompts"
                value={filters.query}
                maxLength={200}
                onChange={(event) =>
                  updateFilters({ query: event.target.value })
                }
              />
            </label>
            <button
              type="button"
              className={libraryStyles.filters}
              aria-expanded={showFilters}
              aria-controls="library-filters"
              onClick={() => setShowFilters(!showFilters)}
            >
              <SlidersHorizontal size={16} /> Filters{' '}
              {filterCount > 0 && <span>{filterCount}</span>}
            </button>
          </div>
          <div className="library-layout">
            <aside
              id="library-filters"
              className="library-sidebar"
              aria-label="Refine examples"
              hidden={!showFilters}
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
                {availableTechniques.map((item) => {
                  const count = filterExamples(
                    {
                      ...filters,
                      technique: item.value,
                    },
                    source,
                  ).length;
                  return (
                    <label className="facet-option" key={item.value}>
                      <input
                        type="checkbox"
                        checked={filters.technique === item.value}
                        onChange={() =>
                          updateFilters({
                            technique:
                              filters.technique === item.value
                                ? ''
                                : item.value,
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
                    {facetOptions(field, source).map((item) => {
                      const count = filterExamples(
                        {
                          ...filters,
                          [field]: [item],
                        },
                        source,
                      ).length;
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
              <output className={libraryStyles.results}>
                {visible.length} {visible.length === 1 ? 'video' : 'videos'}
                {hasFilters ? ' found' : ''}
              </output>
              {filterCount > 0 && (
                <div className="active-filters" aria-label="Active filters">
                  {filters.category !== 'All examples' && (
                    <button
                      type="button"
                      onClick={() =>
                        updateFilters({ category: 'All examples' })
                      }
                    >
                      {filters.category}
                      <X size={11} />
                    </button>
                  )}
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
      )}
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
