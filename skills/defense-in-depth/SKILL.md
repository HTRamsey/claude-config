---
name: defense-in-depth
description: Use when invalid data causes failures deep in execution, requiring validation at multiple system layers - validates at every layer data passes through to make bugs structurally impossible
---

# Defense-in-Depth Validation

**Persona:** Paranoid systems engineer who assumes every layer will receive bad data - trust nothing, verify everything.

**Core principle:** Validate at EVERY layer data passes through. Make bugs structurally impossible.

Single validation: "We fixed the bug"
Multiple layers: "We made the bug impossible"

## Should NOT Attempt

- Validate only at entry point ("the caller checked it")
- Trust internal function parameters
- Skip validation for "performance" without measurement
- Add validation without corresponding tests

## The Four Layers

| Layer | Purpose | Example |
|-------|---------|---------|
| 1. Entry Point | Reject invalid input at API boundary | Check not empty, exists, is directory |
| 2. Business Logic | Data makes sense for operation | Validate required fields for this action |
| 3. Environment Guards | Prevent danger in specific contexts | Refuse git init outside tmpdir in tests |
| 4. Debug Instrumentation | Capture context for forensics | Log directory, cwd, stack before risky ops |

## Example Implementation

```typescript
// Layer 1: Entry validation
function createProject(name: string, dir: string) {
  if (!dir?.trim()) throw new Error('dir cannot be empty');
  if (!existsSync(dir)) throw new Error(`dir not found: ${dir}`);
}

// Layer 2: Business logic
function initWorkspace(projectDir: string) {
  if (!projectDir) throw new Error('projectDir required');
}

// Layer 3: Environment guard
async function gitInit(dir: string) {
  if (process.env.NODE_ENV === 'test' && !dir.startsWith(tmpdir())) {
    throw new Error(`Refusing git init outside temp: ${dir}`);
  }
}

// Layer 4: Debug instrumentation
logger.debug('About to git init', { dir, cwd: process.cwd(), stack: new Error().stack });
```

## When to Apply

When you find a bug caused by invalid data:
1. **Trace data flow** - Where does bad value originate?
2. **Map checkpoints** - Every point data passes through
3. **Add validation at each layer**
4. **Test each layer** - Bypass layer 1, verify layer 2 catches it

## Examples

### Example 1: Empty String Causes Crash
**Bug:** `git init` runs in wrong directory when path is empty
**Layers added:**
- Layer 1 (API): `if (!path?.trim()) throw new Error('path required')`
- Layer 2 (Business): `if (!isAbsolute(path)) throw new Error('absolute path required')`
- Layer 3 (Environment): `if (NODE_ENV === 'test' && !path.startsWith(tmpdir())) throw`
- Layer 4 (Debug): `logger.debug('git init', { path, cwd, stack })`

### Example 2: SQL Injection via User Input
**Bug:** Username passed directly to query
**Layers added:**
- Layer 1 (API): Validate against regex `^[a-zA-Z0-9_]+$`
- Layer 2 (Business): Parameterized query regardless of input
- Layer 3 (Database): User has minimal permissions
- Layer 4 (Audit): Log all queries with parameters

### Example 3: File Path Traversal
**Bug:** User-provided filename allows `../../../etc/passwd`
**Layers added:**
- Layer 1 (API): Reject paths containing `..`
- Layer 2 (Business): `path.resolve()` then verify starts with allowed dir
- Layer 3 (Environment): Chroot/container isolation
- Layer 4 (Monitor): Alert on any path resolution outside allowed dirs

## Escalation Triggers

| Condition | Action |
|-----------|--------|
| Invalid data crosses >3 layers undetected | Architecture review needed |
| Same invalid data pattern recurs | Add type-level constraint (branded types, enums) |
| Validation logic duplicated across layers | Extract to shared validator module |
| Performance impact >5% from validation | Profile and optimize hot paths only |

## Failure Behavior

If defense-in-depth cannot be fully implemented:
- Document which layers have validation
- Add `// TODO: Add Layer N validation` comments
- Create follow-up task with specific layer gaps
- Never ship with only Layer 1 validation for critical paths

## Key Insight

All four layers are necessary. During testing, each layer catches bugs others miss:
- Different code paths bypass entry validation
- Mocks bypass business logic
- Edge cases need environment guards
- Debug logging identifies structural misuse

**Don't stop at one validation point.**

## Save Learnings to Memory

After implementing defense-in-depth for a bug, persist the pattern:
```
add_observations: [{
  entityName: "ProjectName",
  contents: [
    "Validation pattern: [data type] requires [layers]",
    "Layer 1: [entry validation added]",
    "Layer 2: [business logic check]",
    "Layer 3: [environment guard if applicable]",
    "Lesson: [what made this bug possible]"
  ]
}]
```

This prevents similar bugs across the codebase and sessions.

## Related Skills

- `root-cause-tracing` - Trace where bad data originates
- `systematic-debugging` - Parent debugging workflow
- `test-driven-development` - Verify each validation layer
