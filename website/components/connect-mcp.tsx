'use client';

import { useEffect, useId, useRef, useState, type ReactNode } from 'react';
import Image from 'next/image';
import { ArrowUpRight, Check, Copy, Plug, Terminal, X } from 'lucide-react';
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from '@/components/ui/dialog';
import { mcpUrl, repository } from '@/lib/gallery';
import styles from './connect-mcp.module.css';

export function AgentMarks({ compact = false }: { compact?: boolean }) {
  return (
    <span
      className={`agent-marks ${compact ? 'compact' : ''}`}
      aria-hidden="true"
    >
      {(['chatgpt', 'claude', 'cursor'] as const).map((client) => (
        <span className={`agent-mark ${client}-mark`} key={client}>
          <Image
            src={`/clients/${client}.svg`}
            alt=""
            width={
              client === 'chatgpt' ? (compact ? 30 : 38) : compact ? 14 : 18
            }
            height={
              client === 'chatgpt' ? (compact ? 30 : 38) : compact ? 14 : 18
            }
            unoptimized
          />
        </span>
      ))}
    </span>
  );
}

type Client = 'chatgpt' | 'claude' | 'cursor' | 'local';

const clients = {
  chatgpt: {
    name: 'ChatGPT',
    guide: 'https://developers.openai.com/plugins/deploy/connect-chatgpt',
  },
  claude: {
    name: 'Claude',
    guide:
      'https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp',
  },
  cursor: {
    name: 'Cursor',
    guide: 'https://cursor.com/docs/mcp',
  },
  local: { name: 'Open source', guide: `${repository}#readme` },
} satisfies Record<Client, { name: string; guide: string }>;

export function ConnectMcp({
  className = '',
  label = 'Connect Video Use',
  compact = false,
  initialClient = 'chatgpt',
  children,
}: {
  className?: string;
  label?: string;
  compact?: boolean;
  initialClient?: Client;
  children?: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const [client, setClient] = useState<Client>(initialClient);
  const [copyState, setCopyState] = useState<'idle' | 'copied' | 'manual'>(
    'idle',
  );
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const selectedClient = useRef<HTMLButtonElement>(null);
  const copyAttempt = useRef(0);
  const fieldId = useId();
  const value =
    client === 'local'
      ? `git clone ${repository}.git`
      : client === 'cursor'
        ? JSON.stringify({ mcpServers: { 'video-use': { url: mcpUrl } } })
        : mcpUrl;
  const fieldLabel =
    client === 'local'
      ? 'Clone command'
      : client === 'cursor'
        ? 'Cursor configuration'
        : 'MCP server URL';

  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
      copyAttempt.current += 1;
    },
    [],
  );
  useEffect(() => {
    if (!open) return;
    window.dispatchEvent(new CustomEvent('videouse:overlay', { detail: true }));
    return () => {
      window.dispatchEvent(
        new CustomEvent('videouse:overlay', { detail: false }),
      );
    };
  }, [open]);

  function resetCopy() {
    copyAttempt.current += 1;
    if (timer.current) clearTimeout(timer.current);
    setCopyState('idle');
  }

  function changeOpen(nextOpen: boolean) {
    resetCopy();
    setOpen(nextOpen);
  }

  async function copy() {
    const attempt = ++copyAttempt.current;
    if (timer.current) clearTimeout(timer.current);
    try {
      await navigator.clipboard.writeText(value);
      if (attempt !== copyAttempt.current) return;
      setCopyState('copied');
      timer.current = setTimeout(() => setCopyState('idle'), 2400);
    } catch {
      if (attempt !== copyAttempt.current) return;
      setCopyState('manual');
      input.current?.focus();
      input.current?.select();
    }
  }

  return (
    <>
      <button
        ref={trigger}
        type="button"
        className={`connect-button ${className}`}
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={() => {
          setClient(initialClient);
          changeOpen(true);
        }}
        aria-label={
          children
            ? label
            : compact
              ? 'Connect Video Use MCP to ChatGPT, Claude, Cursor, or your own agent'
              : undefined
        }
      >
        {children ?? (
          <>
            {compact ? <AgentMarks compact /> : <Plug size={15} />}
            <span>{label}</span>
            {!compact && <ArrowUpRight size={15} />}
          </>
        )}
      </button>
      <Dialog open={open} onOpenChange={changeOpen}>
        <DialogContent
          className={styles.dialog}
          showCloseButton={false}
          initialFocus={selectedClient}
          finalFocus={trigger}
        >
          <header className={styles.header}>
            <div className={styles.heading}>
              <Image
                src="/brand/browser-use.svg"
                alt=""
                width={30}
                height={30}
              />
              <DialogTitle className={styles.title}>
                Connect Video Use
              </DialogTitle>
              <DialogClose className={styles.close} aria-label="Close">
                <X size={18} aria-hidden="true" />
              </DialogClose>
            </div>
            <DialogDescription className={styles.description}>
              Choose your app to get started.
            </DialogDescription>
          </header>

          <fieldset className={styles.clients} aria-label="Choose your setup">
            {(Object.keys(clients) as Client[]).map((item) => (
              <button
                ref={client === item ? selectedClient : undefined}
                type="button"
                key={item}
                aria-pressed={client === item}
                onClick={() => {
                  resetCopy();
                  setClient(item);
                }}
              >
                <span className={styles.clientIcon} aria-hidden="true">
                  {item === 'local' ? (
                    <Terminal size={25} />
                  ) : (
                    <Image
                      src={`/clients/${item}.svg`}
                      alt=""
                      className={
                        item === 'chatgpt' ? styles.openaiIcon : undefined
                      }
                      width={item === 'chatgpt' ? 54 : 27}
                      height={item === 'chatgpt' ? 54 : 27}
                      unoptimized
                    />
                  )}
                </span>
                {clients[item].name}
              </button>
            ))}
          </fieldset>

          <div className={styles.field}>
            <label htmlFor={fieldId}>{fieldLabel}</label>
            <div className={styles.copyRow}>
              <input
                id={fieldId}
                ref={input}
                value={value}
                readOnly
                spellCheck={false}
                aria-describedby={
                  copyState === 'manual' ? `${fieldId}-status` : undefined
                }
                onFocus={(event) => event.target.select()}
              />
              <button
                type="button"
                onClick={copy}
                aria-label={`Copy ${fieldLabel}`}
              >
                {copyState === 'copied' ? (
                  <Check size={14} />
                ) : (
                  <Copy size={14} />
                )}
                {copyState === 'copied' ? 'Copied' : 'Copy'}
              </button>
            </div>
            <output
              id={`${fieldId}-status`}
              className={copyState === 'manual' ? styles.copyHelp : 'sr-only'}
              aria-live="polite"
            >
              {copyState === 'manual'
                ? 'Copy the selected text with ⌘C or Ctrl+C.'
                : copyState === 'copied'
                  ? 'Copied to clipboard.'
                  : ''}
            </output>
          </div>

          <ol
            className={styles.steps}
            aria-label={`${clients[client].name} setup`}
          >
            {client === 'chatgpt' && (
              <>
                <li>
                  <p>
                    Open{' '}
                    <a
                      href="https://chatgpt.com/plugins"
                      target="_blank"
                      rel="noreferrer"
                    >
                      ChatGPT Plugins <ArrowUpRight size={12} />
                    </a>
                    , then <strong>+ → Add custom MCP server.</strong>
                  </p>
                </li>
                <li>
                  <p>
                    Name it <strong>Video Use</strong>, paste the URL, and
                    choose <strong>OAuth.</strong>
                  </p>
                </li>
                <li>
                  <p>
                    Create and install the plugin, then sign in. Choose{' '}
                    <strong>@Video Use</strong> in a new chat.
                  </p>
                </li>
              </>
            )}
            {client === 'claude' && (
              <>
                <li>
                  <p>
                    Open{' '}
                    <a
                      href="https://claude.ai/customize/connectors"
                      target="_blank"
                      rel="noreferrer"
                    >
                      Claude Connectors <ArrowUpRight size={12} />
                    </a>
                    , then <strong>Add custom connector.</strong>
                  </p>
                </li>
                <li>
                  <p>
                    Name it <strong>Video Use</strong>, paste the URL, and sign
                    in. Choose <strong>Register automatically</strong> if asked.
                  </p>
                </li>
                <li>
                  <p>
                    Enable <strong>Video Use</strong> from{' '}
                    <strong>+ → Connectors</strong> in your chat.
                  </p>
                </li>
              </>
            )}
            {client === 'cursor' && (
              <>
                <li>
                  <p>
                    Copy the configuration into <code>.cursor/mcp.json</code> in
                    your project. Keep any existing servers.
                  </p>
                </li>
                <li>
                  <p>
                    Save, then sign in to <strong>Video Use</strong> when Cursor
                    prompts you.
                  </p>
                </li>
                <li>
                  <p>
                    Open <strong>Agent</strong> and ask Video Use to create or
                    edit a video.
                  </p>
                </li>
              </>
            )}
            {client === 'local' && (
              <>
                <li>
                  <p>Copy the command and run it in your terminal.</p>
                </li>
                <li>
                  <p>
                    Follow the{' '}
                    <a
                      href={`${repository}#readme`}
                      target="_blank"
                      rel="noreferrer"
                    >
                      repository setup <ArrowUpRight size={12} />
                    </a>{' '}
                    for your agent, model, and rendering tools.
                  </p>
                </li>
                <li>
                  <p>
                    Ask your agent to use <strong>Video Use</strong> with your
                    footage or an idea.
                  </p>
                </li>
              </>
            )}
          </ol>

          <footer className={styles.footer}>
            <p>
              {client === 'local'
                ? 'Open source. Model and rendering costs apply.'
                : 'Video Use pilot access required.'}
            </p>
            <a
              href={clients[client].guide}
              target="_blank"
              rel="noreferrer"
              aria-label={`${clients[client].name} setup guide`}
            >
              Setup guide <ArrowUpRight size={13} aria-hidden="true" />
            </a>
          </footer>
          {client === 'cursor' && (
            <p className={styles.note}>
              Cursor setup is not yet verified end to end.
            </p>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
