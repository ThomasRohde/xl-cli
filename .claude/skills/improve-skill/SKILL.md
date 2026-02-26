---
name: improve-skill
description: This skill should be used when the user asks to "improve a skill", "optimize a skill", "review a skill", "audit a skill", "apply SkillsBench findings", "make a skill more effective", "refactor a skill", "fix a skill", or mentions improving, optimizing, or auditing an existing Claude Code skill based on research-backed best practices.
---

# Improve Skill

Analyze and improve an existing Claude Code skill using findings from the SkillsBench research paper (arXiv:2602.12670v1), which evaluated 7,308 agent trajectories and identified what makes skills effective.

## Prerequisites

- Path to an existing skill directory containing a SKILL.md file
- If no path is provided, ask the user which skill to improve

## Improvement Workflow

### Step 1: Load and Audit the Skill

Read the target skill's SKILL.md and all files in its `references/`, `examples/`, and `scripts/` directories. Produce a structured audit against the five evaluation dimensions below.

### Step 2: Score the Five Dimensions

Rate each dimension 1-5 and note specific issues:

**Dimension 1 — Procedural Density**
Measures whether content teaches *how to do things* versus *what things are*.

- 5: Nearly all content is step-by-step procedures with decision points
- 3: Mix of procedural and reference/factual content
- 1: Reads like API documentation or a reference manual

Count the ratio of procedural sentences ("To X, do Y", "Run Z", "Configure W by...") to factual/descriptive sentences ("X is a...", "The Y property contains...", "There are three types of..."). Target: >70% procedural in SKILL.md body.

**Dimension 2 — Conciseness**
Measures whether SKILL.md body stays in the optimal token range.

- 5: Body is 845-1,165 tokens (~1,200-1,800 words), detailed content in references/
- 3: Body is 1,500-2,500 tokens, some content could move to references/
- 1: Body exceeds 2,500 tokens, comprehensive documentation hurting effectiveness

Estimate token count of the SKILL.md body (excluding frontmatter). Comprehensive skills (-2.9pp) perform worse than no skill at all. Detailed (~1,165 tokens, +18.8pp) and compact (~845 tokens, +17.1pp) are optimal.

**Dimension 3 — Working Examples**
Measures whether the skill provides concrete, copy-pasteable code for its procedures.

- 5: Every major procedure has a complete working example
- 3: Some procedures have examples, others are abstract
- 1: No working examples, or examples are fragments/pseudocode

The research found "stepwise guidance with at least one working example" is essential. Code templates and reference implementations matter more than documentation volume.

**Dimension 4 — Signal-to-Noise Ratio**
Measures whether content focuses on non-obvious, domain-specific knowledge versus standard practices models already know.

- 5: All content addresses specialized knowledge or non-obvious procedures
- 3: Mix of specialized and commonly-known content
- 1: Mostly standard practices (basic patterns, common conventions)

Software engineering skills showed only +4.5pp improvement in SkillsBench because models already know standard programming. Content teaching common practices adds noise without value.

**Dimension 5 — Trigger Quality**
Measures whether the frontmatter description reliably activates the skill for intended use cases.

- 5: Third-person, 5+ specific trigger phrases covering all use cases
- 3: Some trigger phrases but missing scenarios
- 1: Vague description, wrong person, or missing trigger phrases

### Step 3: Identify Improvements

Based on the audit scores, identify specific improvements. Prioritize dimensions scoring 1-3. Apply these research-backed principles:

**Principle A — Extract to References (Conciseness)**
Move factual content, detailed schemas, comprehensive lists, and API documentation from SKILL.md to `references/` files. Keep only procedural steps and essential context in SKILL.md.

Before: One large SKILL.md with everything.
After: Lean SKILL.md pointing to `references/detailed-guide.md`, `references/api-reference.md`.

**Principle B — Rewrite Factual as Procedural (Procedural Density)**
Transform "X is a Y that does Z" into "To accomplish Z, use X by doing..."

Before: "The `$()` function returns a collection object with filter, add, and each methods."
After: "To query model elements, call `$('element-type')`. Chain `.filter()` to narrow results and `.each()` to iterate."

**Principle C — Add Working Examples (Working Examples)**
For each major procedure that lacks a concrete example, add a complete, copy-pasteable code block showing the procedure in context.

**Principle D — Remove Common Knowledge (Signal-to-Noise)**
Delete content teaching standard practices. Ask: "Would a competent developer using Claude already know this without the skill?" If yes, remove it.

**Principle E — Strengthen Triggers (Trigger Quality)**
Add specific phrases users would say. Use third person. Cover edge-case phrasings.

**Principle F — Eliminate Conflicting Guidance**
When multiple approaches exist for the same task, designate one as the recommended default. Mention alternatives only with explicit decision criteria for when to deviate.

**Principle G — Verify No Negative Value Content**
The research found 16/84 tasks where skills *hurt* performance. Review for content that:
- Contradicts correct model pretraining knowledge
- Over-specifies solutions, preventing flexible problem-solving
- Adds complexity without procedural value

Remove or restructure such content.

### Step 4: Present Findings and Propose Changes

Present the audit results to the user as a summary table:

```
| Dimension           | Score | Key Issues                    |
|---------------------|-------|-------------------------------|
| Procedural Density  | X/5   | ...                           |
| Conciseness         | X/5   | ...                           |
| Working Examples    | X/5   | ...                           |
| Signal-to-Noise     | X/5   | ...                           |
| Trigger Quality     | X/5   | ...                           |
```

Then list proposed changes grouped by principle (A-G), showing what will change and why. Wait for user approval before making changes.

### Step 5: Apply Approved Changes

After user approval, apply the changes:

1. Edit SKILL.md — restructure body, improve frontmatter
2. Create or update `references/` files for extracted content
3. Add working examples where needed
4. Remove low-value content
5. Verify all referenced files exist

### Step 6: Post-Improvement Validation

After applying changes, verify:

- [ ] SKILL.md body is under 1,200 tokens (target: 845-1,165)
- [ ] Frontmatter uses third person with 5+ trigger phrases
- [ ] Body uses imperative/infinitive form throughout
- [ ] Every major procedure has a working example
- [ ] No factual-only sections remain in SKILL.md (moved to references/)
- [ ] All `references/` files mentioned in SKILL.md actually exist
- [ ] No content teaches standard practices models already know
- [ ] No conflicting guidance without decision criteria

## Key Research Numbers

Quick reference for the most actionable SkillsBench findings:

| Finding | Value | Implication |
|---|---|---|
| Detailed skills | +18.8pp | Step-by-step with examples wins |
| Compact skills | +17.1pp | Focused essentials also effective |
| Comprehensive skills | -2.9pp | Exhaustive docs hurt performance |
| 2-3 skills per task | +18.6pp | Focused scope is optimal |
| 4+ skills per task | +5.9pp | Cognitive overhead reduces gains |
| Self-generated skills | -1.3pp | Human authoring essential |

## Reference Files

For detailed research findings, anti-patterns, and evaluation criteria:
- **`references/skillsbench-findings.md`** — Complete SkillsBench research summary including anti-patterns, evaluation dimensions, and leakage audit criteria
