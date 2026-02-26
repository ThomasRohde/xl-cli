# SkillsBench Research Findings

Source: "SkillsBench: Benchmarking How Well Agent Skills Work Across Diverse Tasks" (arXiv:2602.12670v1)

This paper evaluated 7,308 agent trajectories across 84 tasks and 11 domains, testing curated vs. self-generated Skills across 7 model configurations. The findings directly inform how to author effective Skills.

## Core Results

### 1. Curated Skills Provide +16.2pp Average Improvement

Curated (human-authored) Skills improved agent performance by an average of +16.2 percentage points. However, effectiveness varies significantly (+13.6pp to +23.3pp) depending on model and harness combination.

### 2. Self-Generated Skills Fail (-1.3pp)

When models were prompted to generate their own procedural knowledge before solving tasks, performance decreased by -1.3pp compared to baseline. Only one model (Opus 4.6) showed modest improvement (+1.4pp). Models cannot reliably self-generate effective domain expertise.

**Implication for skill improvement:** Automated rewriting without human review is unreliable. Improvements must be human-validated.

### 3. Moderate Length Outperforms Comprehensive Documentation

| Skill Length | Avg Improvement | Description |
|---|---|---|
| Detailed (~1,165 tokens) | +18.8pp | Step-by-step with examples |
| Compact (~845 tokens) | +17.1pp | Focused essentials |
| Comprehensive (~2,500+ tokens) | -2.9pp | Exhaustive documentation |

**Critical finding:** Comprehensive documentation actually *hurts* performance. Focused, procedural guidance outperforms exhaustive documentation by 21+ percentage points.

**Token count guidance:**
- SKILL.md body (excluding frontmatter) should target 845-1,165 tokens
- Roughly equivalent to 1,200-1,800 words of markdown
- References files are loaded on-demand and don't count toward this

### 4. Less Is More: 2-3 Skills Optimal Per Task

| Number of Skills | Avg Improvement |
|---|---|
| 1 Skill | +14.2pp |
| 2-3 Skills | +18.6pp |
| 4+ Skills | +5.9pp |

Excessive skills create cognitive overhead. When a single skill covers too many topics, consider splitting into focused sub-skills.

### 5. Domain Variation Is Extreme

Domains with specialized procedural knowledge rarely covered in pretraining benefit most:
- Healthcare: +51.9pp
- Manufacturing: +41.9pp
- Software Engineering: +4.5pp (lowest)

**Implication:** Skills should focus on procedures and knowledge that models are unlikely to know from pretraining. Standard programming patterns provide minimal value as skill content.

### 6. Skills Can Hurt Performance (16 of 84 Tasks)

In 16 tasks, skills produced negative results. Root causes:
- Conflicting guidance that confuses the agent
- Unnecessary complexity for tasks models already handle well
- Overly prescriptive procedures that prevent flexible problem-solving
- Information that contradicts model's correct pretraining knowledge

## What Makes an Effective Skill

### The Four Criteria (from paper)

1. **Procedural content**: How-to guidance (procedures, workflows, SOPs), not factual retrieval
2. **Task-class applicability**: Applies to problem classes, not single instances
3. **Structured components**: SKILL.md file plus optional resources
4. **Portability**: File-system-based, no external dependencies

### Key Effectiveness Factors

1. **Procedural specificity**: Step-by-step workflows for specialized domains
2. **Working examples**: "Stepwise guidance with at least one working example" — code templates and reference implementations matter more than documentation
3. **Focused scope**: Target 2-3 skills of moderate length rather than one comprehensive skill
4. **Harness alignment**: Skills should match the execution environment's constraints and capabilities
5. **Procedural gap targeting**: Focus on knowledge underrepresented in model pretraining

### Skills vs. Other Augmentation

The paper distinguishes Skills from:
- **System prompts**: Lack structure and bundled resources
- **Few-shot examples**: Declarative, not procedural
- **RAG retrievals**: Factual lookup, not procedural guidance
- **Tool documentation**: Describes capabilities, not how to use them in workflows

## Anti-Patterns Identified

### Anti-Pattern 1: Encyclopedic Coverage
Writing a skill that attempts to document everything about a domain. Results in comprehensive (-2.9pp) rather than detailed (+18.8pp) performance.

**Symptom:** SKILL.md exceeds ~1,200 tokens of body content. Dense reference tables dominate over procedural steps.

**Fix:** Extract reference material to `references/` files. Keep SKILL.md focused on procedural steps with minimal examples.

### Anti-Pattern 2: Factual Instead of Procedural
Skill reads like API documentation or a reference manual rather than a workflow guide.

**Symptom:** Content describes *what things are* rather than *how to use them*. Lists of properties, types, or options without workflow context.

**Fix:** Restructure around tasks: "To accomplish X, do Y" with step-by-step procedures.

### Anti-Pattern 3: Conflicting or Redundant Guidance
Skill provides multiple approaches for the same task without clear guidance on when to use each, or restates information the model already knows well.

**Symptom:** "You can do X, or alternatively Y, or also Z" without decision criteria. Performance decreases when skill is loaded.

**Fix:** Pick the recommended approach, make it the default, mention alternatives only with clear decision criteria.

### Anti-Pattern 4: Missing Working Examples
Skill describes procedures abstractly without concrete, copy-pasteable code.

**Symptom:** Procedural steps reference APIs or patterns without showing them in context.

**Fix:** Add at least one complete working example per major procedure.

### Anti-Pattern 5: Overly Prescriptive for Well-Known Tasks
Skill provides detailed instructions for tasks models handle well from pretraining (e.g., basic JavaScript patterns, common git workflows).

**Symptom:** Skill content covers standard programming practices. Low or negative improvement when tested.

**Fix:** Remove content that teaches standard practices. Focus on domain-specific, non-obvious procedures.

## Evaluation Dimensions

The paper's human review evaluates five criteria relevant to skill quality:

1. **Data validity**: Does the skill address real-world complexity?
2. **Task realism**: Does it reflect professional workflows?
3. **Skill quality**: Is it error-free, consistent, and useful?
4. **Anti-cheating**: Does it guide without over-specifying solutions?
5. **Leakage prevention**: Does it teach procedures, not specific solutions?

## Leakage Audit Criteria

Skills must NOT contain:
- Task-specific filenames, paths, or identifiers
- Exact command sequences that solve specific tasks
- Constants or magic numbers from specifications
- References to test cases or expected outputs

Skills SHOULD contain:
- General procedures applicable to a class of tasks
- Decision frameworks for choosing approaches
- Working examples that demonstrate patterns (not solutions)
- Non-obvious constraints and pitfalls
