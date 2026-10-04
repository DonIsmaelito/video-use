'use client';

import { useEffect, useId, useRef, useState } from 'react';
import { Check, Copy } from 'lucide-react';
import styles from './mcp-copy.module.css';

/** Keep setup details selectable when clipboard permission is unavailable. */
export function McpCopy({
  value,
  label,
  code = false,
}: {
  value: string;
  label: string;
  code?: boolean;
}) {
  const id = useId();
  const input = useRef<HTMLInputElement>(null);
  const pre = useRef<HTMLPreElement>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [state, setState] = useState<'idle' | 'copied' | 'manual'>('idle');

  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );

  async function copy() {
    if (timer.current) clearTimeout(timer.current);
    try {
      await navigator.clipboard.writeText(value);
      setState('copied');
      timer.current = setTimeout(() => setState('idle'), 2400);
    } catch {
      setState('manual');
      if (code && pre.current) {
        pre.current.focus();
        const range = document.createRange();
        range.selectNodeContents(pre.current);
        const selection = window.getSelection();
        selection?.removeAllRanges();
        selection?.addRange(range);
      } else {
        input.current?.focus();
        input.current?.select();
      }
    }
  }

  return (
    <div className={`${styles.field} ${code ? styles.code : styles.pill}`}>
      {code ? (
        <span id={id} className={styles.label}>
          {label}
        </span>
      ) : (
        <label htmlFor={id} className="sr-only">
          {label}
        </label>
      )}
      <div className={styles.row}>
        {code ? (
          <pre ref={pre} tabIndex={-1} aria-labelledby={id}>
            {value}
          </pre>
        ) : (
          <input
            id={id}
            ref={input}
            value={value}
            readOnly
            spellCheck={false}
            onFocus={(event) => event.target.select()}
          />
        )}
        <button type="button" onClick={copy} aria-label={`Copy ${label}`}>
          {state === 'copied' ? <Check size={16} /> : <Copy size={16} />}
        </button>
      </div>
      <output
        className={state === 'manual' ? styles.manual : 'sr-only'}
        aria-live="polite"
      >
        {state === 'copied'
          ? 'Copied to clipboard.'
          : state === 'manual'
            ? 'Copy the selected text.'
            : ''}
      </output>
    </div>
  );
}
