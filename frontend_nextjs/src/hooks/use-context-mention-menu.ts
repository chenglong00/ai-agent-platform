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
  type ContextMentionItem,
  fetchContextMentions,
  filterContextMentions,
} from "@/lib/context-mentions";

export type MentionContext = {
  query: string;
  start: number;
  end: number;
};

export function getMentionContext(
  text: string,
  cursor: number,
): MentionContext | null {
  const before = text.slice(0, cursor);
  const match = before.match(/(?:^|\s)@([\w./-]*)$/);
  if (!match) return null;
  const query = match[1];
  const token = match[0].trimStart();
  const start = cursor - token.length;
  return { query, start, end: cursor };
}

type UseContextMentionMenuOptions = {
  value: string;
  onValueChange: (value: string) => void;
  enabled?: boolean;
};

export function useContextMentionMenu({
  value,
  onValueChange,
  enabled = true,
}: UseContextMentionMenuOptions) {
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const [inputSnapshot, setInputSnapshot] = useState({
    text: value,
    cursor: value.length,
  });
  const [items, setItems] = useState<ContextMentionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    setInputSnapshot({ text: value, cursor: value.length });
  }, [value]);

  useEffect(() => {
    if (!enabled) return;
    const token = getToken();
    if (!token) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    void fetchContextMentions(token)
      .then(list => {
        if (!cancelled) setItems(list);
      })
      .catch(() => {
        if (!cancelled) setItems([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [enabled]);

  const mentionContext = useMemo(
    () =>
      enabled
        ? getMentionContext(inputSnapshot.text, inputSnapshot.cursor)
        : null,
    [enabled, inputSnapshot],
  );

  const filteredItems = useMemo(
    () =>
      mentionContext ? filterContextMentions(items, mentionContext.query) : [],
    [mentionContext, items],
  );

  const menuOpen = enabled && !!mentionContext && !dismissed;

  useEffect(() => {
    setSelectedIndex(0);
    setDismissed(false);
  }, [mentionContext?.query, mentionContext?.start]);

  const syncFromElement = useCallback((el: HTMLTextAreaElement) => {
    textareaRef.current = el;
    setInputSnapshot({
      text: el.value,
      cursor: el.selectionStart ?? el.value.length,
    });
  }, []);

  const selectItem = useCallback(
    (item: ContextMentionItem) => {
      if (!mentionContext) return;
      const replacement = `${item.token} `;
      const newValue =
        inputSnapshot.text.slice(0, mentionContext.start) +
        replacement +
        inputSnapshot.text.slice(mentionContext.end);
      const newCursor = mentionContext.start + replacement.length;
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
    [inputSnapshot.text, mentionContext, onValueChange],
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

  const onTextareaKeyDown = useCallback(
    (event: KeyboardEvent<HTMLTextAreaElement>): boolean => {
      syncFromElement(event.currentTarget);

      if (!menuOpen) {
        if (event.key === "Escape") setDismissed(true);
        return false;
      }

      if (filteredItems.length === 0) {
        if (event.key === "Escape") {
          event.preventDefault();
          setDismissed(true);
          return true;
        }
        return false;
      }

      if (event.key === "ArrowDown") {
        event.preventDefault();
        setSelectedIndex(i => (i + 1) % filteredItems.length);
        return true;
      }

      if (event.key === "ArrowUp") {
        event.preventDefault();
        setSelectedIndex(
          i => (i - 1 + filteredItems.length) % filteredItems.length,
        );
        return true;
      }

      if (event.key === "Enter" || event.key === "Tab") {
        event.preventDefault();
        const item = filteredItems[selectedIndex];
        if (item) selectItem(item);
        return true;
      }

      if (event.key === "Escape") {
        event.preventDefault();
        setDismissed(true);
        return true;
      }

      return false;
    },
    [filteredItems, menuOpen, selectItem, selectedIndex, syncFromElement],
  );

  return {
    menuOpen,
    filteredItems,
    selectedIndex,
    loading,
    textareaRef,
    selectItem,
    onTextareaChange,
    onTextareaSelect,
    onTextareaKeyDown,
  };
}
