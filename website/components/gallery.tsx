'use client';

/* oxlint-disable jsx-a11y/media-has-caption -- These are original published media, some silent and some with burned captions. Do not invent caption tracks for existing videos. */

import { useEffect, useRef, useState } from 'react';
import {
  ArrowUpRight,
  Check,
  Copy,
  FolderCode,
  Link2,
  Heart,
  Maximize2,
  Search,
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
import { ConnectMcp } from '@/components/connect-mcp';
import { McpFeature } from '@/components/mcp-feature';
import {
  useGalleryLikes,
  type LikeState,
} from '@/components/use-gallery-likes';
import { PreviewMedia } from '@/components/preview-media';
import { TechniqueIcon } from '@/components/technique-icon';
import {
  buildChatPrompt,
  categories,
  defaultFilters,
  examples,
  exampleLink,
  facetOptions,
  filterExamples,
  formatDuration,
  readGalleryQuery,
  safeSourceUrl,
  techniqueLabel,
  techniqueOptions,
  writeGalleryQuery,
  type Filters,
  type GalleryExample,
} from '@/lib/gallery';

// Mix footage, product films and graphic work in the opening row without changing
// the source catalog or its provenance. Filters and deep links still use all films.
const openingIds = [
  'cloud-edit-travel',
  'useful-08-refill-product',
  'cloud-edit-podcast',
  'useful-07-workshop-invite',
  'useful-09-cafe-promo',
  'useful-19-fulfilment-flow',
];
const galleryExamples = [
  ...openingIds.flatMap((id) =>
    examples.filter((example) => example.id === id),
  ),
  ...examples.filter((example) => !openingIds.includes(example.id)),
];

function VideoCard({
  example,
  open,
  copy,
  copied,
  suspended,
  like,
  liking,
  toggleLike,
}: {
  example: GalleryExample;
  open: () => void;
  copy: () => void;
  copied: boolean;
  suspended: boolean;
  like?: LikeState;
  liking: boolean;
  toggleLike: () => void;
}) {
  return (
    <article className="video-card" aria-label={example.title}>
      <button
        type="button"
        className={`video-frame ${example.orientation}`}
        onClick={open}
        aria-label={'Watch ' + example.title + ' and view its prompt'}
      >
        <PreviewMedia
          src={example.video}
          poster={example.poster}
          orientation={example.orientation}
          suspended={suspended}
          ambient
        />
        <span className="video-shade" />
        <span className="card-caption">{example.title}</span>
      </button>
      <span className="video-duration">{formatDuration(example.duration)}</span>
      <button
        type="button"
        className={`like-button ${like?.liked ? 'is-liked' : ''}`}
        aria-label={`${like?.liked ? 'Unlike' : 'Like'} ${example.title}`}
        aria-pressed={like?.liked ?? false}
        disabled={liking}
        onClick={toggleLike}
      >
        <span>{like ? like.count.toLocaleString() : '–'}</span>
        <Heart size={17} fill={like?.liked ? 'currentColor' : 'none'} />
      </button>
      <div className="card-actions">
        <button
          className={'copy-card ' + (copied ? 'copied' : '')}
          type="button"
          onClick={copy}
          aria-label={'Copy prompt for ' + example.title}
        >
          {copied ? <Check size={14} /> : <Copy size={14} />}{' '}
          {copied ? 'Copied' : 'Copy Prompt'}
        </button>
        <button
          type="button"
          className="expand-card"
          onClick={open}
          aria-label={`Expand ${example.title}`}
        >
          <Maximize2 size={16} />
        </button>
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
  const [videoError, setVideoError] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const manualText = useRef<HTMLTextAreaElement>(null);
  const visible = filterExamples(filters, galleryExamples);
  const { likes, pending, toggle } = useGalleryLikes(notify);
  const featuredCandidates = [
    ...examples.filter(
      (example) => example.id === 'whiplash-cinematic-story-edit',
    ),
    ...examples.filter((example) => example.id === 'useful-02-modular-desk'),
    ...examples.filter((example) => example.hasWorkflowMetadata),
    ...examples.filter((example) => example.id.startsWith('practical-')),
  ];
  const featuredExamples = featuredCandidates
    .filter(
      (example, index) =>
        featuredCandidates.findIndex((item) => item.id === example.id) ===
        index,
    )
    .slice(0, 2);
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
      setVideoError(false);
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

  function notify(text: string) {
    setMessage(text);
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      setMessage('');
      setCopied('');
    }, 2600);
  }

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
    setVideoError(false);
    writeLocation(filters, example.id, true);
  }

  function closeExample() {
    setSelected(null);
    if (window.history.state?.videoUseExample) window.history.back();
    else writeLocation(filters, null);
  }

  return (
    <>
      <section
        className="homepage-featured"
        aria-label="Featured Video Use workflows"
      >
        <div className="homepage-featured-grid">
          <McpFeature suspended={selected !== null || !!manualCopy} />
          {featuredExamples.map((example, index) => (
            <article className="featured-card" key={example.id}>
              <button
                type="button"
                className="featured-frame"
                onClick={() => openExample(example)}
                aria-label={`Watch ${example.title}`}
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
                  {index === 0 ? 'Cinematic edits' : 'Ideas in motion'}
                </button>
                <span>
                  {index === 0 ? 'Find your rhythm' : 'Make it move'}{' '}
                  <ArrowUpRight size={14} />
                </span>
              </div>
            </article>
          ))}
        </div>
      </section>
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
            <div className="sidebar-title">
              <span>Browse</span>
              {hasFilters && (
                <button
                  type="button"
                  onClick={() => updateFilters(defaultFilters)}
                >
                  Reset
                </button>
              )}
            </div>
            <fieldset className="facet-group">
              <legend>Video type</legend>
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
            {(['audiences', 'useCases'] as const).map((field) => (
              <Disclosure
                key={field}
                label={field === 'audiences' ? 'Audience' : 'Use case'}
                defaultOpen={field === 'audiences'}
                className="facet-disclosure"
              >
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
              </Disclosure>
            ))}
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
            <div className="video-grid">
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
                  like={likes[example.id]}
                  liking={pending.has(example.id)}
                  toggleLike={() => toggle(example.id)}
                />
              ))}
            </div>
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
          <DialogContent className="example-dialog">
            <div className="detail-preview">
              <div className={'dialog-video ' + selected.orientation}>
                {!videoError ? (
                  <video
                    key={selected.id}
                    src={selected.video}
                    poster={selected.poster}
                    controls
                    playsInline
                    autoPlay
                    muted={selected.category === 'Motion Design'}
                    loop={selected.loop ?? selected.category === 'Motion Design'}
                    preload="metadata"
                    onError={() => setVideoError(true)}
                  />
                ) : (
                  <div className="video-error">
                    <p>This preview couldn’t load.</p>
                    <a href={selected.video} target="_blank" rel="noreferrer">
                      Open the video directly <ArrowUpRight size={14} />
                    </a>
                  </div>
                )}
              </div>
              <div className="detail-facts">
                <span className="detail-technique">
                  <TechniqueIcon technique={selected.technique} />
                  {techniqueLabel(selected.technique)}
                </span>
                <span>{formatDuration(selected.duration)}</span>
                <span>
                  {selected.orientation === 'portrait'
                    ? 'Portrait'
                    : selected.orientation === 'square'
                      ? 'Square'
                      : 'Landscape'}
                </span>
              </div>
              <div className="detail-workflow">
                <a
                  href="https://github.com/browser-use/video-use"
                  target="_blank"
                  rel="noreferrer"
                >
                  Video Use <ArrowUpRight size={12} />
                </a>
                <ConnectMcp label="Connect your chat" compact />
              </div>
              {[
                'edit-velocity',
                'edit-freeze_poster',
                'edit-triptych',
                'edit-after_dark',
              ].includes(selected.id) && (
                <p className="media-attribution">
                  Modified excerpt from{' '}
                  <a
                    href="https://www.youtube.com/watch?v=R6MlUcmOul8"
                    target="_blank"
                    rel="noreferrer"
                  >
                    Tears of Steel
                  </a>{' '}
                  · (CC) Blender Foundation |{' '}
                  <a
                    href="https://mango.blender.org/"
                    target="_blank"
                    rel="noreferrer"
                  >
                    mango.blender.org
                  </a>{' '}
                  ·{' '}
                  <a
                    href="https://creativecommons.org/licenses/by/3.0/"
                    target="_blank"
                    rel="noreferrer"
                  >
                    CC BY 3.0
                  </a>
                </p>
              )}
            </div>
            <div className="detail-body">
              <DialogTitle className="detail-title">
                {selected.title}
              </DialogTitle>
              <DialogDescription className="sr-only">
                {selected.description}
              </DialogDescription>
              <div className="detail-actions">
                <button
                  type="button"
                  className="primary-button"
                  onClick={() =>
                    copyText(
                      buildChatPrompt(selected),
                      selected.id,
                      'Prompt copied',
                    )
                  }
                >
                  {copied === selected.id ? (
                    <Check size={16} />
                  ) : (
                    <Copy size={16} />
                  )}
                  {copied === selected.id ? 'Copied' : 'Copy Prompt'}
                </button>
                <button
                  type="button"
                  className={`detail-like ${likes[selected.id]?.liked ? 'is-liked' : ''}`}
                  onClick={() => toggle(selected.id)}
                  disabled={pending.has(selected.id)}
                  aria-label={`${likes[selected.id]?.liked ? 'Unlike' : 'Like'} ${selected.title}`}
                  aria-pressed={likes[selected.id]?.liked ?? false}
                >
                  <Heart
                    size={17}
                    fill={likes[selected.id]?.liked ? 'currentColor' : 'none'}
                  />
                  {likes[selected.id]?.count.toLocaleString() ?? '–'}
                </button>
                <button
                  type="button"
                  className="share-example"
                  aria-label="Copy link to this example"
                  onClick={() =>
                    copyText(
                      exampleLink(window.location.origin, selected.id),
                      'link-' + selected.id,
                      'Example link copied.',
                    )
                  }
                >
                  {copied === 'link-' + selected.id ? (
                    <Check size={16} />
                  ) : (
                    <Link2 size={16} />
                  )}
                </button>
              </div>
              <div className="prompt-heading">
                <h3>{selected.promptKind}</h3>
              </div>
              <textarea
                className="prompt-text"
                readOnly
                rows={7}
                aria-label="Complete prompt that will be copied"
                value={buildChatPrompt(selected)}
              />
              <Disclosure
                label="Details & sources"
                icon={<FolderCode size={16} />}
                className="source-disclosure"
              >
                <p className="detail-description">{selected.description}</p>
                <div className="detail-audience">
                  <span>Useful for</span>
                  {selected.audiences.map((item) => (
                    <span key={item}>{item}</span>
                  ))}
                </div>
                {(selected.promptSource ||
                  safeSourceUrl(selected.sourceRepo)) && (
                  <p className="prompt-source">
                    {selected.promptSource}
                    {safeSourceUrl(selected.sourceRepo) && (
                      <a
                        href={safeSourceUrl(selected.sourceRepo)!}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Open-source inspiration <ArrowUpRight size={11} />
                      </a>
                    )}
                  </p>
                )}
                {(safeSourceUrl(selected.sourceArchive) ||
                  safeSourceUrl(selected.reviewUrl)) && (
                  <div className="project-resources">
                    {safeSourceUrl(selected.sourceArchive) && (
                      <a
                        href={safeSourceUrl(selected.sourceArchive)!}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Editable project <ArrowUpRight size={11} />
                      </a>
                    )}
                    {safeSourceUrl(selected.reviewUrl) && (
                      <a
                        href={safeSourceUrl(selected.reviewUrl)!}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Production notes <ArrowUpRight size={11} />
                      </a>
                    )}
                  </div>
                )}
              </Disclosure>
            </div>
          </DialogContent>
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
