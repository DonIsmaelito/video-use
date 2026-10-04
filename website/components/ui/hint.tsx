'use client';

import { useId, useState, type ReactElement } from 'react';
import { Tooltip } from '@base-ui/react/tooltip';

/** Supplemental labels only; the trigger keeps its own accessible name. */
export function Hint({
  label,
  children,
}: {
  label: string;
  children: ReactElement;
}) {
  const id = useId();
  const [open, setOpen] = useState(false);
  return (
    <Tooltip.Root open={open} onOpenChange={setOpen}>
      <Tooltip.Trigger
        render={children}
        delay={350}
        aria-describedby={open ? id : undefined}
      />
      <Tooltip.Portal>
        <Tooltip.Positioner
          side="top"
          sideOffset={9}
          className="hint-positioner"
        >
          <Tooltip.Popup className="ui-hint" id={id} role="tooltip">
            {label}
          </Tooltip.Popup>
        </Tooltip.Positioner>
      </Tooltip.Portal>
    </Tooltip.Root>
  );
}
