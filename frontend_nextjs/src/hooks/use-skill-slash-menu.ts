"use client";

import {
  type ChangeEvent,
  type KeyboardEvent,
  type SyntheticEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { getToken } from "@/lib/auth";
import {
  fetchAllAvailableSkills,
  type SkillSummary,
} from "@/lib/skills";

export type SlashContext = {
  query: string;
  start: number;
  end: number;
};

export function getSlashContext(
  text: string,
  cursor: number,
): SlashContext | null {
  const before = text.slice(0, cursor);
  const match = before.match(/(?:^|\s)\/([a-zA-Z0-9_-]*)$/);
  if (!match) return null;
  const query = match[1];
  const token = match[0].trimStart();
  const start = cursor - token.length;
  return { query, start, end: cursor };
}

function filterSkills(skills: SkillSummary[], query: string): SkillSummary[] {
  const q = query.trim().toLowerCase();
  if (!q) return skills;
  return skills.filter(
    skill =>
      skill.slug.toLowerCase().includes(q) ||
      skill.name.toLowerCase().includes(q) ||
      skill.description.toLowerCase().includes(q),
  );
}

type UseSkillSlashMenuOptions = {
  value: string;
  onValueChange: (value: string) => void;
  enabled?: boolean;
};

export function useSkillSlashMenu({
  value,
  onValueChange,
  enabled = true,
}: UseSkillSlashMenuOptions) {
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const [inputSnapshot, setInputSnapshot] = useState({
    text: value,
    cursor: value.length,
  });
  const [skills, setSkills] = useState<SkillSummary[]>([]);
  const [skillsLoading, setSkillsLoading] = useState(true);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    setInputSnapshot({ text: value, cursor: value.length });
  }, [value]);

  useEffect(() => {
    if (!enabled) return;
    const token = getToken();
    if (!token) {
      setSkillsLoading(false);
      return;
    }
    let cancelled = false;
    setSkillsLoading(true);
    void fetchAllAvailableSkills(token)
      .then(list => {
        if (!cancelled) setSkills(list);
      })
      .catch(() => {
        if (!cancelled) setSkills([]);
      })
      .finally(() => {
        if (!cancelled) setSkillsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [enabled]);

  const slashContext = useMemo(
    () =>
      enabled
        ? getSlashContext(inputSnapshot.text, inputSnapshot.cursor)
        : null,
    [enabled, inputSnapshot],
  );

  const filteredSkills = useMemo(
    () =>
      slashContext ? filterSkills(skills, slashContext.query) : [],
    [slashContext, skills],
  );

  const menuOpen = enabled && !!slashContext && !dismissed;

  useEffect(() => {
    setSelectedIndex(0);
    setDismissed(false);
  }, [slashContext?.query, slashContext?.start]);

  const syncFromElement = useCallback((el: HTMLTextAreaElement) => {
    textareaRef.current = el;
    setInputSnapshot({
      text: el.value,
      cursor: el.selectionStart ?? el.value.length,
    });
  }, []);

  const selectSkill = useCallback(
    (skill: SkillSummary) => {
      if (!slashContext) return;
      const replacement = `/${skill.slug} `;
      const newValue =
        inputSnapshot.text.slice(0, slashContext.start) +
        replacement +
        inputSnapshot.text.slice(slashContext.end);
      const newCursor = slashContext.start + replacement.length;
      onValueChange(newValue);
      setInputSnapshot({ text: newValue, cursor: newCursor });
      setDismissed(true);
      requestAnimationFrame(() => {
        const el = textareaRef.current;
        if (!el) return;
        el.focus();
        el.setSelectionRange(newCursor, newCursor);
      });
    },
    [inputSnapshot.text, onValueChange, slashContext],
  );

  const onTextareaChange = useCallback(
    (event: ChangeEvent<HTMLTextAreaElement>) => {
      syncFromElement(event.currentTarget);
    },
    [syncFromElement],
  );

  const onTextareaSelect = useCallback(
    (event: SyntheticEvent<HTMLTextAreaElement>) => {
      syncFromElement(event.currentTarget);
    },
    [syncFromElement],
  );

  /** Returns true when the key event was handled by the slash menu. */
  const onTextareaKeyDown = useCallback(
    (event: KeyboardEvent<HTMLTextAreaElement>): boolean => {
      syncFromElement(event.currentTarget);

      if (!menuOpen) {
        if (event.key === "Escape") setDismissed(true);
        return false;
      }

      if (filteredSkills.length === 0) {
        if (event.key === "Escape") {
          event.preventDefault();
          setDismissed(true);
          return true;
        }
        return false;
      }

      if (event.key === "ArrowDown") {
        event.preventDefault();
        setSelectedIndex(i => (i + 1) % filteredSkills.length);
        return true;
      }

      if (event.key === "ArrowUp") {
        event.preventDefault();
        setSelectedIndex(
          i => (i - 1 + filteredSkills.length) % filteredSkills.length,
        );
        return true;
      }

      if (event.key === "Enter" || event.key === "Tab") {
        event.preventDefault();
        const skill = filteredSkills[selectedIndex];
        if (skill) selectSkill(skill);
        return true;
      }

      if (event.key === "Escape") {
        event.preventDefault();
        setDismissed(true);
        return true;
      }

      return false;
    },
    [filteredSkills, menuOpen, selectSkill, selectedIndex, syncFromElement],
  );

  return {
    menuOpen,
    filteredSkills,
    selectedIndex,
    skillsLoading,
    textareaRef,
    selectSkill,
    onTextareaChange,
    onTextareaSelect,
    onTextareaKeyDown,
  };
}
