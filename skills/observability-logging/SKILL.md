---
name: observability-logging
description: Use when adding logging, debugging distributed systems, or implementing error handling - patterns for structured, correlated, useful logs
---

# Observability & Logging

**Persona:** SRE who designs logs for debugging production incidents at 3am.

**Core principle:** Logs should answer "what happened, when, where, and why" without guessing.

## Should NOT Attempt

- Log sensitive data (passwords, tokens, PII)
- Log in tight loops (performance impact)
- Use unstructured string interpolation
- Skip correlation IDs in distributed systems
- Log without context (bare exception logging)

## Log Levels

| Level | Use For |
|-------|---------|
| ERROR | Failures requiring attention |
| WARN | Unexpected but handled |
| INFO | Key business operations |
| DEBUG | Diagnostic details |
| TRACE | Verbose debugging only |

## Structured Logging

```python
# BAD: Unstructured
logger.info(f"User {user_id} created order {order_id} for ${amount}")

# GOOD: Structured
logger.info("Order created", extra={
    "event": "order.created",
    "user_id": user_id,
    "order_id": order_id,
    "amount_cents": amount_cents
})
```

## Correlation IDs

```python
# Middleware sets trace/request IDs from headers or generates them
trace_id: ContextVar[str] = ContextVar('trace_id')

# Logger includes them automatically
class CorrelatedLogger:
    def info(self, message, **kwargs):
        kwargs['trace_id'] = trace_id.get()
        self._log('INFO', message, kwargs)

# Propagate to downstream services
headers = {'X-Trace-ID': trace_id.get()}
```

## What to Log

**Always:** Business events, errors with context, security events
**Never:** Passwords, API keys, tokens, PII, full request bodies

```python
# Error with context
logger.error("Payment failed", extra={
    "order_id": order.id,
    "error_type": type(e).__name__,
    "retry_count": retries
}, exc_info=True)
```

## Performance Logging

```python
@contextmanager
def log_timing(operation: str, **context):
    start = time.perf_counter()
    try:
        yield
    finally:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(f"{operation} completed", extra={
            "duration_ms": round(duration_ms, 2), **context
        })
```

## Checklist

- [ ] Appropriate log level?
- [ ] Human-readable message?
- [ ] Key fields structured (not in message)?
- [ ] No sensitive data?
- [ ] Correlation IDs included?
- [ ] Error logs include stack trace?

## Escalation Triggers

| Situation | Escalate To |
|-----------|-------------|
| Debugging distributed issue | `observability-engineer` agent |
| Log volume too high | Review log levels, add sampling |
| Sensitive data in logs detected | Immediate remediation, security review |
| Logs not queryable | Review structure, add missing fields |

## Failure Behavior

- **Logger fails:** Never crash application, degrade gracefully
- **Log destination unavailable:** Buffer locally, retry with backoff
- **Sensitive data logged:** Report immediately, plan remediation
- **Correlation ID missing:** Generate new one, log warning

## Red Flags

- Unstructured logging in message string
- Logging in tight loops
- `except: logger.error(e)` - no context
- No correlation IDs
