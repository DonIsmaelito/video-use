'use client';

/* oxlint-disable jsx-a11y/media-has-caption -- These are original published media, some silent and some with burned captions. Do not invent caption tracks for existing videos. */

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import {
  ArrowUpRight,
  Check,
  Copy,
  FileText,
  FolderCode,
  Link2,
  Play,
  Plug,
  Search,
  SlidersHorizontal,
  X,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Disclosure } from '@/components/ui/disclosure';
import { Hint } from '@/components/ui/hint';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from '@/components/ui/dialog';
import { AgentMarks, ConnectMcp } from '@/components/connect-mcp';
import { McpFeature } from '@/components/mcp-feature';
import { HowItWorks } from '@/components/hero';
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
    <article className="video-card" aria-label={example.title}>
      <button
        type="button"
        className="video-frame"
        onClick={open}
        aria-label={'Watch ' + example.title + ' and view its prompt'}
      >
        <PreviewMedia
          src={example.video}
          poster={example.poster}
          orientation={example.orientation}
          suspended={suspended}
        />
        <span className="video-shade" />
        <span className="video-duration">
          {formatDuration(example.duration)}
        </span>
        <span className="card-play" aria-hidden="true">
          <Play size={17} fill="currentColor" />
        </span>
        <span className="preview-label">
          View example <ArrowUpRight size={13} />
        </span>
      </button>
      <div className="card-heading">
        <button type="button" onClick={open}>
          {example.title}
        </button>
        <span className="card-technique">
          <TechniqueIcon technique={example.technique} size={12} />
          {example.technique === '3d'
            ? '3D'
            : example.technique === 'video-editing'
              ? 'Edit'
              : example.technique === 'diagrams'
                ? 'Explain'
                : 'Motion'}
        </span>
      </div>
      <div className="card-bottom">
        <button
          className={'copy-card ' + (copied ? 'copied' : '')}
          type="button"
          onClick={copy}
          aria-label={'Copy chat prompt for ' + example.title}
        >
          {copied ? <Check size={14} /> : <Copy size={14} />}{' '}
          {copied ? 'Copied' : 'Copy prompt'}
        </button>
        <Hint label="Use in your chat · Video Use MCP">
          <Link
            href="/mcp"
            className="card-mcp-icon"
            aria-label="Learn about Video Use MCP"
          >
            <Plug size={15} strokeWidth={1.7} />
          </Link>
        </Hint>
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
  const [showFilters, setShowFilters] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const manualText = useRef<HTMLTextAreaElement>(null);
  const visible = filterExamples(filters);
  const featuredCandidates = [
    ...examples.filter((example) => /^useful-0[12]-/.test(example.id)),
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
  const practicalExamples = visible.filter(
    (example) => example.hasWorkflowMetadata,
  );
  const sections = [
    {
      name: 'Useful workflows',
      items: practicalExamples,
    },
    ...categories.slice(1).map((category) => ({
      name: category,
      items: visible.filter(
        (example) =>
          example.category === category && !example.hasWorkflowMetadata,
      ),
    })),
  ];
  const selectedTags = selected ? Array.from(selected.useCases) : [];
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
        <div className="homepage-featured-heading">
          <span className="eyebrow">A few things you can make</span>
          <a href="#examples">
            Explore the library <ArrowUpRight size={12} />
          </a>
        </div>
        <div className="homepage-featured-grid">
          <McpFeature />
          {featuredExamples.map((example) => (
            <VideoCard
              key={example.id}
              example={example}
              open={() => openExample(example)}
              copy={() =>
                copyText(
                  buildChatPrompt(example),
                  example.id,
                  'Prompt copied. Paste it into your Video Use chat.',
                )
              }
              copied={copied === example.id}
              suspended={selected !== null || !!manualCopy}
            />
          ))}
        </div>
      </section>
      <HowItWorks />
      <section
        id="examples"
        className="gallery-section"
        aria-labelledby="library-heading"
      >
        <div className="library-heading">
          <div>
            <span className="eyebrow">The Video Use library</span>
            <h2 id="library-heading">
              Find your <em>starting point.</em>
            </h2>
          </div>
        </div>
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
                {item === 'All examples' ? 'All examples' : item}
                <span>
                  {filterExamples({ ...filters, category: item }).length}
                </span>
              </button>
            ))}
          </fieldset>
          <label className="library-search">
            <Search size={16} />
            <span className="sr-only">Search examples</span>
            <input
              type="search"
              placeholder="Find a workflow…"
              value={filters.query}
              maxLength={200}
              onChange={(event) => updateFilters({ query: event.target.value })}
            />
          </label>
          <button
            type="button"
            className={'mobile-filters ' + (showFilters ? 'active' : '')}
            aria-expanded={showFilters}
            aria-controls="library-filters"
            onClick={() => setShowFilters(!showFilters)}
          >
            <SlidersHorizontal size={15} /> Filters{' '}
            {filterCount ? '(' + filterCount + ')' : ''}
          </button>
        </div>
        <div className="library-layout">
          <aside
            id="library-filters"
            className={'library-sidebar ' + (showFilters ? 'is-open' : '')}
            aria-label="Refine examples"
          >
            <div className="sidebar-title">
              <span>Find your fit</span>
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
            <Link href="/mcp" className="sidebar-mcp">
              <AgentMarks />
              <span className="sidebar-mcp-link">
                Make it in your chat <ArrowUpRight size={13} />
              </span>
            </Link>
          </aside>
          <div className="library-content">
            <div className="results-line" aria-live="polite">
              <span>
                {visible.length} {visible.length === 1 ? 'example' : 'examples'}
                {hasFilters ? ' found' : ''}
              </span>
              <span>Free to make your own</span>
            </div>
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
            {sections.map(({ name: category, items }) => {
              if (!items.length) return null;
              const headingId =
                'category-' + category.toLowerCase().replaceAll(' ', '-');
              return (
                <section
                  key={category}
                  className="gallery-category"
                  aria-labelledby={headingId}
                >
                  <div className="category-heading">
                    <div>
                      <h3 id={headingId}>
                        {category}
                        <span>{items.length}</span>
                      </h3>
                    </div>
                  </div>
                  <div className="video-grid">
                    {items.map((example) => (
                      <VideoCard
                        key={example.id}
                        example={example}
                        open={() => openExample(example)}
                        copy={() =>
                          copyText(
                            buildChatPrompt(example),
                            example.id,
                            'Prompt copied. Paste it into your Video Use chat.',
                          )
                        }
                        copied={copied === example.id}
                        suspended={selected !== null || !!manualCopy}
                      />
                    ))}
                  </div>
                </section>
              );
            })}
            {!visible.length && (
              <div className="empty-results">
                <Search size={25} />
                <h3>No examples found yet.</h3>
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
                    loop={selected.category === 'Motion Design'}
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
              <span className="eyebrow">
                <FileText size={13} /> Free prompt
              </span>
              <DialogTitle className="detail-title">
                {selected.title}
              </DialogTitle>
              <DialogDescription className="detail-description">
                {selected.description}
              </DialogDescription>
              <div className="detail-tags">
                {selectedTags.slice(0, 2).map((item) => (
                  <span key={item}>{item}</span>
                ))}
              </div>
              <div className="detail-actions">
                <button
                  type="button"
                  className="primary-button"
                  onClick={() =>
                    copyText(
                      buildChatPrompt(selected),
                      selected.id,
                      'Prompt copied. Paste it into your Video Use chat.',
                    )
                  }
                >
                  {copied === selected.id ? (
                    <Check size={16} />
                  ) : (
                    <Copy size={16} />
                  )}
                  {copied === selected.id
                    ? 'Copied for your chat'
                    : 'Copy for my chat'}
                  <ArrowUpRight size={15} />
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
                <h3>Your prompt</h3>
                <span>
                  {selected.promptKind === 'Starter prompt'
                    ? 'Starter + chat context'
                    : 'Original brief + chat context'}
                </span>
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
          <DialogTitle>Copy for your chat</DialogTitle>
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
      {message && (
        <output className="toast-message">
          <Check size={14} />
          {message}
        </output>
      )}
    </>
  );
}
