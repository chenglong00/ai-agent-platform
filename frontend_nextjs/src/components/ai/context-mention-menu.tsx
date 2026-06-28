"use client";

import {
  type CSSProperties,
  type RefObject,
  useLayoutEffect,
  useState,
} from "react";
import { createPortal } from "react-dom";

import {
  type ContextMentionItem,
  contextMentionTypeLabel,
} from "@/lib/context-mentions";
import { cn } from "@/lib/utils";

type ContextMentionMenuProps = {
  items: ContextMentionItem[];
  selectedIndex: number;
  onSelect: (item: ContextMentionItem) => void;
  loading?: boolean;
  className?: string;
  style?: CSSProperties;
};

export function ContextMentionMenu({
  items,
  selectedIndex,
  onSelect,
  loading = false,
  className,
  style,
}: ContextMentionMenuProps) {
  return (
    <div
      className={cn(
        "z-50 max-h-52 overflow-y-auto rounded-md border bg-popover text-popover-foreground shadow-md",
        className,
      )}
      style={style}
      role="listbox"
      aria-label="Context mentions"
    >
      <div className="border-b px-3 py-1.5 text-[11px] font-medium text-muted-foreground">
        Context
      </div>
      {loading ? (
        <div className="px-3 py-2 text-xs text-muted-foreground">
          Loading context…
        </div>
      ) : items.length === 0 ? (
        <div className="px-3 py-2 text-xs text-muted-foreground">
          No matching context
        </div>
      ) : (
        items.map((item, index) => (
          <button
            key={item.id}
            type="button"
            role="option"
            aria-selected={index === selectedIndex}
            className={cn(
              "w-full px-3 py-2 text-left transition-colors hover:bg-accent",
              index === selectedIndex && "bg-accent",
            )}
            onMouseDown={event => {
              event.preventDefault();
              onSelect(item);
            }}
          >
            <div className="flex items-center gap-2">
              <span className="truncate text-xs font-medium">{item.label}</span>
              <span className="ml-auto shrink-0 rounded bg-muted px-1.5 py-0.5 text-[10px] uppercase text-muted-foreground">
                {contextMentionTypeLabel(item.type)}
              </span>
            </div>
            <p className="mt-0.5 line-clamp-1 font-mono text-[11px] text-muted-foreground">
              {item.token}
            </p>
            {item.description ? (
              <p className="mt-0.5 line-clamp-1 text-[11px] text-muted-foreground">
                {item.description}
              </p>
            ) : null}
          </button>
        ))
      )}
    </div>
  );
}

type ContextMentionMenuPortalProps = ContextMentionMenuProps & {
  open: boolean;
  anchorRef: RefObject<HTMLElement | null>;
};

export function ContextMentionMenuPortal({
  open,
  anchorRef,
  ...props
}: ContextMentionMenuPortalProps) {
  const [position, setPosition] = useState<{
    left: number;
    width: number;
    bottom: number;
  } | null>(null);

  useLayoutEffect(() => {
    if (!open) {
      setPosition(null);
      return;
    }

    const updatePosition = () => {
      const anchor = anchorRef.current;
      if (!anchor) return;
      const rect = anchor.getBoundingClientRect();
      setPosition({
        left: rect.left,
        width: rect.width,
        bottom: window.innerHeight - rect.top + 4,
      });
    };

    updatePosition();
    window.addEventListener("resize", updatePosition);
    window.addEventListener("scroll", updatePosition, true);
    return () => {
      window.removeEventListener("resize", updatePosition);
      window.removeEventListener("scroll", updatePosition, true);
    };
  }, [anchorRef, open, props.items.length, props.loading]);

  if (!open || !position || typeof document === "undefined") return null;

  return createPortal(
    <ContextMentionMenu
      {...props}
      style={{
        position: "fixed",
        left: position.left,
        width: position.width,
        bottom: position.bottom,
      }}
    />,
    document.body,
  );
}
