"use client";

import {
  type ChangeEvent,
  type ClipboardEventHandler,
  type KeyboardEventHandler,
  type SyntheticEvent,
  useCallback,
  useRef,
  useState,
} from "react";

import { ContextMentionMenuPortal } from "@/components/ai/context-mention-menu";
import { SkillSlashMenuPortal } from "@/components/ai/skill-slash-menu";
import {
  type PromptInputTextareaProps,
  useOptionalPromptInputController,
  usePromptInputAttachments,
} from "@/components/ai/prompt-input";
import { InputGroupTextarea } from "@/components/ui/input-group";
import { useContextMentionMenu } from "@/hooks/use-context-mention-menu";
import { useSkillSlashMenu } from "@/hooks/use-skill-slash-menu";
import { cn } from "@/lib/utils";

export function PromptInputSkillTextarea({
  onChange,
  className,
  placeholder = "Type your message… (/ skills, @ context)",
  onKeyDown,
  ...props
}: PromptInputTextareaProps) {
  const controller = useOptionalPromptInputController();
  const attachments = usePromptInputAttachments();
  const [isComposing, setIsComposing] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  const value = controller?.textInput.value ?? "";
  const setValue = controller?.textInput.setInput;

  const slash = useSkillSlashMenu({
    value,
    onValueChange: next => setValue?.(next),
    enabled: !!controller,
  });

  const context = useContextMentionMenu({
    value,
    onValueChange: next => setValue?.(next),
    enabled: !!controller,
  });

  const syncTextarea = useCallback(
    (el: HTMLTextAreaElement) => {
      textareaRef.current = el;
      slash.textareaRef.current = el;
      context.textareaRef.current = el;
    },
    [context.textareaRef, slash.textareaRef],
  );

  const handleChange = useCallback(
    (event: ChangeEvent<HTMLTextAreaElement>) => {
      syncTextarea(event.currentTarget);
      slash.onTextareaChange(event);
      context.onTextareaChange(event);
    },
    [context, slash, syncTextarea],
  );

  const handleSelect = useCallback(
    (event: SyntheticEvent<HTMLTextAreaElement>) => {
      syncTextarea(event.currentTarget);
      slash.onTextareaSelect(event);
      context.onTextareaSelect(event);
    },
    [context, slash, syncTextarea],
  );

  const handleKeyDown: KeyboardEventHandler<HTMLTextAreaElement> = event => {
    syncTextarea(event.currentTarget);
    if (context.onTextareaKeyDown(event)) {
      onKeyDown?.(event);
      return;
    }
    if (slash.onTextareaKeyDown(event)) {
      onKeyDown?.(event);
      return;
    }

    if (event.key === "Enter") {
      if (isComposing || event.nativeEvent.isComposing) {
        onKeyDown?.(event);
        return;
      }
      if (event.shiftKey) {
        onKeyDown?.(event);
        return;
      }
      event.preventDefault();

      const form = event.currentTarget.form;
      const submitButton = form?.querySelector(
        'button[type="submit"]',
      ) as HTMLButtonElement | null;
      if (submitButton?.disabled) {
        onKeyDown?.(event);
        return;
      }

      form?.requestSubmit();
    }

    if (
      event.key === "Backspace" &&
      event.currentTarget.value === "" &&
      attachments.files.length > 0
    ) {
      event.preventDefault();
      const lastAttachment = attachments.files.at(-1);
      if (lastAttachment) {
        attachments.remove(lastAttachment.id);
      }
    }

    onKeyDown?.(event);
  };

  const handlePaste: ClipboardEventHandler<HTMLTextAreaElement> = event => {
    const items = event.clipboardData?.items;
    if (!items) return;

    const files: File[] = [];
    for (const item of items) {
      if (item.kind === "file") {
        const file = item.getAsFile();
        if (file) files.push(file);
      }
    }

    if (files.length > 0) {
      event.preventDefault();
      attachments.add(files);
    }
  };

  const controlledProps = controller
    ? {
        value: controller.textInput.value,
        onChange: (event: ChangeEvent<HTMLTextAreaElement>) => {
          controller.textInput.setInput(event.currentTarget.value);
          handleChange(event);
          onChange?.(event);
        },
      }
    : {
        onChange: (event: ChangeEvent<HTMLTextAreaElement>) => {
          handleChange(event);
          onChange?.(event);
        },
      };

  const menuAnchorRef = textareaRef;

  return (
    <div className="relative w-full">
      <ContextMentionMenuPortal
        open={context.menuOpen}
        anchorRef={menuAnchorRef}
        items={context.filteredItems}
        selectedIndex={context.selectedIndex}
        onSelect={context.selectItem}
        loading={context.loading}
      />
      <SkillSlashMenuPortal
        open={slash.menuOpen && !context.menuOpen}
        anchorRef={menuAnchorRef}
        skills={slash.filteredSkills}
        selectedIndex={slash.selectedIndex}
        onSelect={slash.selectSkill}
        loading={slash.skillsLoading}
      />
      <InputGroupTextarea
        ref={textareaRef}
        className={cn("field-sizing-content max-h-48 min-h-16", className)}
        name="message"
        onCompositionEnd={() => setIsComposing(false)}
        onCompositionStart={() => setIsComposing(true)}
        onKeyDown={handleKeyDown}
        onPaste={handlePaste}
        onSelect={handleSelect}
        onClick={handleSelect}
        placeholder={placeholder}
        {...props}
        {...controlledProps}
      />
    </div>
  );
}
