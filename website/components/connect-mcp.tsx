'use client';

import { useEffect, useRef, useState } from 'react';
import { ArrowUpRight, Check, Copy, Plug, Terminal } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from '@/components/ui/dialog';
import { mcpUrl, repository } from '@/lib/gallery';

export function McpEndpoint() {
  const [copied, setCopied] = useState(false);
  const [manual, setManual] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  return (
    <div className="landing-endpoint">
      <label htmlFor="landing-mcp-url">Your connection URL</label>
      <div>
        <input
          id="landing-mcp-url"
          ref={input}
          readOnly
          value={mcpUrl}
          onFocus={(event) => event.target.select()}
        />
        <button
          type="button"
          onClick={async () => {
            try {
              await navigator.clipboard.writeText(mcpUrl);
              setCopied(true);
              setManual(false);
            } catch {
              setManual(true);
              input.current?.focus();
              input.current?.select();
            }
          }}
          aria-label="Copy Video Use MCP URL"
        >
          {copied ? <Check size={16} /> : <Copy size={16} />}
          <span>{copied ? 'Copied' : 'Copy URL'}</span>
        </button>
      </div>
      {manual && <output>Copy the selected URL above.</output>}
    </div>
  );
}

export function AgentMarks({ compact = false }: { compact?: boolean }) {
  return (
    <span
      className={`agent-marks ${compact ? 'compact' : ''}`}
      aria-hidden="true"
    >
      <span className="agent-mark chatgpt-mark">G</span>
      <span className="agent-mark claude-mark">C</span>
      <span className="agent-mark mcp-mark">
        <Plug size={compact ? 10 : 13} />
      </span>
    </span>
  );
}

export function ConnectMcp({
  className = '',
  label = 'Connect Video Use',
  compact = false,
}: {
  className?: string;
  label?: string;
  compact?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [client, setClient] = useState<'chatgpt' | 'claude' | 'local'>(
    'chatgpt',
  );
  const [copied, setCopied] = useState(false);
  const [manual, setManual] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const command = 'git clone https://github.com/browser-use/video-use.git';
  const value = client === 'local' ? command : mcpUrl;

  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );
  useEffect(() => {
    if (manual) input.current?.select();
  }, [manual]);
  useEffect(() => {
    if (!open) return;
    window.dispatchEvent(new CustomEvent('videouse:overlay', { detail: true }));
    return () => {
      window.dispatchEvent(
        new CustomEvent('videouse:overlay', { detail: false }),
      );
    };
  }, [open]);

  async function copy() {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setManual(false);
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => setCopied(false), 2400);
    } catch {
      setManual(true);
    }
  }

  return (
    <>
      <button
        type="button"
        className={`connect-button ${className}`}
        onClick={() => setOpen(true)}
        aria-label={
          compact
            ? 'Connect Video Use MCP to ChatGPT, Claude, or your own agent'
            : undefined
        }
      >
        {compact ? <AgentMarks compact /> : <Plug size={15} />}
        <span>{label}</span>
        {!compact && <ArrowUpRight size={15} />}
      </button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="connect-dialog">
          <span className="eyebrow">Bring your agent</span>
          <DialogTitle className="connect-title">
            Your chat. Your video studio.
          </DialogTitle>
          <DialogDescription className="connect-description">
            Connect Video Use once, then paste an example prompt into your chat
            and make it your own.
          </DialogDescription>
          <fieldset className="connection-tabs" aria-label="Choose your setup">
            {(['chatgpt', 'claude', 'local'] as const).map((item) => (
              <button
                type="button"
                key={item}
                aria-pressed={client === item}
                className={client === item ? 'active' : ''}
                onClick={() => {
                  setClient(item);
                  setCopied(false);
                  setManual(false);
                }}
              >
                {item === 'chatgpt'
                  ? 'ChatGPT'
                  : item === 'claude'
                    ? 'Claude'
                    : 'Open source'}
              </button>
            ))}
          </fieldset>
          <div className="endpoint-field">
            <label htmlFor={`endpoint-${client}`}>
              {client === 'local'
                ? 'Clone the repository'
                : 'Video Use MCP URL'}
            </label>
            <div>
              <input
                id={`endpoint-${client}`}
                ref={input}
                value={value}
                readOnly
                aria-label={
                  client === 'local'
                    ? 'Repository clone command'
                    : 'Video Use MCP server URL'
                }
                onFocus={(event) => event.target.select()}
              />
              <button
                type="button"
                onClick={copy}
                aria-label={
                  client === 'local' ? 'Copy clone command' : 'Copy MCP URL'
                }
              >
                {copied ? <Check size={17} /> : <Copy size={17} />}
              </button>
            </div>
            <output className="copy-status">
              {manual
                ? 'Select and copy the text above.'
                : copied
                  ? 'Copied to clipboard.'
                  : client === 'local'
                    ? 'Run this command in your terminal.'
                    : 'Connect with OAuth. No API key to paste here.'}
            </output>
          </div>
          {client === 'chatgpt' && (
            <ol className="connect-steps">
              <li>
                <span>01</span>
                <p>
                  In ChatGPT, enable <strong>Developer mode</strong> under
                  Settings → Security and login.
                </p>
              </li>
              <li>
                <span>02</span>
                <p>
                  Open{' '}
                  <a
                    href="https://chatgpt.com/plugins"
                    target="_blank"
                    rel="noreferrer"
                  >
                    Plugins <ArrowUpRight size={12} />
                  </a>
                  , select +, and add the MCP URL. Choose OAuth and sign in to
                  Video Use.
                </p>
              </li>
              <li>
                <span>03</span>
                <p>
                  Select Video Use in a new chat. Paste a prompt from this
                  library and add your subject or brand.
                </p>
              </li>
            </ol>
          )}
          {client === 'claude' && (
            <ol className="connect-steps">
              <li>
                <span>01</span>
                <p>
                  In Claude, open <strong>Customize → Connectors</strong> and
                  add a custom web connector.
                </p>
              </li>
              <li>
                <span>02</span>
                <p>
                  Name it Video Use, paste the MCP URL, and sign in with OAuth.
                  Use automatic client registration if asked.
                </p>
              </li>
              <li>
                <span>03</span>
                <p>
                  Enable Video Use from the + menu in your chat, then paste a
                  library prompt.
                </p>
              </li>
            </ol>
          )}
          {client === 'local' && (
            <div className="local-setup">
              <Terminal size={23} />
              <p>
                Use the open-source Video Use skill with a coding agent. Follow
                the repository setup for the runtime, rendering tools, and your
                model provider.
              </p>
              <a href={`${repository}#readme`} target="_blank" rel="noreferrer">
                Read the setup guide <ArrowUpRight size={14} />
              </a>
            </div>
          )}
          <p className="connection-note">
            {client === 'local'
              ? 'Library prompts are free. Running an agent or rendering video may use your provider’s paid resources.'
              : 'The hosted MCP is in private pilot and requires a Video Use account with access. Client availability depends on your plan and workspace. Library prompts are free.'}
          </p>
          {client !== 'local' && (
            <a
              className="setup-source"
              href={
                client === 'chatgpt'
                  ? 'https://developers.openai.com/plugins/deploy/connect-chatgpt'
                  : 'https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp'
              }
              target="_blank"
              rel="noreferrer"
            >
              {client === 'chatgpt'
                ? 'Official OpenAI connection guide'
                : 'Official Claude connection guide'}{' '}
              <ArrowUpRight size={12} />
            </a>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}

export function McpBanner() {
  return (
    <section
      className="mcp-banner"
      id="connect"
      aria-label="Make videos in your chat"
    >
      <div className="mcp-banner-copy">
        <span className="eyebrow">
          <Plug size={13} /> Video Use MCP
        </span>
        <h2>
          A little inspiration.
          <br />
          <em>A lot you can make.</em>
        </h2>
        <p>
          Pick a workflow. Copy its prompt. Bring it back to your agent with
          your own idea, assets, and context.
        </p>
      </div>
      <div className="mcp-banner-action">
        <div className="client-line">
          <AgentMarks />
          <span>ChatGPT · Claude · MCP clients</span>
        </div>
        <ConnectMcp className="primary-button" label="Set up Video Use" />
        <span className="quiet-note">Free prompts. Open-source toolkit.</span>
      </div>
    </section>
  );
}
