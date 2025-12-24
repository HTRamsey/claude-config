---
name: api-versioning
description: Use when designing APIs, making breaking changes, or planning deprecation - consistent versioning strategy for evolving APIs
---

# API Versioning

**Persona:** API steward who protects existing clients while enabling evolution.

**Core principle:** Never break existing clients. Deprecate gracefully, remove eventually.

## Should NOT Attempt

- Make breaking changes without version bump
- Remove fields without deprecation period (6+ months)
- Maintain more than 2 active major versions
- Version business logic (only version API layer)
- Skip migration guides for major changes

## When to Use

- Designing new API
- Making breaking changes
- Deprecating endpoints
- Planning API evolution

## Versioning Strategies

| Strategy | Example | Pros | Cons |
|----------|---------|------|------|
| **URL Path** (Recommended) | `/api/v1/users` | Clear, easy to route, cache-friendly | Duplicated routes |
| Header | `Accept: application/vnd.api+json; version=2` | Clean URLs | Hidden, harder to test |
| Query | `/api/users?version=2` | Easy to test | Not RESTful, caching issues |

**Recommendation:** URL path for major versions, header for minor versions within a major.

## Breaking vs Non-Breaking Changes

| Breaking (New Version Required) | Non-Breaking (Version Optional) |
|--------------------------------|--------------------------------|
| Remove endpoint/field | Add new endpoint |
| Change field type/semantics | Add optional parameter |
| Rename field | Add new response field |
| Add required parameter | Deprecate (not remove) field |
| Change auth/error format | Performance/bug fixes |

## Evolution Patterns

### Adding Fields (Safe)
Clients should ignore unknown fields. Add new fields without version bump.

### Deprecating Fields
```
Phase 1: Mark deprecated (Deprecation: true header, Sunset date)
Phase 2: Document with migration guide
Phase 3: Remove in next major version
```

### Changing Field Type
```
Phase 1: Add new field alongside old (created -> created_at)
Phase 2: Deprecate old field
Phase 3: Remove old in next major version
```

## Version Lifecycle

```
CURRENT -> DEPRECATED -> SUNSET -> REMOVED
   |           |          |
   Active      Headers    Warning period (6+ months)
```

**Example:** Jan 2024: v2 released, v1 deprecated -> Jul 2024: v1 sunset warning -> Jan 2025: v1 removed

## Implementation

```python
# Router-level versioning (FastAPI)
v1_router = APIRouter(prefix="/api/v1")
v2_router = APIRouter(prefix="/api/v2")

# Deprecation headers
response.headers["Deprecation"] = "true"
response.headers["Sunset"] = "Sat, 01 Jan 2025 00:00:00 GMT"
response.headers["Link"] = '</api/v2/users/{id}>; rel="successor-version"'
```

**Key:** Share business logic across versions; only version the API layer.

## Documentation

```yaml
# OpenAPI: Mark deprecated operations
paths:
  /users/{id}:
    get:
      deprecated: true
      x-sunset: "2025-01-01"
```

Provide migration guides with field mapping tables and code examples.

## Output Format

When recommending version strategy:
```
VERSIONING RECOMMENDATION

Change type: [Breaking|Non-breaking]
Current version: vX.Y.Z
Recommended: [vX+1.0.0 | vX.Y+1.0 | vX.Y.Z+1]

Migration plan:
1. [Phase 1 - what to do]
2. [Phase 2 - what to do]

Timeline:
- [Date]: [action]
- [Date]: [action]

Deprecation notice (if applicable):
Sunset: [date]
Successor: [new endpoint/field]
```

## Red Flags

- Breaking changes without version bump
- Removing fields without deprecation period
- No sunset date for deprecated versions
- Versioning business logic (not just API layer)
- More than 2 active major versions

## Escalation Triggers

| Situation | Escalate To |
|-----------|-------------|
| Breaking change unavoidable | Plan multi-phase migration, ask user for timeline |
| Client compatibility unknown | Research usage patterns before deciding |
| Auth/security format change | `security-reviewer` agent |
| Major API redesign | `api-designer` agent |

## Failure Behavior

- **Cannot avoid breaking change:** Document clearly, provide migration path, extend deprecation
- **Client on unsupported version:** Provide upgrade guide, suggest compatibility shim
- **Unclear if change is breaking:** Assume breaking, treat conservatively
- **Sunset date approaching:** Warn proactively, check for stragglers

## Save Learnings to Memory

After making versioning decisions, persist for consistency:
```
add_observations: [{
  entityName: "ProjectName-API",
  contents: [
    "Versioning strategy: [URL path | header | query]",
    "Current version: vX.Y.Z",
    "Deprecation policy: [N months notice]",
    "Breaking change: [what triggered version bump]",
    "Migration pattern used: [expand-contract | etc]"
  ]
}]
```

This ensures consistent versioning decisions across the project lifecycle.

## Integration

- **architecture-decision-records** - Document versioning strategy as ADR
- **incremental-implementation** - Ship version changes incrementally
- **error-handling-patterns** - Consistent error format across versions
