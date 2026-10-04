'use client';

import { useEffect, useRef, useState } from 'react';
import { Check, Copy, Terminal } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Disclosure } from '@/components/ui/disclosure';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from '@/components/ui/dialog';

const cloneCommand = 'git clone https://github.com/browser-use/video-use.git';

export function GettingStarted() {
  const [copied, setCopied] = useState(false);
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

  async function copyClone() {
    try {
      await navigator.clipboard.writeText(cloneCommand);
      setCopied(true);
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => setCopied(false), 2400);
    } catch {
      setManualCopy(cloneCommand);
    }
  }

  return (
    <>
      <Disclosure
        label="Install Video Use"
        icon={<Terminal size={15} />}
        className="getting-started"
      >
        <Button
          variant="ghost"
          className="clone-command"
          onClick={copyClone}
          aria-label="Copy the git clone command to run in your terminal"
          title="Copy command · paste in your terminal"
        >
          <code className="clone-command-text">{cloneCommand}</code>
          <span className="clone-command-action">
            {copied ? <Check size={15} /> : <Copy size={15} />}
          </span>
        </Button>
        <output className="sr-only">
          {copied && 'Clone command copied. Paste it in your terminal.'}
        </output>
      </Disclosure>
      <Dialog
        open={!!manualCopy}
        onOpenChange={(open) => {
          if (!open) setManualCopy('');
        }}
      >
        <DialogContent className="manual-copy-dialog">
          <DialogTitle>Copy clone command</DialogTitle>
          <DialogDescription>
            Your browser couldn’t copy automatically. Copy the selected text
            below.
          </DialogDescription>
          <textarea
            ref={manualText}
            value={manualCopy}
            readOnly
            aria-label="Git clone command to copy"
            rows={3}
          />
          <Button onClick={() => setManualCopy('')}>Done</Button>
        </DialogContent>
      </Dialog>
    </>
  );
}
