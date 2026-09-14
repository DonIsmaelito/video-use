'use client';

import { useEffect, useRef, useState } from 'react';
import { Check, Copy } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from '@/components/ui/dialog';

const cloneCommand =
  'mkdir -p ~/Developer && git clone https://github.com/browser-use/video-use ~/Developer/video-use';

const setupPrompt =
  'Set up ~/Developer/video-use for me. Read its install.md first and follow the setup: install dependencies, wire up ffmpeg, and register the whole repo as a skill with this agent. Reuse an existing ElevenLabs API key or ask me for one when needed. Then read SKILL.md and helpers/, verify setup without transcribing, and wait for my video prompt.';

export function GettingStarted() {
  const [copied, setCopied] = useState<'clone' | 'setup' | null>(null);
  const [manualCopy, setManualCopy] = useState('');
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const manualText = useRef<HTMLTextAreaElement>(null);

  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );

  useEffect(() => {
    if (manualCopy) manualText.current?.select();
  }, [manualCopy]);

  async function copyStep(step: 'clone' | 'setup') {
    const text = step === 'clone' ? cloneCommand : setupPrompt;
    try {
      await navigator.clipboard.writeText(text);
      setCopied(step);
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => setCopied(null), 2400);
    } catch {
      setManualCopy(text);
    }
  }

  return (
    <>
      <fieldset className="getting-started" aria-label="Start using video-use">
        <Button
          variant="ghost"
          className="setup-step clone-step"
          onClick={() => copyStep('clone')}
          aria-label="Copy the git clone command to run in your terminal"
          title="Copy command · paste in your terminal"
        >
          <span className="setup-number" aria-hidden="true">
            01
          </span>
          <code className="setup-command">
            <span>mkdir -p ~/Developer &amp;&amp;</span>{' '}
            <span>
              git clone https://github.com/browser-use/video-use
              ~/Developer/video-use
            </span>
          </code>
          {copied === 'clone' ? <Check size={16} /> : <Copy size={16} />}
        </Button>
        <Button
          variant="ghost"
          className="setup-step"
          onClick={() => copyStep('setup')}
          aria-label="Copy the setup prompt to paste in your coding agent"
          title="Copy setup prompt · paste in your coding agent"
        >
          <span className="setup-number" aria-hidden="true">
            02
          </span>
          <span className="setup-label">
            {copied === 'setup'
              ? 'Setup prompt copied'
              : 'Copy setup prompt for your agent'}
          </span>
          {copied === 'setup' ? <Check size={16} /> : <Copy size={16} />}
        </Button>
        <output className="sr-only">
          {copied === 'clone' &&
            'Clone command copied. Paste it in your terminal.'}
          {copied === 'setup' &&
            'Setup prompt copied. Paste it in your coding agent.'}
        </output>
      </fieldset>
      <Dialog
        open={!!manualCopy}
        onOpenChange={(open) => {
          if (!open) setManualCopy('');
        }}
      >
        <DialogContent className="manual-copy-dialog">
          <DialogTitle>Copy to get started</DialogTitle>
          <DialogDescription>
            Your browser couldn’t copy automatically. Copy the selected text
            below.
          </DialogDescription>
          <textarea
            ref={manualText}
            value={manualCopy}
            readOnly
            aria-label="Setup text to copy"
            rows={7}
          />
          <Button onClick={() => setManualCopy('')}>Done</Button>
        </DialogContent>
      </Dialog>
    </>
  );
}
