---
name: root-cause-tracing
description: Use when errors occur deep in execution and you need to trace back to find the original trigger - systematically traces bugs backward through call stack, adding instrumentation when needed, to identify source of invalid data or incorrect behavior
---

# Root Cause Tracing

**Persona:** Methodical detective who traces every symptom back to its source.

**Core principle:** Trace backward through the call chain until you find the original trigger, then fix at the source. NEVER fix just the symptom.

## Should NOT Attempt

- Fix symptoms without finding root cause
- Stop tracing when first guess seems plausible
- Add permanent instrumentation (remove after debugging)
- Trace without recording findings

## When to Use

- Error happens deep in execution (not at entry point)
- Stack trace shows long call chain
- Unclear where invalid data originated
- Need to find which test/code triggers the problem

## The Tracing Process

### 1. Observe Symptom
```
Error: git init failed in /Users/jesse/project/packages/core
```

### 2. Find Immediate Cause
```typescript
await execFileAsync('git', ['init'], { cwd: projectDir }); // What called this?
```

### 3. Trace Up the Call Chain
```typescript
WorktreeManager.createSessionWorktree(projectDir, sessionId)
  -> Session.initializeWorkspace()
  -> Session.create()
  -> test at Project.create()
```

### 4. Find Original Trigger
```typescript
const context = setupCoreTest(); // Returns { tempDir: '' }
Project.create('name', context.tempDir); // Accessed before beforeEach!
```

## Adding Stack Traces

When you cannot trace manually, add instrumentation:

```typescript
async function gitInit(directory: string) {
  console.error('DEBUG git init:', {
    directory, cwd: process.cwd(), stack: new Error().stack,
  });
  await execFileAsync('git', ['init'], { cwd: directory });
}
```

**Tips:**
- Use `console.error()` in tests (logger may be suppressed)
- Log BEFORE the dangerous operation, not after failure
- Include: directory, cwd, env vars, timestamps
- Run: `npm test 2>&1 | grep 'DEBUG git init'`

## Finding Which Test Causes Pollution

Use bisection script: `~/.claude/skills/root-cause-tracing/scripts/find-polluter.sh`

```bash
~/.claude/skills/root-cause-tracing/scripts/find-polluter.sh '.git' 'src/**/*.test.ts'
```

## Real Example

**Symptom:** `.git` created in `packages/core/` (source code)

**Trace:**
1. `git init` runs in `process.cwd()` <- empty cwd parameter
2. WorktreeManager called with empty projectDir
3. Session.create() passed empty string
4. Test accessed `context.tempDir` before beforeEach
5. setupCoreTest() returns `{ tempDir: '' }` initially

**Fix:** Made tempDir a getter that throws if accessed before beforeEach

**Defense-in-depth added:**
- Layer 1: Project.create() validates directory
- Layer 2: WorkspaceManager validates not empty
- Layer 3: NODE_ENV guard refuses git init outside tmpdir
- Layer 4: Stack trace logging before git init

## Escalation Triggers

| Situation | Escalate To |
|-----------|-------------|
| Race condition suspected | `condition-based-waiting` skill |
| Need git history context | `git-archaeologist` agent |
| Security-related bug | `security-reviewer` agent |
| Cannot reproduce locally | Ask user for more context |
| Multi-service issue | `observability-engineer` agent |

## Failure Behavior

- **Cannot reproduce:** Document steps tried, ask for exact reproduction steps
- **Trace leads to external dependency:** Report findings, suggest workarounds
- **Multiple possible causes:** Test each hypothesis systematically
- **Fix causes new failures:** Roll back, trace new symptom

## Key Principle

1. Found immediate cause -> trace one level up
2. Keep tracing until you find the source
3. Fix at source + add validation at each layer = bug impossible

## Save Learnings to Memory

After completing a trace, persist the debugging path:
```
add_observations: [{
  entityName: "ProjectName",
  contents: [
    "Trace: [symptom] -> [intermediate cause] -> [root cause]",
    "Fix location: [file:line]",
    "Pattern: [what to watch for in future]",
    "Defense added: [validation layers if any]"
  ]
}]
```

This helps avoid re-tracing similar issues in future sessions.
