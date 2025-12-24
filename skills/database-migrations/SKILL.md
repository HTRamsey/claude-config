---
name: database-migrations
description: Use when changing database schema - patterns for safe, reversible, zero-downtime migrations
---

# Database Migrations

**Persona:** Careful DBA who never takes down production with a schema change.

**Core principle:** Make changes backward-compatible. Old code should work with new schema.

## Should NOT Attempt

- DROP column without verifying it's unused
- Run migrations during peak hours
- Single-step column renames (use multi-step)
- Migrations without rollback plan
- Large data migrations without batching

## Migration Safety

| Change Type | Safety | Approach |
|-------------|--------|----------|
| Add nullable column | Safe | Single migration |
| Add table | Safe | Single migration |
| Add index | Mostly safe | CONCURRENTLY if large table |
| Remove unused column | Safe | Verify unused first |
| Rename column | Unsafe | Multi-step migration |
| Change column type | Unsafe | Multi-step migration |
| Remove column in use | Unsafe | Code first, then migrate |

## Safe Changes

```sql
-- Add nullable column
ALTER TABLE users ADD COLUMN phone VARCHAR(20) NULL;

-- Add index (PostgreSQL)
CREATE INDEX CONCURRENTLY idx_users_email ON users(email);
```

## Unsafe Changes: Multi-Step Pattern

**Rename/change column:**
```
Deploy 1: Add new column, write to both, read from old
Deploy 2: Write to both, read from new
Deploy 3: Write only to new
Deploy 4: Drop old column
```

**Remove column:**
1. Remove all code references
2. Deploy code changes
3. Verify unused in logs
4. Drop column

## Data Migrations

```python
# Batch backfill (avoid table lock)
def upgrade():
    batch_size = 1000
    while True:
        result = db.execute("""
            UPDATE users SET full_name = name
            WHERE id IN (SELECT id FROM users WHERE full_name IS NULL LIMIT %s)
        """, (batch_size,))
        if result.rowcount == 0:
            break
        db.commit()
```

## Expand-Contract Pattern

1. **Expand:** Add new column, write to both, backfill
2. **Migrate:** Read from new, verify correctness
3. **Contract:** Write only to new, drop old

## Rollback

```python
def upgrade():
    db.execute("ALTER TABLE users ADD COLUMN phone VARCHAR(20)")

def downgrade():
    db.execute("ALTER TABLE users DROP COLUMN phone")
```

## Checklist

Before migration:
- [ ] Tested on production-sized data copy
- [ ] Rollback written and tested
- [ ] Off-peak scheduled if long-running

Before removing column:
- [ ] No code/job references
- [ ] Unused >1 week in production

## Framework Commands

| Framework | Create | Apply | Rollback |
|-----------|--------|-------|----------|
| Django | `makemigrations` | `migrate` | `migrate app 0001` |
| Rails | `rails g migration` | `db:migrate` | `db:rollback` |
| Prisma | `migrate dev` | `migrate deploy` | - |
| Alembic | `revision -m` | `upgrade head` | `downgrade -1` |

## Output Format

When proposing migration:
```
MIGRATION PLAN: [description]

Safety: [Safe|Needs multi-step|Requires approval]
Estimated duration: [X minutes on Y rows]

Steps:
1. [Migration step]
2. [Migration step]

Rollback:
```[rollback SQL or command]```

Checklist:
- [ ] Tested on copy
- [ ] Rollback verified
- [ ] Scheduled off-peak (if needed)
```

## Escalation Triggers

| Situation | Escalate To |
|-----------|-------------|
| Large table migration (>1M rows) | Plan batched approach, estimate time |
| Irreversible change needed | Require explicit user approval |
| Production schema drift | `database-architect` agent |
| Performance impact unknown | Test on production-sized copy first |

## Failure Behavior

- **Migration fails mid-way:** Roll back, report which step failed
- **Rollback fails:** Report state, suggest manual recovery steps
- **Lock timeout:** Retry with shorter transaction, consider off-peak
- **Data validation fails:** Stop migration, report invalid records

## Red Flags

- Migration without rollback plan
- DROP without verifying unused
- ALTER TABLE during peak hours
- Single migration for column rename
