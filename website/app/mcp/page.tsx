import type { Metadata } from 'next';
import Link from 'next/link';
import {
  ArrowDown,
  ArrowUpRight,
  Check,
  Clapperboard,
  MessageSquare,
  Play,
  WandSparkles,
} from 'lucide-react';
import { AgentMarks, ConnectMcp, McpEndpoint } from '@/components/connect-mcp';
import { McpLaunch } from '@/components/mcp-launch';
import { SiteHeader } from '@/components/site-header';
import { Wordmark } from '@/components/wordmark';
import { repository } from '@/lib/gallery';

export const metadata: Metadata = {
  title: 'Video Use MCP — Your chat is a video studio',
  description:
    'Bring Video Use into your conversation. Find a direction, review a preview, and create or edit a video with your agent. Private pilot.',
};

const workflows = [
  {
    icon: WandSparkles,
    label: 'Motion with a message',
    text: 'Product launches, feature updates, and brand stories.',
    href: '/?technique=motion-design#examples',
  },
  {
    icon: Clapperboard,
    label: 'More from your footage',
    text: 'Cutdowns, captions, and a better edit.',
    href: '/?technique=video-editing#examples',
  },
  {
    icon: MessageSquare,
    label: 'Make something clear',
    text: 'Diagrams and explainers that make an idea click.',
    href: '/?technique=diagrams#examples',
  },
];

export default function McpPage() {
  return (
    <main className="mcp-page">
      <a className="skip-link" href="#mcp-how">
        Skip to how Video Use MCP works
      </a>
      <SiteHeader mcp />
      <section className="mcp-hero">
        <div className="mcp-hero-copy">
          <span className="eyebrow">
            <span className="status-dot" /> Video Use MCP · Private pilot
          </span>
          <h1>
            Your chat.
            <br />
            <em>Your video studio.</em>
          </h1>
          <p>Create and edit video, right in your conversation.</p>
          <div className="hero-actions">
            <ConnectMcp className="primary-button" label="Connect your chat" />
            <a className="text-link" href="#mcp-how">
              See how it works <ArrowDown size={15} />
            </a>
          </div>
          <div className="client-line">
            <AgentMarks />
            <span>ChatGPT · Claude · Cursor guides</span>
          </div>
        </div>
        <div className="mcp-hero-media">
          <McpLaunch />
          <div className="mcp-media-caption">
            <span>Idea → direction → preview → video</span>
            <span>Powered by Video Use</span>
          </div>
        </div>
      </section>
      <section id="mcp-how" className="mcp-how">
        <div className="mcp-section-heading">
          <span className="eyebrow">How it works</span>
          <h2>
            An idea.
            <br />
            <em>Then a video.</em>
          </h2>
        </div>
        <div className="mcp-steps">
          <article>
            <span className="step-number">01</span>
            <span className="mcp-step-icon">
              <MessageSquare size={22} />
            </span>
            <h3>Bring your idea</h3>
            <p>Share the goal, audience, and any footage.</p>
          </article>
          <article>
            <span className="step-number">02</span>
            <span className="mcp-step-icon">
              <WandSparkles size={22} />
            </span>
            <h3>Choose a direction</h3>
            <p>Bring a reference or borrow a library prompt.</p>
          </article>
          <article>
            <span className="step-number">03</span>
            <span className="mcp-step-icon">
              <Play size={22} />
            </span>
            <h3>See a preview</h3>
            <p>In hands-on mode, approve a snippet before the full film.</p>
          </article>
          <article>
            <span className="step-number">04</span>
            <span className="mcp-step-icon">
              <Check size={22} />
            </span>
            <h3>Make it yours</h3>
            <p>Refine it in chat. Keep the video and editable project.</p>
          </article>
        </div>
      </section>
      <section className="mcp-connection" id="setup">
        <div>
          <span className="eyebrow">Get connected</span>
          <h2>
            One setup.
            <br />
            <em>Keep the conversation.</em>
          </h2>
          <p>Add the MCP, sign in, and start a conversation.</p>
          <ConnectMcp className="primary-button" label="Choose your chat app" />
        </div>
        <div className="mcp-setup-card">
          <AgentMarks />
          <McpEndpoint />
          <div className="connection-facts">
            <span>
              <Check size={13} /> OAuth sign-in
            </span>
            <span>
              <Check size={13} /> Your projects
            </span>
            <span>
              <Check size={13} /> Hands-on previews
            </span>
          </div>
          <p>
            Private pilot. A Video Use account with access is required.
            Availability varies by client and workspace.
          </p>
        </div>
      </section>
      <section className="mcp-workflows">
        <div className="mcp-section-heading">
          <span className="eyebrow">Made for real work</span>
          <h2>
            What will you <em>make?</em>
          </h2>
          <Link href="/#examples" className="text-link">
            Explore every example <ArrowUpRight size={14} />
          </Link>
        </div>
        <div className="workflow-grid">
          {workflows.map((item) => (
            <Link href={item.href} key={item.label}>
              <span className="workflow-icon">
                <item.icon size={23} />
              </span>
              <h3>{item.label}</h3>
              <p>{item.text}</p>
              <span>
                Find a prompt <ArrowUpRight size={14} />
              </span>
            </Link>
          ))}
        </div>
      </section>
      <section className="mcp-faq">
        <div>
          <span className="eyebrow">Good to know</span>
          <h2>
            Before you
            <br />
            <em>press play.</em>
          </h2>
        </div>
        <div className="faq-items">
          <details>
            <summary>Do I need the MCP to use this library?</summary>
            <p>
              No. Prompts are free to copy. You can run the open-source skill
              with a coding agent and your own runtime, or connect through the
              MCP.
            </p>
          </details>
          <details>
            <summary>Will copying a prompt start a render?</summary>
            <p>
              No. Paste it into a chat with Video Use enabled. Your context,
              approval choices, and involvement mode still apply.
            </p>
          </details>
          <details>
            <summary>Which chat apps can I connect?</summary>
            <p>
              The guides cover ChatGPT, Claude, and Cursor with OAuth. Account
              and workspace requirements vary. Other clients must support the
              server’s transport and authentication. Cursor has not yet had an
              end-to-end test with this pilot.
            </p>
          </details>
          <details>
            <summary>Is Video Use free?</summary>
            <p>
              The prompts and toolkit are free. Model and rendering costs depend
              on your setup. The hosted MCP is a private pilot.
            </p>
          </details>
          <details>
            <summary>Can I use a reference I already like?</summary>
            <p>
              Yes. Your agent inspects it, adapts it to your request, and shows
              a snippet for approval in hands-on mode.
            </p>
          </details>
        </div>
      </section>
      <section className="mcp-open-source">
        <div>
          <span className="eyebrow">Built in the open</span>
          <h2>
            The same toolkit.
            <br />
            <em>However you make.</em>
          </h2>
        </div>
        <a
          className="primary-button"
          href={repository}
          target="_blank"
          rel="noreferrer"
        >
          Get Video Use on GitHub <ArrowUpRight size={15} />
        </a>
      </section>
      <Wordmark />
    </main>
  );
}
