"use client";

import {
  type CSSProperties,
  type RefObject,
  useLayoutEffect,
  useState,
} from "react";
import { createPortal } from "react-dom";

import type { SkillSummary } from "@/lib/skills";
import { cn } from "@/lib/utils";

type SkillSlashMenuProps = {
  skills: SkillSummary[];
  selectedIndex: number;
  onSelect: (skill: SkillSummary) => void;
  loading?: boolean;
  className?: string;
  style?: CSSProperties;
};

export function SkillSlashMenu({
  skills,
  selectedIndex,
  onSelect,
  loading = false,
  className,
  style,
}: SkillSlashMenuProps) {
  return (
    <div
      className={cn(
        "z-50 max-h-52 overflow-y-auto rounded-md border bg-popover text-popover-foreground shadow-md",
        className,
      )}
      style={style}
      role="listbox"
      aria-label="Available skills"
    >
      <div className="border-b px-3 py-1.5 text-[11px] font-medium text-muted-foreground">
        Skills
      </div>
      {loading ? (
        <div className="px-3 py-2 text-xs text-muted-foreground">
          Loading skills…
        </div>
      ) : skills.length === 0 ? (
        <div className="px-3 py-2 text-xs text-muted-foreground">
          No matching skills
        </div>
      ) : (
        skills.map((skill, index) => (
          <button
            key={skill.id}
            type="button"
            role="option"
            aria-selected={index === selectedIndex}
            className={cn(
              "w-full px-3 py-2 text-left transition-colors hover:bg-accent",
              index === selectedIndex && "bg-accent",
            )}
            onMouseDown={event => {
              event.preventDefault();
              onSelect(skill);
            }}
          >
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs font-medium">
                /{skill.slug}
              </span>
              <span className="truncate text-xs text-muted-foreground">
                {skill.name}
              </span>
              <span className="ml-auto shrink-0 rounded bg-muted px-1.5 py-0.5 text-[10px] uppercase text-muted-foreground">
                {skill.source}
              </span>
            </div>
            {skill.description ? (
              <p className="mt-0.5 line-clamp-1 text-[11px] text-muted-foreground">
                {skill.description}
              </p>
            ) : null}
          </button>
        ))
      )}
    </div>
  );
}

type SkillSlashMenuPortalProps = SkillSlashMenuProps & {
  open: boolean;
  anchorRef: RefObject<HTMLElement | null>;
};

export function SkillSlashMenuPortal({
  open,
  anchorRef,
  ...props
}: SkillSlashMenuPortalProps) {
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
  }, [anchorRef, open, props.skills.length, props.loading]);

  if (!open || !position || typeof document === "undefined") return null;

  return createPortal(
    <SkillSlashMenu
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
