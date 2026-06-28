---
name: skill-generator
description: Help users design, draft, and refine custom agent skills with clear instructions, triggers, and access settings for the Skills page.
---

# Skill Generator

Use this skill when the user wants to **create**, **design**, **improve**, or **turn a workflow into** a custom agent skill.

## When to use

- "Create a skill for …"
- "Help me write a skill that …"
- "Turn this process into a skill"
- "What should my skill instructions say?"
- User describes a repeatable workflow the agent should follow

## Workflow

1. **Clarify intent** — Ask only what is missing:
   - What task or workflow should the skill cover?
   - When should the agent load this skill (trigger phrases / scenarios)?
   - Any required output format, tools, or constraints?
   - Who should access it: **private** (only creator), **organization**, specific **groups**, or **roles**?

2. **Draft the skill** — Produce a complete draft with these fields:
   - **Name** — short, human-readable (max 120 chars)
   - **Slug** — lowercase kebab-case (optional; derived from name if omitted)
   - **Description** — one sentence for `list_skills` (when the agent should use it)
   - **Instructions** — markdown body the agent follows after `read_skill`

3. **Structure instructions** using this outline:

   ```markdown
   ## When to use
   - …

   ## Steps
   1. …

   ## Output format
   - …

   ## Do not
   - …
   ```

4. **Recommend access** — Default to **private** unless the user wants to share:
   - **private** — personal workflows, drafts, sensitive procedures
   - **organization** — team-wide standards everyone should use
   - **group** — limited to selected groups the user belongs to
   - **role** — e.g. ADMIN-only runbooks

5. **Hand off to the UI** — Tell the user to open **Skills** (`/skills`), click **New**, paste the draft, set access, and save. Custom skills are stored in Postgres and appear in `list_skills` for permitted users.

6. **Iterate** — Offer to refine name, description, triggers, or steps based on feedback.

## Draft output format

Always present the draft in this copy-paste-friendly block:

```
Name: …
Slug: …
Description: …
Access: private | organization | group (…) | role (…)

--- Instructions ---
## When to use
…

## Steps
1. …

## Output format
…

## Do not
…
```

## Quality checklist

Before finalizing, verify:

- **Description** states *when* to use the skill, not just *what* it does
- **Steps** are actionable and ordered; reference platform tools by exact name when relevant (`search_knowledge_base`, `list_skills`, browser tools, sandbox filesystem, etc.)
- **Do not** section prevents common mistakes (hallucination, skipping tools, wrong access)
- Instructions fit in ~100k chars; prefer concise, scannable markdown
- No vague triggers like "when helpful" — use concrete user intents

## Platform notes

- **Built-in skills** live under `app/ai/skills/` (e.g. `knowledge-base`, `skill-generator`); only developers add those via code.
- **Custom skills** are created in the **Skills** UI and loaded via `read_skill` using the skill's UUID (shown after save) or slug for built-ins only.
- After saving, the user can test in chat; the agent should call `list_skills` then `read_skill` when the task matches.

## Example (abbreviated)

**User:** "Create a skill for reviewing Python PRs"

**You produce:**

```
Name: Python PR Review
Slug: python-pr-review
Description: Review Python pull requests for correctness, tests, style, and security when the user asks for a code review.
Access: private

--- Instructions ---
## When to use
- User asks to review a PR, diff, or Python patch

## Steps
1. Ask for the diff or file paths if not provided
2. Check correctness, edge cases, error handling, and tests
3. Note style issues only when they affect readability or consistency
4. Summarize: blocking issues, suggestions, and positive notes

## Output format
- **Blocking** — must fix
- **Suggestions** — optional improvements
- **Summary** — one paragraph

## Do not
- Approve without reading the actual code
- Invent files or line numbers not shown
```

## Do not

- Create skills silently in chat without giving the user a copy-paste draft for the Skills page (unless a create-skill API tool exists and the user explicitly asks you to save it).
- Write instructions that contradict built-in platform behavior or tools the agent does not have.
- Use organization-wide access unless the user confirms they want to share with everyone.
