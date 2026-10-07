'use client';

import { useId } from 'react';

type Character = 'editor' | 'designer' | 'artist' | 'storyteller' | 'pearl';

const silhouettes: Record<Character, string> = {
  editor:
    'M22 76C12 70 16 56 27 50C27 41 29 35 37 31C36 15 48 9 60 16C70 17 74 26 72 36C86 40 86 51 81 59C96 75 84 89 70 86C63 96 45 94 39 85C32 88 25 84 22 76Z',
  designer:
    'M18 71C24 55 35 23 44 16C51 10 62 15 66 24L84 69C90 85 80 94 66 86C59 92 45 92 39 85C22 96 11 88 18 71Z',
  artist:
    'M39 18C44 6 60 8 64 21C76 13 89 24 83 36C98 39 99 55 86 61C96 73 85 88 72 83C68 99 50 97 45 84C31 94 17 83 23 70C8 64 11 48 25 44C15 30 27 17 39 18Z',
  storyteller:
    'M27 37C31 16 65 10 77 31C84 43 77 58 82 70C88 93 64 96 49 92C23 94 16 81 21 65C25 53 22 46 27 37Z',
  pearl:
    'M38 18C42 6 60 8 64 20C76 15 87 26 81 37C94 40 95 55 84 62C92 74 81 85 69 81C64 95 49 95 43 82C29 90 16 79 23 67C10 59 13 45 26 42C19 29 26 19 38 18Z',
};

/** Original vector sculptures: one light setup, five distinct silhouettes. */
export function McpMascot({ character }: { character: Character }) {
  const id = useId().replaceAll(':', '');
  const pearl = character === 'pearl';
  return (
    <svg viewBox="0 0 108 108" fill="none" aria-hidden="true">
      <defs>
        <radialGradient
          id={`${id}-clay`}
          cx="0"
          cy="0"
          r="1"
          gradientTransform="translate(36 27) rotate(52) scale(81 73)"
          gradientUnits="userSpaceOnUse"
        >
          <stop stopColor={pearl ? '#fff' : '#ffe8bc'} />
          <stop offset=".24" stopColor={pearl ? '#f3f3f2' : '#ffc16e'} />
          <stop offset=".56" stopColor={pearl ? '#d7d8d7' : '#ff932c'} />
          <stop offset=".8" stopColor={pearl ? '#a8acaf' : '#d5600a'} />
          <stop offset="1" stopColor={pearl ? '#6c747a' : '#87410f'} />
        </radialGradient>
        <radialGradient
          id={`${id}-shine`}
          cx="0"
          cy="0"
          r="1"
          gradientTransform="translate(38 26) rotate(65) scale(31 35)"
          gradientUnits="userSpaceOnUse"
        >
          <stop stopColor="#fff" stopOpacity=".64" />
          <stop offset="1" stopColor="#fff" stopOpacity="0" />
        </radialGradient>
        <linearGradient
          id={`${id}-lens`}
          x1="34"
          y1="42"
          x2="69"
          y2="67"
          gradientUnits="userSpaceOnUse"
        >
          <stop stopColor="#5a4c40" />
          <stop offset=".3" stopColor="#1d1917" />
          <stop offset="1" stopColor="#080808" />
        </linearGradient>
        <filter
          id={`${id}-shadow`}
          x="0"
          y="0"
          width="108"
          height="112"
          filterUnits="userSpaceOnUse"
        >
          <feDropShadow dx="1" dy="4" stdDeviation="2.5" floodOpacity=".38" />
        </filter>
      </defs>
      <g filter={`url(#${id}-shadow)`}>
        <path d={silhouettes[character]} fill={`url(#${id}-clay)`} />
        <path d={silhouettes[character]} fill={`url(#${id}-shine)`} />
        {character === 'editor' ? (
          <g transform="rotate(9 54 54)">
            <path
              d="M30 48L39 51M70 52L79 49"
              stroke="#30231b"
              strokeWidth="3"
              strokeLinecap="round"
            />
            <rect
              x="34"
              y="44"
              width="19"
              height="16"
              rx="6"
              fill={`url(#${id}-lens)`}
              stroke="#30231b"
              strokeWidth="2"
            />
            <rect
              x="57"
              y="44"
              width="19"
              height="16"
              rx="6"
              fill={`url(#${id}-lens)`}
              stroke="#30231b"
              strokeWidth="2"
            />
            <path
              d="M53 49C54 47 56 47 57 49"
              stroke="#30231b"
              strokeWidth="3"
            />
            <path
              d="M38 47H45M61 47H67"
              stroke="#ffffff55"
              strokeWidth="2"
              strokeLinecap="round"
            />
          </g>
        ) : (
          <g
            transform={character === 'artist' ? 'rotate(-10 54 57)' : undefined}
          >
            <ellipse cx="43" cy="55" rx="4.2" ry="7" fill="#241c19" />
            <ellipse cx="62" cy="56" rx="4.2" ry="7" fill="#241c19" />
            <ellipse cx="42" cy="52" rx="1.2" ry="2" fill="#ffffff80" />
            <ellipse cx="61" cy="53" rx="1.2" ry="2" fill="#ffffff80" />
            {character === 'designer' && (
              <g stroke="#3e2b1d" strokeWidth="2.4">
                <circle cx="43" cy="55" r="10" />
                <circle cx="65" cy="55" r="10" />
                <path
                  d="M53 54H55M33 51L28 49M75 51L79 48"
                  strokeLinecap="round"
                />
              </g>
            )}
          </g>
        )}
        {character === 'storyteller' && (
          <g>
            <path
              d="M21 58V48C19 11 84 10 85 48V61"
              stroke="#17181a"
              strokeWidth="7"
              strokeLinecap="round"
            />
            <path
              d="M22 43C25 14 77 13 82 42"
              stroke="#73706b"
              strokeWidth="2"
              strokeLinecap="round"
            />
            <rect
              x="16"
              y="44"
              width="13"
              height="25"
              rx="6.5"
              fill="#292a2b"
              stroke="#77736b"
              strokeWidth="1.5"
            />
            <rect
              x="77"
              y="44"
              width="13"
              height="25"
              rx="6.5"
              fill="#292a2b"
              stroke="#77736b"
              strokeWidth="1.5"
            />
            <path
              d="M21 50V61M82 50V61"
              stroke="#4a4a49"
              strokeWidth="3"
              strokeLinecap="round"
            />
          </g>
        )}
      </g>
    </svg>
  );
}
