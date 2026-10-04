'use client';

import type { ReactNode } from 'react';
import { Collapsible } from '@base-ui/react/collapsible';
import { ChevronDown } from 'lucide-react';

export function Disclosure({
  label,
  children,
  icon,
  defaultOpen = false,
  className = '',
}: {
  label: string;
  children: ReactNode;
  icon?: ReactNode;
  defaultOpen?: boolean;
  className?: string;
}) {
  return (
    <Collapsible.Root
      defaultOpen={defaultOpen}
      className={`disclosure ${className}`}
    >
      <Collapsible.Trigger className="disclosure-trigger">
        {icon}
        <span>{label}</span>
        <ChevronDown size={15} className="disclosure-chevron" />
      </Collapsible.Trigger>
      <Collapsible.Panel className="disclosure-panel">
        <div className="disclosure-content">{children}</div>
      </Collapsible.Panel>
    </Collapsible.Root>
  );
}
