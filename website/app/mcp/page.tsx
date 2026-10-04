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
    text: 'Animate a product launch, a feature update, or an idea worth explaining.',
    href: '/?technique=motion-design#examples',
  },
  {
    icon: Clapperboard,
    label: 'More from your footage',
    text: 'Turn a long recording into a useful clip. Tighten the pacing, reframe, and caption.',
    href: '/?technique=video-editing#examples',
  },
  {
    icon: MessageSquare,
    label: 'Make something clear',
    text: 'Use diagrams and visual steps to help people understand how something works.',
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
          <p>
            Bring the idea. Your agent finds a direction, creates a preview, and
            helps you make a video that feels like yours.
          </p>
          <div className="hero-actions">
            <ConnectMcp className="primary-button" label="Connect your chat" />
            <a className="text-link" href="#mcp-how">
              See how it works <ArrowDown size={15} />
            </a>
          </div>
          <div className="client-line">
            <AgentMarks />
            <span>Connection guides for ChatGPT & Claude</span>
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
          <span className="eyebrow">A conversation, all the way through</span>
          <h2>
            From “what if”
            <br />
            <em>to something you can watch.</em>
          </h2>
        </div>
        <div className="mcp-steps">
          <article>
            <span className="step-number">01</span>
            <MessageSquare size={22} />
            <h3>Tell it what you need</h3>
            <p>
              Share your goal, audience, and assets. Choose motion design, 3D,
              an explainer, or an edit of your footage.
            </p>
          </article>
          <article>
            <span className="step-number">02</span>
            <WandSparkles size={22} />
            <h3>Find your direction</h3>
            <p>
              Bring a reference or copy a prompt from the library. Your agent
              adapts the treatment to your subject and context.
            </p>
          </article>
          <article>
            <span className="step-number">03</span>
            <Play size={22} />
            <h3>See a little first</h3>
            <p>
              In hands-on mode, review a short snippet. Refine the details, then
              approve continuing to the full video.
            </p>
          </article>
          <article>
            <span className="step-number">04</span>
            <Check size={22} />
            <h3>Make it yours</h3>
            <p>
              Continue the conversation to refine the result and get the
              finished video. Your project stays with your work.
            </p>
          </article>
        </div>
      </section>
      <section className="mcp-connection" id="setup">
        <div>
          <span className="eyebrow">
            A small connection. A new possibility.
          </span>
          <h2>
            One setup.
            <br />
            <em>Keep the conversation.</em>
          </h2>
          <p>
            Add Video Use as a remote MCP connection, sign in, and select it in
            your chat. The setup guide walks through each client.
          </p>
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
              <Check size={13} /> Your own projects
            </span>
            <span>
              <Check size={13} /> Preview before approval
            </span>
          </div>
          <p>
            The hosted MCP is a private pilot. You need a Video Use account with
            access; an invite may be required. Client availability depends on
            your account and workspace.
          </p>
        </div>
      </section>
      <section className="mcp-workflows">
        <div className="mcp-section-heading">
          <span className="eyebrow">A useful place to start</span>
          <h2>
            Give it something <em>worth making.</em>
          </h2>
          <Link href="/#examples" className="text-link">
            Explore every example <ArrowUpRight size={14} />
          </Link>
        </div>
        <div className="workflow-grid">
          {workflows.map((item) => (
            <Link href={item.href} key={item.label}>
              <item.icon size={23} />
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
          <span className="eyebrow">A few useful details</span>
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
              No. Every example prompt is free to copy. You can also use the
              open-source Video Use skill with a coding agent and your own
              runtime. The MCP is another way to bring the tools into your chat.
            </p>
          </details>
          <details>
            <summary>Will copying a prompt start a render?</summary>
            <p>
              No. Copying only puts text on your clipboard. Paste it into a chat
              with Video Use enabled, add your context, and continue from there.
              Your approval and involvement mode still apply.
            </p>
          </details>
          <details>
            <summary>Which chat apps can I connect?</summary>
            <p>
              The setup guide covers ChatGPT and Claude using a remote MCP
              connection with OAuth. Each client has its own account and
              workspace requirements. Other MCP clients must support the
              server’s transport and authentication.
            </p>
          </details>
          <details>
            <summary>Is Video Use free?</summary>
            <p>
              The library prompts and open-source toolkit are free. Your model
              provider and rendering infrastructure may have their own costs.
              Hosted MCP access is currently limited to the private pilot.
            </p>
          </details>
          <details>
            <summary>Can I use a reference I already like?</summary>
            <p>
              Yes. Bring a video reference or choose a library example. Your
              agent should inspect the reference, adapt it to your request, and
              show a snippet in hands-on mode before making the full video.
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
        <p>
          Explore the source, run Video Use with your agent, and make the
          workflow your own.
        </p>
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
