# Async Patterns

## Python

### Concurrent execution
```python
import asyncio

async def fetch_all(urls: list[str]) -> list[Response]:
    tasks = [fetch(url) for url in urls]
    return await asyncio.gather(*tasks, return_exceptions=True)
```

### Rate limiting
```python
import asyncio

class RateLimiter:
    def __init__(self, rate: int, period: float = 1.0):
        self.rate = rate
        self.period = period
        self.semaphore = asyncio.Semaphore(rate)

    async def acquire(self):
        await self.semaphore.acquire()
        asyncio.get_event_loop().call_later(
            self.period, self.semaphore.release
        )
```

## JavaScript/TypeScript

### Promise.all with error handling
```typescript
async function fetchAllSafe<T>(
  promises: Promise<T>[]
): Promise<Array<T | Error>> {
  return Promise.all(
    promises.map(p => p.catch(e => e))
  );
}
```

### Retry with backoff
```typescript
async function retry<T>(
  fn: () => Promise<T>,
  maxAttempts = 3,
  baseDelay = 1000
): Promise<T> {
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      return await fn();
    } catch (error) {
      if (attempt === maxAttempts) throw error;
      await new Promise(r =>
        setTimeout(r, baseDelay * Math.pow(2, attempt - 1))
      );
    }
  }
  throw new Error('Unreachable');
}
```

### Debounce
```typescript
function debounce<T extends (...args: any[]) => any>(
  fn: T,
  delay: number
): (...args: Parameters<T>) => void {
  let timeoutId: ReturnType<typeof setTimeout>;
  return (...args) => {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => fn(...args), delay);
  };
}
```
