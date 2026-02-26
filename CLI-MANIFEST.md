# CLI-MANIFEST.md — Building Agent-First CLIs

Most CLIs were designed for humans reading terminals. Agents need contracts, not prose.

If output shape changes between commands, errors are only natural language, or writes happen without preview and guardrails, agent automation becomes fragile and expensive.

This manifest defines a practical contract for agent-friendly CLIs:
- one structured response envelope for every command
- stable error and exit-code semantics
- explicit read/write boundaries and safety controls
- plan/validate/apply/verify workflows when risk is high

It is stack-neutral, with implementation hints for Python, TypeScript, and Go.

Use it incrementally:
- Part I for every CLI
- add Parts II-V as your CLI moves from read-only to mutating, transactional, and multi-agent use

| Part | When to apply | Example CLIs |
|------|--------------|-------------|
| I. Foundations | Every agent-facing CLI | All of the below |
| II. Read & Discover | CLIs that expose data for agents to reason over | `kubectl get`, `gh issue list`, `aws s3 ls`, `rg` |
| III. Safe Mutation | CLIs that change state (files, configs, records) | `sed`, `kubectl apply`, `psql`, `gh pr merge` |
| IV. Transactional Workflows | CLIs where mutations are planned, reviewed, then applied | `terraform`, `flyway`, `alembic`, `helm upgrade` |
| V. Multi-Agent Coordination | CLIs used by multiple agents or agents + humans concurrently | Shared file editors, database migration tools, deployment pipelines |

A read-only query tool needs Parts I-II. A config editor needs I-III. A full infrastructure-as-code tool needs all five.

---

# Part I: Foundations

*Apply to every agent-facing CLI, regardless of what it does.*

## 1. Every Command Returns a Structured Envelope

The single most important rule. **Every command — success or failure — returns the same top-level JSON shape.** Agents parse one schema, not N.

```jsonc
{
  "ok": true,                   // Always present. Check this first.
  "command": "resource.list",   // Dotted command ID
  "target": { ... },            // What was acted on (optional for global commands)
  "result": { ... },            // Command-specific payload
  "warnings": [ ... ],          // Non-fatal issues
  "errors": [ ... ],            // Structured errors (code + message)
  "metrics": {                  // Observability
    "duration_ms": 42
  }
}
```

### Minimum contract (strict)

Define a small set of envelope invariants so agents can trust every response shape:

- `schema_version`, `request_id`, `ok`, `command`, `result`, `errors`, `warnings`, and `metrics` are always present.
- `errors` and `warnings` are always arrays (possibly empty), never omitted.
- `result` is always present; on failure use `null`, not missing keys.
- `command` is the canonical dotted command ID, regardless of user-facing aliases.
- `request_id` is unique per invocation and should also appear in stderr diagnostics for correlation.

```jsonc
{
  "schema_version": "1.0",
  "request_id": "req_20260226_143000_7f3a",
  "ok": false,
  "command": "user.create",
  "result": null,
  "warnings": [],
  "errors": [{ "code": "ERR_VALIDATION_REQUIRED", "message": "Missing email" }],
  "metrics": { "duration_ms": 8 }
}
```

**Don't** — different shapes for success vs. error, or mixing text with data:

```
# Success: plain text
Created user 'ada' with role 'viewer'.

# Error: different shape, unstructured
Error: user 'ada' already exists (use --force to overwrite)

# Or worse: JSON on success, text on error
{"user": "ada", "role": "viewer"}    # success
Error: connection refused             # error
```

An agent receiving these must maintain three parsers and hope the format doesn't change between versions.

**Do** — one envelope, always:

```jsonc
// Success
{ "ok": true,  "command": "user.create", "result": { "user": "ada", "role": "viewer" }, "errors": [] }

// Error — same shape
{ "ok": false, "command": "user.create", "result": null, "errors": [{ "code": "ERR_ALREADY_EXISTS", ... }] }
```

**Why it matters:** Agents write one response parser. They check `ok`, branch on `errors[0].code`, and extract `result`. No regex. No guessing.

### Implementation hints

| Language   | Envelope type | Serialization |
|------------|--------------|---------------|
| Python     | Pydantic `BaseModel` with `model_dump()` | `orjson` / `json` |
| TypeScript | Zod schema or interface + discriminated union | `JSON.stringify` |
| Go         | Struct with `json` tags, generic `Result[T]` | `encoding/json` |

---

## 2. Machine-Readable Error Codes, Not Just Messages

Errors carry a **code** (for machines) and a **message** (for humans). Agents branch on codes; they never parse prose.

```jsonc
{
  "errors": [
    {
      "code": "ERR_RESOURCE_NOT_FOUND",  // Stable, documented
      "message": "Resource 'users' not found",
      "details": { "resource": "users" } // Optional structured context
    }
  ]
}
```

### Include retry semantics in every error

Agents need to know whether they should retry, wait, fix input, or escalate. Include retry hints directly in the error object:

```jsonc
{
  "code": "ERR_IO_CONNECTION",
  "message": "Can't connect to localhost:5432",
  "retryable": true,
  "retry_after_ms": 1000,
  "suggested_action": "retry",
  "details": { "host": "localhost", "port": 5432 }
}
```

Suggested `suggested_action` values:
- `retry` (same input, maybe with backoff)
- `fix_input` (validation issue)
- `reauth` (credential refresh needed)
- `escalate` (internal bug or policy block)

**Taxonomy example:**

| Code prefix | Meaning |
|-------------|---------|
| `ERR_VALIDATION_*` | Input didn't pass checks |
| `ERR_CONFLICT_*`   | State mismatch (stale data, lock held) |
| `ERR_IO_*`         | File system / network failure |
| `ERR_AUTH_*`       | Permission / credential issue |
| `ERR_INTERNAL_*`   | Bug — agent should not retry |

Keep codes stable across versions. Add new ones freely; never rename or remove.

**Don't** — errors as prose that agents must regex-match:

```
Error: unable to find table 'users' in database — did you mean 'Users'?
Error: can't connect to database at localhost:5432 (connection refused)
Error: permission denied for user 'readonly' on table 'users'
```

An agent trying to distinguish "not found" from "connection refused" from "permission denied" must pattern-match natural language across versions and locales.

**Do** — agents branch on `code`, humans read `message`:

```jsonc
{ "code": "ERR_RESOURCE_NOT_FOUND", "message": "Table 'users' not found — did you mean 'Users'?", "details": { "resource": "users", "suggestion": "Users" } }
{ "code": "ERR_IO_CONNECTION",      "message": "Can't connect to localhost:5432", "details": { "host": "localhost", "port": 5432 } }
{ "code": "ERR_AUTH_FORBIDDEN",     "message": "Permission denied for user 'readonly'", "details": { "user": "readonly" } }
```

---

## 3. Exit Codes Are a Contract

Map error categories to distinct exit codes so shell scripts and CI pipelines can branch without parsing JSON.

```
0   Success
10  Validation error    (bad input, schema mismatch)
20  Permission denied   (protected resource)
40  Conflict            (stale state, lock contention)
50  I/O error           (file not found, disk full)
90  Internal error      (bug)
```

**Don't** — exit 1 for everything:

```bash
myctl user create --name ""       # exit 1 (validation)
myctl user create --name ada      # exit 1 (duplicate)
myctl user create --name bob      # exit 1 (disk full)
myctl user create --name carol    # exit 1 (bug)
```

An agent can't distinguish "retry later" from "fix input" from "file a bug."

**Do** — distinct exit codes per category:

```bash
myctl user create --name ""       # exit 10 (validation — fix input)
myctl user create --name ada      # exit 40 (conflict — already exists)
myctl user create --name bob      # exit 50 (I/O — retry later)
myctl user create --name carol    # exit 90 (internal — file a bug)
```

**Rule:** One error category per exit code range. Never overload `1` for everything.

### Implementation hints

- **Python (Typer/Click):** `raise SystemExit(code)` or `typer.Exit(code=N)`
- **TypeScript (Commander/oclif):** `process.exit(N)` or throw typed errors
- **Go (Cobra):** `os.Exit(N)` from a deferred handler, or return error codes from `RunE`

---

## 4. Progressive Discovery via Built-In Guide

Agents shouldn't need external docs. Build a **machine-readable guide command** that returns the full CLI schema in one call.

```bash
myctl guide          # Returns JSON: all commands, flags, error codes, examples
myctl --help         # Human-readable overview
myctl <group> --help # Group detail with examples in epilog
```

The guide should include:
- **Command catalog** with input/output schemas
- **Error code taxonomy** and exit code mapping
- **Identifier/ref syntax** your CLI accepts
- **Examples** for common operations

Scale the guide to your CLI's complexity. A simple read-only tool might just list commands and error codes. A transactional tool should also document workflows, safety features, and concurrency rules.

```jsonc
// Abbreviated guide output
{
  "commands": {
    "inspect": { "group": "read", "args": [...], "returns": "ResourceMeta" },
    "apply":   { "group": "write", "args": [...], "flags": ["--dry-run", "--backup"] }
  },
  "error_codes": { "ERR_RESOURCE_NOT_FOUND": { "exit_code": 10, "retryable": false } }
}
```

### Publish command schemas and compatibility policy

The guide should include machine-usable schemas for command inputs and envelopes, plus compatibility guarantees:

```jsonc
{
  "schema_version": "1.0",
  "compatibility": {
    "additive_changes": "minor",
    "breaking_changes": "major"
  },
  "commands": {
    "user.create": {
      "input_schema": { "$ref": "#/$defs/UserCreateInput" },
      "output_schema": { "$ref": "#/$defs/EnvelopeUserCreateResult" }
    }
  }
}
```

Compatibility rule of thumb:
- Add optional fields and new error codes freely (non-breaking).
- Never rename/remove required fields, error codes, or semantic meanings without a major schema bump.

**Don't** — force agents to discover your CLI by trial and error:

```bash
myctl --help                    # "Usage: myctl [command]" ... that's it
myctl user --help               # Lists flags but no examples
myctl user create --name ada    # Error — what other flags are required?
myctl user create --help        # Doesn't mention --email is required
```

The agent burns tokens and API calls probing for valid invocations.

**Do** — one command bootstraps the agent with complete knowledge:

```bash
myctl guide    # Returns every command, flag, error code, workflow, and example as JSON
```

**Why it matters:** An agent calls `guide` once, caches the result, and knows every command, flag, and error code. Zero-shot CLI usage becomes possible.

---

## 5. Command Groups and Consistent Naming

Organize commands into logical groups. Use consistent verb patterns.

```
myctl <noun> <verb>         # e.g., myctl user list
myctl <noun> <verb> --flag  # e.g., myctl user create --dry-run
```

Standard verbs:

| Verb | Meaning | Mutates? |
|------|---------|----------|
| `inspect` / `show` | Detailed view of one resource | No |
| `list` / `ls` | Enumerate resources | No |
| `get` | Read a specific value | No |
| `set` | Write a specific value | Yes |
| `add` / `create` | Create a new resource | Yes |
| `remove` / `rm` / `delete` | Delete a resource | Yes |
| `apply` | Execute a plan | Yes |
| `validate` | Check without mutating | No |
| `verify` | Assert post-conditions | No |

**Don't** — ambiguous verbs that hide intent:

```bash
myctl user run          # Does this read or write?
myctl user process      # Mutation? Query? Both?
myctl user sync         # Which direction? Destructive?
myctl user update       # Update what? The resource? The local cache?
```

**Do** — verbs that telegraph safety:

```bash
myctl user list         # Clearly a read
myctl user inspect      # Clearly a read
myctl user create       # Clearly a write
myctl user delete       # Clearly a write, clearly destructive
```

**Rule:** An agent should be able to predict whether a command mutates state from its verb alone.

---

## 6. Helpful `--help` with Examples

Every command's help text should include concrete examples in an epilog. Agents learn from examples faster than from parameter descriptions.

```
Usage: myctl user create [OPTIONS]

  Create a new user record.

Options:
  --name TEXT     User's display name  [required]
  --email TEXT    Email address  [required]
  --role TEXT     Role assignment (default: viewer)
  --dry-run       Preview changes without writing
  --help          Show this message and exit

Examples:
  # Create a user
  myctl user create --name "Ada Lovelace" --email ada@example.com

  # Preview with dry-run
  myctl user create --name "Ada Lovelace" --email ada@example.com --dry-run

See also: myctl user list, myctl user inspect
```

---

## 7. Terse Output or None (TOON)

stdout is for structured data. Everything else is noise that burns tokens.

This isn't just good for agents — it's good design, period. Humans shouldn't wade through garbage either. But agents make the cost concrete: every decorative line your CLI prints is a token the agent pays for and must discard. In a monorepo build, a single command can dump 750+ tokens of package listings, update notifications, and banners before the actual result. That's context the agent loses for reasoning.

**Don't** — chatty output that buries the signal:

```
$ myctl deploy --env staging
🚀 myctl v2.4.1 — deployment toolkit
Checking for updates... v2.5.0 available! Run `myctl update` to upgrade.

Building packages...
  ✓ @app/core (1.2s)
  ✓ @app/api (0.8s)
  ✓ @app/web (2.1s)

Deploying to staging...
  Uploading artifacts... done.
  Updating load balancer... done.
  Running health checks... done.

✅ Deploy complete! 3 packages deployed to staging in 14.2s.
Visit https://staging.example.com to verify.
```

An agent must now find the actual result in 12 lines of prose. The emoji, the update nag, the per-package build log, the marketing URL — all noise.

**Do** — structured result on stdout, progress on stderr:

```jsonc
// stdout — the only thing the agent parses
{
  "ok": true,
  "command": "deploy",
  "result": {
    "environment": "staging",
    "packages": ["@app/core", "@app/api", "@app/web"],
    "url": "https://staging.example.com"
  },
  "metrics": { "duration_ms": 14200 }
}
```

```
// stderr — optional, for humans watching the terminal
Building @app/core... done (1.2s)
Building @app/api... done (0.8s)
```

### Succeed quietly, fail loudly

The classic Unix convention applies to structured envelopes too. On success, keep the response minimal — the agent needs the result, not congratulations. On failure, get rich: include the error code, a human message, structured details, and enough context that the agent can decide whether to retry, fix input, or escalate.

```jsonc
// Success — minimal, just the facts
{ "ok": true, "result": { "id": "usr_123" } }

// Failure — rich diagnostics
{
  "ok": false,
  "errors": [{
    "code": "ERR_VALIDATION_UNIQUE",
    "message": "Email already registered",
    "details": { "field": "email", "value": "ada@example.com", "existing_id": "usr_042" }
  }]
}
```

### Log sink for verbose operations

For long-running commands (builds, migrations, test suites), write the full verbose output to a log file and return the path in the envelope. The agent reads the summary; it can selectively read the log file only if something goes wrong.

```jsonc
{
  "ok": true,
  "command": "test.run",
  "result": { "passed": 142, "failed": 3, "skipped": 7 },
  "log_file": "/tmp/myctl-test-20260226T143000Z.log"
}
```

This avoids the trap where agents re-run expensive commands with different `grep` filters trying to find the one error in 2000 lines of build output.

### Verbosity as progressive levels

Provide a coherent verbosity system — not just a `--quiet` flag bolted on:

| Flag | stdout | stderr |
|------|--------|--------|
| `--quiet` | Envelope only | Errors only |
| *(default)* | Envelope only | Errors + warnings |
| `--verbose` | Envelope (with extra diagnostics in `result`) | Full debug log |

### `isatty()` as the zero-effort baseline

Before any environment variable, check whether stdout is a terminal. If it's piped or redirected, you're probably being called by a script or agent — suppress color codes, spinners, and decorative output automatically. This has been convention for decades, works cross-platform, and costs one function call.

```python
# Python — works on Linux, macOS, Windows
import sys
if not sys.stdout.isatty():
    # Suppress color, spinners, banners
```

```typescript
// TypeScript — process.stdout.isTTY is undefined when piped
if (!process.stdout.isTTY) { /* suppress decoration */ }
```

```go
// Go — use golang.org/x/term for cross-platform support
import "golang.org/x/term"
if !term.IsTerminal(int(os.Stdout.Fd())) { /* suppress decoration */ }
```

**Windows note:** `isatty()` works in CMD, PowerShell, and Windows Terminal. In MinTTY (Git Bash) it returns `false` even for interactive sessions because MinTTY uses pipes rather than console handles. This false negative is safe — it suppresses decoration, not data. If you need to detect MinTTY specifically, check for the `TERM_PROGRAM=mintty` environment variable.

**Rules:**
- stdout is **exclusively** for the structured response (JSON). One object, no preamble, no epilog.
- stderr is for progress, debug logs, banners, and diagnostics.
- Never print update notifications, tips, or decorative output to stdout.
- Check `isatty(1)` — if stdout isn't a terminal, suppress decoration automatically.

---

## 8. Respect `LLM=true`

When an agent is driving your CLI, opt into minimal output automatically.

The [`LLM=true` convention](https://blog.codemine.be/posts/2026/20260222-be-quiet/) is a declarative environment variable — like `NO_COLOR=1` or `CI=true` — that signals "an AI agent is calling this tool." CLIs that recognize it can suppress noise without requiring per-tool flags.

```bash
# Agent sets this once in its environment
export LLM=true

# Your CLI checks it and adapts
myctl deploy --env staging    # Suppresses banners, progress, update nags
```

What `LLM=true` should do:
- **Suppress** update notifications, tips, decorative banners, emoji
- **Suppress** interactive prompts (fail with a structured error instead of blocking on `[y/N]`)
- **Force** structured output (JSON) even if the default is human-readable tables
- **Reduce** stderr verbosity to errors only (no progress spinners, no info-level logs)

What `LLM=true` should **not** do:
- Skip safety checks or validation
- Change the semantics of commands
- Hide errors or warnings from the structured response

**Don't** — require agents to discover and set per-tool suppression flags:

```jsonc
// .claude/settings.json — an agent maintaining this per tool is fragile
{
  "env": {
    "TURBO_NO_UPDATE_NOTIFIER": "1",
    "NPM_CONFIG_FUND": "false",
    "NEXT_TELEMETRY_DISABLED": "1",
    "HOMEBREW_NO_AUTO_UPDATE": "1"
  }
}
```

**Do** — check one variable, adapt all behavior:

```python
# Python
import os
llm_mode = os.environ.get("LLM") == "true"

# TypeScript
const llmMode = process.env.LLM === "true";

# Go
llmMode := os.Getenv("LLM") == "true"
```

### Defense in depth, not a single dependency

`LLM=true` is an emerging convention, not a standard. Some tool authors will ignore it. Some may never adopt it. Design your CLI in layers so it degrades gracefully:

1. **`isatty()` check** — costs nothing, works everywhere, already convention. Suppresses color and decoration when piped.
2. **TOON by default** — if your CLI follows principle 7, stdout is already clean JSON. `LLM=true` is a no-op.
3. **`LLM=true`** — the extra signal for CLIs that serve both humans and agents. Switches the default output format, suppresses interactive prompts, and reduces stderr noise.
4. **`--quiet` / `--output json`** — explicit flags as the final fallback. Always work, regardless of environment.

If your CLI is agent-first by design (structured envelope on stdout, progress on stderr), `LLM=true` mostly confirms what you already do. It matters most for CLIs that default to human-readable output and need a signal to switch modes.

### Precedence rules and non-interactive auth

Define output-mode precedence so behavior is deterministic:

1. Explicit CLI flags (`--output`, `--quiet`, `--verbose`) take highest precedence.
2. Environment variables (`LLM=true`, `NO_COLOR=1`, `CI=true`) are next.
3. `isatty()` defaults apply when neither flags nor env vars are set.

For authentication in agent mode, use a non-interactive contract:

- Never open browser/device-code prompts when stdin/stdout is non-interactive or `LLM=true`.
- Return structured auth errors (`ERR_AUTH_REQUIRED`, `ERR_AUTH_EXPIRED`) with `details.methods` describing supported auth methods.
- Document credential source precedence (for example: `--token` > `MYCTL_TOKEN` > config file > OS keychain).
- Provide an explicit `auth inspect` or `auth status` command so agents can diagnose auth state without trial-and-error writes.

---

## 9. Observability Built In

Include timing and execution metadata in every response.

```jsonc
{
  "metrics": {
    "duration_ms": 42,
    "operations_executed": 3,
    "bytes_written": 15234
  }
}
```

For long-running operations, consider structured progress events on stderr:

```jsonc
{"event": "progress", "step": 2, "total": 5, "message": "Processing batch..."}
```

**Rule:** stdout is the structured response (JSON). stderr is for progress, debug logs, and diagnostics. Never mix them.

---

## 10. Version Your Output Schema

Include a schema version in your guide and/or envelope so agents can detect breaking changes.

```jsonc
{
  "schema_version": "1.0",
  "ok": true,
  ...
}
```

When you must break the schema, bump the version. Agents that cached the guide can detect the mismatch and re-bootstrap.

---

# Part II: Read & Discover

*Apply when your CLI exposes data for agents to reason over — listing resources, inspecting state, querying records.*

## 11. Separate Reads from Writes

Clearly separate **read** commands (safe to parallelize, retry, cache) from **write** commands (need safety rails).

```
# Read commands — safe, idempotent, parallelizable
myctl inspect
myctl list
myctl query
myctl diff

# Write commands — need safety rails
myctl apply --dry-run     # Preview
myctl apply --backup      # Safe apply
```

Name them so the verb signals intent. An agent should know from the command name alone whether it's safe to run speculatively.

---

## 12. Structured Metadata for Discovery

Read commands should return rich, structured metadata — not just "it exists." Agents plan operations based on what they discover.

```jsonc
// myctl db inspect
{
  "tables": [
    {
      "name": "users",
      "columns": [
        { "name": "id", "type": "integer", "primary_key": true },
        { "name": "email", "type": "text", "nullable": false }
      ],
      "row_count": 10482,
      "indexes": ["idx_users_email"]
    }
  ],
  "fingerprint": "sha256:...",
  "version": "14.2"
}
```

**Don't** — human-readable tables that agents must scrape:

```
$ myctl db inspect
Database: mydb (PostgreSQL 14.2)

Table: users
  id       integer   PK
  email    text      NOT NULL
  role     text      default: 'viewer'

  10,482 rows, 3 indexes
```

An agent must now parse whitespace-aligned columns, understand "PK" means primary key, extract the row count from prose, and handle format changes between versions.

**Do** — structured metadata agents can traverse programmatically:

```jsonc
{
  "tables": [{
    "name": "users",
    "columns": [
      { "name": "id", "type": "integer", "primary_key": true },
      { "name": "email", "type": "text", "nullable": false },
      { "name": "role", "type": "text", "default": "viewer" }
    ],
    "row_count": 10482
  }]
}
```

Expose enough structure that an agent can compose a valid write command from inspect output alone — column names, types, constraints, relationships, counts.

### Deterministic read semantics

Read commands should be deterministic so agents can cache, diff, and paginate reliably:

- Stable default ordering (for example, by primary key or canonical name).
- Cursor pagination (`next_cursor`) instead of offset-only pagination for mutable datasets.
- UTC timestamps in RFC 3339 / ISO-8601 format.
- Locale-independent number/date formatting in structured fields.
- Explicit `sort_by`, `sort_order`, `page_size`, and `cursor` parameters in the guide schema.

If you expose hashes/fingerprints in read output, define exactly what bytes are hashed so two clients produce the same fingerprint.

---

# Part III: Safe Mutation

*Apply when your CLI changes state — writing files, updating records, modifying configs. This is where most CLIs start needing safety rails.*

## 13. Dry-Run on Every Mutation

Every command that changes state must support **`--dry-run`** — execute the full pipeline, return what *would* change, write nothing.

Dry-run responses should include a **change summary** so agents can estimate blast radius before committing:

```jsonc
{
  "dry_run": true,
  "summary": {
    "total_operations": 3,
    "total_records_affected": 150,
    "by_type": { "update": 2, "insert": 1 }
  },
  "changes": [ ... ]  // Full detail
}
```

**Don't** — interactive confirmation prompts:

```
$ myctl user delete --name ada
Are you sure? This will delete 1 user and 47 associated records. [y/N]:
```

Agents can't type "y". Interactive prompts block automation entirely. Even `--yes` just removes the safety without providing information.

**Don't** — dry-run that only says "would succeed":

```
$ myctl user delete --name ada --dry-run
Dry run: operation would succeed.
```

This tells the agent nothing about what would change.

**Do** — dry-run that returns the full change summary as structured data:

```jsonc
{
  "dry_run": true,
  "summary": { "total_records_affected": 48, "by_type": { "delete": 48 } },
  "changes": [
    { "type": "user.delete", "target": "users/ada", "impact": { "cascade": ["records/47"] } }
  ]
}
```

**Why it matters:** Agents plan-then-execute. Dry-run is the "plan" phase. Without it, agents must either guess or mutate blindly.

---

## 14. Change Records with Before/After

Every mutation returns a structured change record so agents know exactly what happened.

```jsonc
{
  "type": "user.create",
  "target": "users/ada",
  "before": null,
  "after": { "name": "Ada Lovelace", "email": "ada@example.com", "role": "viewer" },
  "impact": { "records_affected": 1 }
}
```

**Don't** — success messages that discard context:

```
$ myctl user create --name "Ada Lovelace" --email ada@example.com
Created successfully.

$ myctl user create --name "Ada Lovelace" --email ada@example.com --role admin
Done. 1 record updated.
```

The agent doesn't know what was created, what defaults were applied, or what "1 record updated" actually changed.

**Do** — return the full before/after so the agent can verify and chain:

```jsonc
{
  "type": "user.create",
  "target": "users/ada",
  "before": null,
  "after": { "name": "Ada Lovelace", "email": "ada@example.com", "role": "viewer" },
  "impact": { "records_affected": 1 }
}
```

Now the agent knows the default `role` was `viewer`, can verify the email was stored correctly, and can reference `users/ada` in subsequent commands.

**Why it matters:** Agents need to verify their actions succeeded and understand side effects. "It worked" is not enough — agents need "here is precisely what changed."

---

## 15. Explicit Safety Flags for Dangerous Operations

Don't silently allow dangerous operations. Require explicit opt-in flags.

```bash
# Refuses by default — derived fields are protected
myctl field set --resource users --name score --value 42
# Error: ERR_COMPUTED_OVERWRITE — field 'score' is computed. Use --force to overwrite.

# Explicit opt-in
myctl field set --resource users --name score --value 42 --force-overwrite
```

Other examples:
- `--force` for destructive overwrites
- `--allow-schema-change` for migrations that drop fields
- `--cascade` for operations that affect dependent resources
- `--skip-fingerprint-check` for intentional stale applies

**Don't** — silently succeed at something dangerous:

```bash
$ myctl field set --resource users --name score --value 42
OK.    # Silently overwrote a computed field. Agent doesn't realize it broke a derivation.
```

**Don't** — generic `--force` that suppresses all safety checks at once:

```bash
$ myctl field set --resource users --name score --value 42 --force
OK.    # Which safety check did this bypass? The agent will use --force everywhere now.
```

**Do** — refuse by default, require a specific flag that names the risk:

```bash
$ myctl field set --resource users --name score --value 42
# ERR_COMPUTED_OVERWRITE — field 'score' is computed. Use --force-overwrite-computed to replace.
```

**Rule:** The safe default should require zero flags. Dangerous operations require explicit, well-named flags that document their risk in `--help`.

---

## 16. Backup / Snapshot Before Writing

Support **`--backup`** to snapshot the target before writing (timestamped copy, not in-place).

For file-based CLIs, this means a timestamped copy (e.g., `data.20260226T143000Z.bak`). For API-backed CLIs, this might mean emitting the previous state in the change record so it can be restored.

**Why it matters:** Agents make mistakes. Backups turn irreversible mutations into reversible ones. The cost is trivial; the insurance is enormous.

---

## 17. Atomic Writes

Never write directly to the target file. Write to a temp file, fsync, then atomic-rename.

```
1. Write to .tmp_<random> in the same directory
2. fsync the file descriptor
3. os.rename (atomic on POSIX, near-atomic on Windows)
4. Clean up on failure
```

**Why it matters:** A crash mid-write leaves the original file intact. Without atomic writes, agents can corrupt data and not know it.

This applies to file-backed CLIs. For API-backed CLIs, the equivalent is using database transactions or conditional writes (ETags, optimistic locking).

### Safe retries with idempotency keys

Mutating commands should accept an idempotency key so agents can safely retry after timeouts or transport failures:

```bash
myctl user create --name "Ada Lovelace" --email ada@example.com --idempotency-key req-8f9d
```

```jsonc
{
  "ok": true,
  "command": "user.create",
  "request_id": "req_20260226_143000_7f3a",
  "result": { "user_id": "usr_123" },
  "idempotency": { "key": "req-8f9d", "status": "replayed" }
}
```

Rules:

- Same key + same mutation payload returns the original result (or a typed conflict if payload differs).
- Keys should have a documented retention window (for example, 24 hours).
- Include idempotency status (`new` or `replayed`) in the envelope for traceability.

---

# Part IV: Transactional Workflows

*Apply when mutations are complex enough to benefit from a plan-review-apply cycle — infrastructure tools, schema migration tools, batch processing CLIs.*

## 18. Fingerprint State for Conflict Detection

Before mutating, record a fingerprint (hash) of the target. On apply, reject the operation if the target has changed since planning.

```
plan  →  fingerprint: sha256:abc123
           ...time passes, someone else edits the resource...
apply →  current fingerprint: sha256:def456  ≠  abc123
      →  EXIT 40 — ERR_CONFLICT_FINGERPRINT
```

This is the `terraform plan` pattern. It prevents stale overwrites — the most dangerous failure mode in agent-driven workflows.

### Implementation hints

- **Python:** `hashlib.sha256` over the file bytes
- **TypeScript:** `crypto.createHash('sha256')`
- **Go:** `crypto/sha256`

For API-backed resources, use ETags, version numbers, or `updated_at` timestamps instead of content hashes.

---

## 19. Plan → Validate → Apply → Verify

Design a four-phase mutation workflow. Each phase is a separate command. An agent can stop at any phase.

| Phase        | Command example        | Mutates? | Purpose |
|-------------|----------------------|----------|---------|
| **Plan**     | `myctl plan ...`      | No       | Generate a change spec (JSON/YAML artifact) |
| **Validate** | `myctl validate`      | No       | Check the plan against current state |
| **Apply**    | `myctl apply`         | Yes      | Execute the plan (supports `--dry-run`) |
| **Verify**   | `myctl verify`        | No       | Assert post-conditions hold |

Plans are **first-class artifacts** — files that can be reviewed, diffed, version-controlled, and shared between agents and humans.

```jsonc
// plan.json
{
  "target": { "resource": "users", "fingerprint": "sha256:abc123" },
  "operations": [
    { "op": "add_field", "resource": "users", "name": "full_name" },
    { "op": "update", "resource": "users", "set": { "status": "active" }, "where": { "verified": true } }
  ],
  "options": { "fail_on_external_change": true }
}
```

**Not every CLI needs all four phases.** A simple config editor might only need apply + verify. A full IaC tool needs all four. Match the ceremony to the risk.

---

## 20. Structured Assertions for Verification

After mutations, agents need to verify post-conditions programmatically. Provide a `verify` command that accepts declarative assertions.

```jsonc
// Assertions input
[
  { "type": "resource.exists", "name": "users" },
  { "type": "field.not_null", "resource": "users", "field": "email" },
  { "type": "count.gte", "resource": "users", "min": 100 }
]

// Assertions output
{
  "all_passed": false,
  "results": [
    { "type": "resource.exists", "passed": true },
    { "type": "field.not_null", "passed": true },
    { "type": "count.gte", "passed": false, "expected": 100, "actual": 42, "message": "..." }
  ]
}
```

**Why it matters:** Agents close the loop — plan, apply, verify. Without structured verification, agents must re-inspect and manually diff, which is fragile and slow.

---

## 21. Workflow Composition

For multi-step operations, support a declarative workflow format (YAML or JSON). This lets agents submit a batch of operations as one artifact.

```yaml
name: "Onboard new team"
steps:
  - id: create_group
    run: group.create
    args:
      name: engineering
  - id: add_members
    run: group.add-members
    args:
      group: engineering
      members: [alice, bob, carol]
    depends_on: create_group
  - id: verify
    run: verify.assert
    args:
      assertions:
        - type: group.member_count
          group: engineering
          expected: 3
```

**Why it matters:** Agents generate plans as structured artifacts. Workflows are reviewable, replayable, and composable — unlike shell scripts piping text between commands.

---

# Part V: Multi-Agent Coordination

*Apply when multiple agents (or agents + humans) operate on the same resources concurrently.*

## 22. Resource Locking

If your CLI mutates shared resources, implement exclusive locking. Multiple agents will eventually hit the same resource.

- Use a **sidecar lock file** (e.g., `data.db.lock`) or a lock service for visibility.
- Support **`--wait-lock <seconds>`** for agents that should queue rather than fail immediately.
- Include diagnostics in the lock (PID, timestamp, hostname) for debugging stale locks.
- On lock failure, return a structured error (`ERR_LOCK_HELD`) with the lock owner info.

### Implementation hints

- **Python:** `portalocker` or `fcntl.flock`
- **TypeScript:** `proper-lockfile` or `fd-lock`
- **Go:** `flock(2)` via `syscall` or `os.File.Flock()`

For API-backed resources, use distributed locks (Redis, DynamoDB conditional writes, advisory locks in Postgres).

---

## 23. Document Concurrency Rules

Agents will try to parallelize. Tell them explicitly what's safe.

Include in your guide:

```jsonc
{
  "concurrency": {
    "rule": "Never run multiple write commands on the same resource in parallel.",
    "safe_patterns": [
      "Read commands can run in parallel freely",
      "Write commands to DIFFERENT resources can run in parallel",
      "Chain writes to the SAME resource sequentially or use a workflow file"
    ],
    "unsafe_pattern": "myctl write ... & myctl write ... &  (parallel writes to same resource)"
  }
}
```

**Don't** — leave concurrency behavior undocumented and hope agents figure it out:

```bash
# Agent A and Agent B both run at the same time:
myctl config set --key timeout --value 30 &    # Agent A
myctl config set --key retries --value 5 &     # Agent B
# Result: last write wins silently. One agent's change is lost. Neither knows.
```

**Do** — document the rules, fail loudly on violations, and provide safe alternatives:

```bash
# Concurrent writes fail with ERR_LOCK_HELD
myctl config set --key timeout --value 30      # Agent A acquires lock
myctl config set --key retries --value 5       # Agent B gets ERR_LOCK_HELD, knows to wait

# Or: Agent B queues with --wait-lock
myctl config set --key retries --value 5 --wait-lock 10   # Waits up to 10s for lock
```

Without this, agents will discover the rules through data corruption.

---

# Summary: The Agent-First CLI Checklist

Pick the parts that match your CLI. Each part includes the ones above it.

### Part I — Foundations (every CLI)

| # | Principle | One-liner |
|---|-----------|-----------|
| 1 | Structured envelope | One JSON shape for every command |
| 2 | Error codes | Machines read codes, not messages |
| 3 | Exit codes | Distinct ranges per error category |
| 4 | Built-in guide | Machine-readable CLI schema in one call |
| 5 | Consistent naming | Predictable command groups and verbs |
| 6 | Examples in help | Agents learn from concrete usage |
| 7 | TOON | Terse Output or None — stdout is for data, not decoration |
| 8 | Respect `LLM=true` | One env var switches to agent-optimized output |
| 9 | Observability | Timing and metrics in every response |
| 10 | Schema versioning | Agents detect breaking changes |

### Part II — Read & Discover (query / inspection CLIs)

| # | Principle | One-liner |
|---|-----------|-----------|
| 11 | Read/write separation | Verbs signal mutation intent |
| 12 | Rich metadata | Structured inspect for agent planning |

### Part III — Safe Mutation (state-changing CLIs)

| # | Principle | One-liner |
|---|-----------|-----------|
| 13 | Dry-run | Preview every write before committing |
| 14 | Change records | Before/after for every mutation |
| 15 | Explicit safety flags | Dangerous ops require opt-in |
| 16 | Backup / snapshot | Reversible mutations by default |
| 17 | Atomic writes | Never corrupt on crash |

### Part IV — Transactional Workflows (plan-review-apply CLIs)

| # | Principle | One-liner |
|---|-----------|-----------|
| 18 | Fingerprinting | Detect stale state before overwriting |
| 19 | Plan/validate/apply/verify | Four-phase mutation workflow |
| 20 | Structured assertions | Declarative post-condition checks |
| 21 | Workflow composition | Multi-step plans as reviewable artifacts |

### Part V — Multi-Agent Coordination (shared-resource CLIs)

| # | Principle | One-liner |
|---|-----------|-----------|
| 22 | Resource locking | Serialize concurrent writes |
| 23 | Concurrency docs | Tell agents what's safe to parallelize |

### Production Hardening Add-ons

| Add-on | One-liner |
|---|---|
| Strict envelope invariants | Required keys + nullability + `request_id` on every response |
| Retry semantics in errors | Add `retryable`, `retry_after_ms`, and `suggested_action` |
| Deterministic reads | Stable sort, cursor pagination, UTC timestamps, locale-neutral fields |
| Non-interactive auth contract | Never block on browser prompts; return structured auth errors |
| Schema publication policy | Include per-command input/output schemas and compatibility guarantees |
| Idempotency keys for writes | Safe retries after network or process failures |
| Output precedence rules | `flags > env vars > isatty()` defaults |

---

*Build CLIs like APIs. If an LLM can't drive it zero-shot from `guide` + `--help`, it's not agent-ready.*
