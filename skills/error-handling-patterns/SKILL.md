---
name: error-handling-patterns
description: Use when implementing error handling, designing APIs, or reviewing error-prone code - consistent patterns for robust error management
---

# Error Handling Patterns

**Persona:** Reliability engineer who treats errors as first-class features - every error path intentionally designed.

**Core principle:** Fail fast, fail loud, fail helpfully. Silent failures are worst.

## Error Types

| Type | Examples | Handle |
|------|----------|--------|
| Operational (expected) | Network timeout, file not found, invalid input | Recover, retry, or inform user |
| Programmer (bugs) | Null reference, type errors | Fix the code, don't suppress |

## Should NOT Attempt

- Empty catch blocks (`catch {}`)
- Catching all exceptions without discrimination
- Logging AND re-throwing the same error
- Returning null/undefined for error conditions
- Swallowing errors "temporarily"

## Strategies

### Result Type (explicit handling)
```typescript
type Result<T, E> = { ok: true; value: T } | { ok: false; error: E };

function parseJson(input: string): Result<object, ParseError> {
  try {
    return { ok: true, value: JSON.parse(input) };
  } catch (e) {
    return { ok: false, error: new ParseError(e.message) };
  }
}
```

### Custom Exceptions (when caller must handle)
```python
class InsufficientStock(OrderError):
    def __init__(self, product_id, requested, available):
        self.product_id, self.requested, self.available = product_id, requested, available
        super().__init__(f"Insufficient stock for {product_id}")
```

## Error Propagation

```python
# Add context when re-throwing
try:
    process_payment(order)
except PaymentError as e:
    raise OrderError(f"Failed order {order.id}", order_id=order.id, cause=e) from e
```

## Retry with Backoff

```python
async def retry_with_backoff(op, max_retries=3, base_delay=1.0, retryable=(ConnectionError, TimeoutError)):
    for attempt in range(max_retries + 1):
        try:
            return await op()
        except retryable as e:
            if attempt == max_retries: raise
            await asyncio.sleep(min(base_delay * (2 ** attempt), 30.0))
```

## HTTP Status Mapping

| Error Type | Status | When |
|------------|--------|------|
| Validation | 400 | Bad request format |
| Auth | 401/403 | Missing creds / No permission |
| Not Found | 404 | Resource doesn't exist |
| Rate Limited | 429 | Too many requests |
| Server Error | 500 | Unexpected internal |

## Escalation Triggers

| Condition | Action |
|-----------|--------|
| Same error type >3 times in call chain | Consolidate error handling at higher level |
| Error requires >2 retry strategies | Extract to dedicated retry service |
| Error message exposed to users | Security review for information leakage |
| Error rate >1% in production | Incident response, not just logging |

## Failure Behavior

When error handling itself fails:
- Log the meta-error with full context
- Fall back to generic safe error response
- Never expose internal details to external callers
- Alert on error-handling failures (they indicate systemic issues)

## Anti-Patterns

| Pattern | Problem | Fix |
|---------|---------|-----|
| Empty catch | `catch {}` | Log or re-throw |
| Pokemon catch | `catch (Exception)` | Catch specific types |
| Silent failure | Return null | Return Result or throw |
| Log and throw | Duplicate handling | Do one or other |

## Error Logging

```python
logger.error("Payment failed", extra={
    "error_type": type(e).__name__, "order_id": order.id, "user_id": user.id
}, exc_info=True)
```

## Output Schema (for error responses)

```json
{
  "error": {
    "code": "INSUFFICIENT_STOCK",
    "message": "Not enough inventory for item SKU-123",
    "details": {
      "product_id": "SKU-123",
      "requested": 5,
      "available": 2
    },
    "request_id": "req-abc-123"
  }
}
```

## Checklist

- [ ] Expected errors handled explicitly
- [ ] Errors include sufficient context
- [ ] User-facing errors are helpful (not leaking internals)
- [ ] Retryable ops have retry logic
- [ ] Error chain preserved when wrapping
