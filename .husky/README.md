# Git Hooks

This directory contains Git hooks managed by [Husky](https://typicode.github.io/husky/).

## Available Hooks

### pre-push
Runs before pushing to the `main` branch:
- ✅ Builds the frontend (`npm run build`)
- ✅ Runs all tests (`npm run test:run`)

If either check fails, the push is aborted.

## Setup

Hooks are automatically installed when you run:
```bash
npm install
```

## Bypassing Hooks (Emergency Only)

If you need to bypass the pre-push hook in an emergency:
```bash
git push --no-verify
```

⚠️ **Warning:** Only use `--no-verify` when absolutely necessary, as it skips all quality checks.

## Testing Hooks Locally

You can test the pre-push hook without actually pushing:
```bash
.husky/pre-push
```

## Disabling Hooks

To temporarily disable hooks:
```bash
# Uninstall hooks
npx husky uninstall

# Reinstall when ready
npx husky install
```
