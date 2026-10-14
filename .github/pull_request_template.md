## What and why

<!-- Link the issue: Closes #... -->

## How it was tested

- [ ] `pnpm typecheck && pnpm test`
- [ ] `uv run --group dev pytest` (services touched)
- [ ] Migrations applied to a fresh database (db changes)

## Checklist

- [ ] No sport-specific logic added to `packages/core`
- [ ] Imported data carries provenance; missing values stay missing (not zero)
- [ ] No licensed data, video or secrets committed
