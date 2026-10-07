import type { Metadata } from 'next';
import Image from 'next/image';
import Link from 'next/link';
import {
  ArrowDown,
  ArrowUpRight,
  Captions,
  Check,
  Clapperboard,
  Code2,
  Film,
  Layers3,
  Plus,
  Sparkles,
} from 'lucide-react';
import { ConnectMcp } from '@/components/connect-mcp';
import { McpCopy } from '@/components/mcp-copy';
import { McpLaunch } from '@/components/mcp-launch';
import { SiteHeader } from '@/components/site-header';
import { Wordmark } from '@/components/wordmark';
import { mcpUrl, repository } from '@/lib/gallery';
import styles from './page.module.css';

export const metadata: Metadata = {
  title: 'Video Use MCP — Create and edit video in your AI chat',
  description:
    'Connect Video Use to your AI agent. Create motion graphics, edit footage, and refine a video in conversation. Hosted MCP private pilot.',
};

const prompts = [
  {
    icon: Sparkles,
    label: 'Product launches',
    title: 'Give your product a launch moment',
    prompt:
      'Create a 15-second launch film for this product. Use our brand colors, reveal the main benefit, and finish on the product name. Show me a short preview first.',
    bring: 'A product, a brief, and your brand',
    href: '/?useCase=Product+launches#examples',
  },
  {
    icon: Clapperboard,
    label: 'Video editing',
    title: 'Find the story in your footage',
    prompt:
      'Turn these clips into a tight 30-second edit. Keep the strongest moments, cut the pauses, and make the ending feel intentional.',
    bring: 'Your footage',
    href: '/?technique=video-editing#examples',
  },
  {
    icon: Captions,
    label: 'Social clips',
    title: 'Make the part worth sharing',
    prompt:
      'Find one strong moment in this interview and make a vertical clip. Keep the speaker in frame and add clear, readable captions.',
    bring: 'An interview or recording',
    href: '/?q=captions#examples',
  },
  {
    icon: Layers3,
    label: 'Explainers',
    title: 'Make a complicated idea click',
    prompt:
      'Explain this idea with a simple animated diagram. Introduce one concept at a time and keep the labels easy to read.',
    bring: 'The idea you want to explain',
    href: '/?technique=diagrams#examples',
  },
];

const faqs = [
  {
    question: 'What can I make with Video Use?',
    answer:
      'Create motion graphics and explainers, or edit footage with cuts, captions, color, and overlays. Bring a prompt, a reference, or an existing project and refine the result in conversation.',
  },
  {
    question: 'Which agents can I connect?',
    answer:
      'Setup guides are available for ChatGPT, Claude, and Cursor. Your client must support remote MCP and OAuth. Availability depends on your account and workspace; the Cursor pilot has not yet been tested end to end.',
  },
  {
    question: 'Do I need an API key?',
    answer:
      'The hosted MCP uses OAuth sign-in. You need a Video Use account with pilot access. The open-source toolkit runs in your own environment and may need model-provider credentials for the tools you choose.',
  },
  {
    question: 'Can I choose the direction before the full video?',
    answer:
      'Yes. In hands-on mode, review a short snippet before the full render. You can also tell your agent how much creative freedom you want to give it.',
  },
  {
    question: 'Is Video Use free?',
    answer:
      'The toolkit and library prompts are free. Model and rendering costs depend on your setup. The hosted MCP is currently a private pilot.',
  },
  {
    question: 'Can I keep editing the same project?',
    answer:
      'Yes. Continue the conversation with your project. Keep the exported video and its editable source so you can revisit the copy, timing, and visual direction.',
  },
];

export default function McpPage() {
  return (
    <main className={styles.page}>
      <a className="skip-link" href="#mcp-how">
        Skip to how Video Use MCP works
      </a>
      <SiteHeader active="mcp" />
      <section className={styles.hero} aria-labelledby="mcp-heading">
        <span className={styles.badge}>
          <span /> Model Context Protocol
        </span>
        <h1 id="mcp-heading">
          Video Use MCP for
          <br />
          <span>your AI agent.</span>
        </h1>
        <p className={styles.intro}>
          Create and edit video from the chat you already use.
          <br className={styles.desktopBreak} /> Bring an idea. Find a
          direction. Make it move.
        </p>
        <div className={styles.heroConnect}>
          <McpCopy value={mcpUrl} label="Video Use MCP URL" />
          <a className={styles.quietLink} href="#setup">
            Choose your chat app <ArrowDown size={14} />
          </a>
        </div>
        <div className={styles.film}>
          <McpLaunch />
        </div>
        <ul className={styles.facts} aria-label="Video Use features">
          {[
            'OAuth sign-in',
            'Video editing',
            'Motion design',
            'Editable projects',
          ].map((fact) => (
            <li key={fact}>
              <Check size={14} />
              {fact}
            </li>
          ))}
        </ul>
      </section>

      <section
        id="mcp-how"
        className={styles.section}
        aria-labelledby="how-heading"
      >
        <div className={styles.sectionHeading}>
          <h2 id="how-heading">From a thought to a film.</h2>
          <p>Three steps. All in your conversation.</p>
        </div>
        <ol className={styles.steps}>
          <li>
            <span className={styles.stepNumber}>1</span>
            <h3>Connect your agent</h3>
            <p>
              Add Video Use in your client’s MCP settings, then sign in with
              your pilot account.
            </p>
            <a className={styles.cardLink} href="#setup">
              Find your setup <ArrowDown size={15} />
            </a>
          </li>
          <li>
            <span className={styles.stepNumber}>2</span>
            <h3>Bring your idea</h3>
            <p>
              Share your goal, a reference, or some footage. Your agent helps
              shape the direction.
            </p>
            <div className={styles.examplePrompt}>
              “Make a launch video for my product.”
            </div>
          </li>
          <li>
            <span className={styles.stepNumber}>3</span>
            <h3>Preview. Refine. Export.</h3>
            <p>
              Review a snippet in hands-on mode. Keep refining in chat, then
              take the video and editable project.
            </p>
            <Link className={styles.cardLink} href="/#examples">
              See what you can make <ArrowUpRight size={15} />
            </Link>
          </li>
        </ol>
      </section>

      <section
        id="setup"
        className={styles.section}
        aria-labelledby="setup-heading"
      >
        <div className={styles.sectionHeading}>
          <span className={styles.kicker}>One connection</span>
          <h2 id="setup-heading">Your agent. Your setup.</h2>
          <p>
            Add the server in your client’s settings, then sign in with OAuth.
          </p>
        </div>
        <div className={styles.clients}>
          <article className={styles.clientCard}>
            <div className={styles.clientHeading}>
              <span className={styles.clientIcon}>
                <Image
                  src="/clients/chatgpt.svg"
                  alt=""
                  width={54}
                  height={54}
                  unoptimized
                />
              </span>
              <div>
                <span className={styles.kicker}>Chat</span>
                <h3>ChatGPT</h3>
              </div>
            </div>
            <p>
              Add Video Use as a custom MCP app with OAuth in a workspace that
              supports developer mode.
            </p>
            <McpCopy value={mcpUrl} label="ChatGPT server URL" code />
            <ConnectMcp
              initialClient="chatgpt"
              className={styles.setupButton}
              label="ChatGPT setup"
            />
          </article>
          <article className={styles.clientCard}>
            <div className={styles.clientHeading}>
              <span className={styles.clientIcon}>
                <Image
                  src="/clients/claude.svg"
                  alt=""
                  width={28}
                  height={28}
                  unoptimized
                />
              </span>
              <div>
                <span className={styles.kicker}>Desktop & web</span>
                <h3>Claude</h3>
              </div>
            </div>
            <p>
              Add a custom connector, paste the server URL, and complete the
              Video Use sign-in.
            </p>
            <McpCopy value={mcpUrl} label="Claude server URL" code />
            <ConnectMcp
              initialClient="claude"
              className={styles.setupButton}
              label="Claude setup"
            />
          </article>
          <article className={styles.clientCard}>
            <div className={styles.clientHeading}>
              <span className={styles.clientIcon}>
                <Image
                  src="/clients/cursor.svg"
                  alt=""
                  width={28}
                  height={28}
                  unoptimized
                />
              </span>
              <div>
                <span className={styles.kicker}>Editor</span>
                <h3>Cursor</h3>
              </div>
            </div>
            <p>
              Add this server to your project’s <code>.cursor/mcp.json</code>,
              then connect with OAuth.
            </p>
            <McpCopy
              value={JSON.stringify(
                { mcpServers: { 'video-use': { url: mcpUrl } } },
                null,
                2,
              )}
              label="Cursor configuration"
              code
            />
            <ConnectMcp
              initialClient="cursor"
              className={styles.setupButton}
              label="Cursor setup"
            />
          </article>
        </div>
        <p className={styles.setupNote}>
          Hosted MCP is a private pilot. Account and workspace access required.
          Cursor setup is provided as a guide; end-to-end pilot testing is
          pending.
        </p>
      </section>

      <section className={styles.section} aria-labelledby="prompts-heading">
        <div className={styles.sectionHeading}>
          <span className={styles.kicker}>Start with a prompt</span>
          <h2 id="prompts-heading">What will you make?</h2>
          <p>Bring your subject. These are a place to start.</p>
        </div>
        <div className={styles.prompts}>
          {prompts.map((item) => (
            <article className={styles.promptCard} key={item.label}>
              <div className={styles.promptLabel}>
                <span>
                  <item.icon size={18} />
                </span>
                <span className={styles.kicker}>{item.label}</span>
              </div>
              <h3>{item.title}</h3>
              <McpCopy
                value={item.prompt}
                label={`${item.label} starter prompt`}
                code
              />
              <div className={styles.promptFooter}>
                <span>{item.bring}</span>
                <Link href={item.href}>
                  Examples <ArrowUpRight size={14} />
                </Link>
              </div>
            </article>
          ))}
        </div>
        <Link className={styles.exploreLink} href="/#examples">
          Explore the video library <ArrowUpRight size={15} />
        </Link>
      </section>

      <section className={styles.section} aria-labelledby="agents-heading">
        <div className={styles.sectionHeading}>
          <span className={styles.kicker}>Made to fit your workflow</span>
          <h2 id="agents-heading">Keep the tools you love.</h2>
          <p>
            Use a connected chat, or run the open-source toolkit with your
            coding agent.
          </p>
        </div>
        <div className={styles.agentOptions}>
          <a href="#setup">
            <span>ChatGPT</span>
            <span>
              Custom MCP app <ArrowUpRight size={14} />
            </span>
          </a>
          <a href="#setup">
            <span>Claude</span>
            <span>
              Custom connector <ArrowUpRight size={14} />
            </span>
          </a>
          <a href="#setup">
            <span>Cursor</span>
            <span>
              MCP configuration <ArrowUpRight size={14} />
            </span>
          </a>
          <a href={`${repository}#readme`} target="_blank" rel="noreferrer">
            <span>
              <Code2 size={18} /> Open source
            </span>
            <span>
              Your own runtime <ArrowUpRight size={14} />
            </span>
          </a>
        </div>
      </section>

      <section className={styles.section} aria-labelledby="faq-heading">
        <div className={styles.sectionHeading}>
          <span className={styles.kicker}>A little more detail</span>
          <h2 id="faq-heading">Before you press play.</h2>
        </div>
        <div className={styles.faqs}>
          {faqs.map((item) => (
            <details key={item.question}>
              <summary>
                {item.question}
                <Plus size={18} />
              </summary>
              <p>{item.answer}</p>
            </details>
          ))}
        </div>
      </section>

      <section
        className={`${styles.section} ${styles.closing}`}
        aria-label="Get started with Video Use"
      >
        <Film size={24} />
        <h2>Your next video starts here.</h2>
        <div>
          <ConnectMcp className="primary-button" label="Connect MCP" />
          <Link href="/#examples" className={styles.cardLink}>
            Find a prompt <ArrowUpRight size={15} />
          </Link>
        </div>
      </section>
      <Wordmark />
    </main>
  );
}
