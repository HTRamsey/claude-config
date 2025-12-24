---
name: feature-flag-patterns
description: Use when implementing features needing controlled rollout, working on trunk/main branch, or enabling trunk-based development - patterns for safe, incremental releases
---

# Feature Flag Patterns

**Persona:** Release engineer who enables safe, incremental rollouts.

**Core principle:** Deploy frequently, release strategically. Flags are temporary--plan for removal.

## Should NOT Attempt

- Create flags without cleanup dates
- Nest multiple flags in complex conditions
- Use one flag for unrelated features
- Test only one flag state
- Keep "temporary" flags beyond their purpose

## Flag Types

| Type | Lifespan | Example |
|------|----------|---------|
| Release | Days-weeks | New checkout flow |
| Experiment | Weeks | A/B test button color |
| Ops | Permanent | Maintenance mode |
| Permission | Permanent | Premium features |

## Naming: `{type}_{feature}_{variant}`
Examples: `release_new_checkout`, `exp_button_color_blue`, `ops_maintenance_mode`

## Implementation Patterns

### Simple Conditional
```typescript
if (flags.isEnabled('release_new_checkout')) return <NewCheckout />;
return <LegacyCheckout />;
```

### Branching by Abstraction
```typescript
class PaymentService {
  private processor: PaymentProcessor;
  constructor(flags: FeatureFlags) {
    this.processor = flags.isEnabled('release_new_payments')
      ? new StripeProcessor() : new LegacyProcessor();
  }
}
```

### Percentage Rollout
```typescript
function shouldShow(userId: string): boolean {
  return (hashUserId(userId) % 100) < flags.getPercent('release_new_search');
}
```

## Testing

```typescript
describe('with flag enabled', () => {
  beforeEach(() => flags.enable('release_new_checkout'));
  it('shows new UI', () => {});
});

describe('with flag disabled', () => {
  beforeEach(() => flags.disable('release_new_checkout'));
  it('shows legacy UI', () => {});
});
```

## Lifecycle

```
CREATE (default OFF) -> DEVELOP -> TEST -> ROLLOUT (1%->10%->100%) -> STABILIZE -> CLEANUP
```

### Cleanup Checklist
- [ ] At 100% for >1 week, no incidents
- [ ] Remove flag checks, delete old code
- [ ] Remove from config, update tests

## Anti-Patterns

| Pattern | Problem | Fix |
|---------|---------|-----|
| Flag soup | Too many flags | Limit active, cleanup aggressively |
| Nested flags | `if (A && B && !C)` | Combine or refactor |
| Permanent "temporary" | Never removed | Set expiration dates |
| No default | Crash if missing | Always have default |

## Escalation Triggers

| Situation | Escalate To |
|-----------|-------------|
| Flag causing production issues | Immediate rollback, then investigate |
| Too many active flags (>10) | Plan cleanup sprint |
| Flag needed for >3 months | Convert to permanent config or remove |
| A/B test needs statistical analysis | Involve data team |

## Failure Behavior

- **Flag evaluation fails:** Use safe default (usually OFF for new features)
- **Rollout causes errors:** Roll back percentage, investigate
- **Cannot determine user segment:** Fall back to default behavior
- **Stale flag detected:** Report for cleanup, don't auto-remove

## Red Flags

- Flags for small changes (overhead not worth it)
- Flags without cleanup dates
- Testing only one flag state
- One flag controlling unrelated features
