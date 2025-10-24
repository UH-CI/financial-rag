# Testing Guide for Financial RAG Frontend

## Overview

This project uses **Vitest** and **React Testing Library** for comprehensive testing of UI components and utilities. The test suite ensures that strikethrough functionality, citation rendering, and user interactions work correctly.

## Setup

### Install Dependencies

```bash
npm install
```

This will install all testing dependencies including:
- `vitest` - Fast unit test framework
- `@testing-library/react` - React component testing utilities
- `@testing-library/user-event` - User interaction simulation
- `@testing-library/jest-dom` - Custom matchers for DOM assertions
- `jsdom` - DOM implementation for Node.js
- `@vitest/ui` - Visual test UI

## Running Tests

### Run All Tests (Watch Mode)
```bash
npm test
```

### Run Tests Once (CI Mode)
```bash
npm run test:run
```

### Run Tests with UI
```bash
npm run test:ui
```

### Run Tests with Coverage
```bash
npm run test:coverage
```

## Test Structure

### Test Files

```
frontend/
├── src/
│   ├── components/
│   │   └── FiscalNoteContent.test.tsx    # Component tests
│   ├── utils/
│   │   └── atomStrikethrough.test.ts     # Utility function tests
│   └── test/
│       ├── setup.ts                       # Test environment setup
│       └── mockData.ts                    # Mock data for tests
├── vitest.config.ts                       # Vitest configuration
└── TESTING.md                             # This file
```

## Test Coverage

### Atom Strikethrough Utilities (`atomStrikethrough.test.ts`)

Tests for core text parsing and strikethrough logic:

- ✅ **parseToAtoms**: Parse text into atoms (text chunks and citations)
  - Plain text without citations
  - Single and multiple citations
  - Chunk citations (e.g., `[5.3]`)
  - Complex citations (e.g., `[CHUNK 1, NUMBER 5]`)
  - Edge cases (empty text, null, undefined)

- ✅ **segmentsForAtom**: Calculate struck/unstruck segments
  - Unstruck text
  - Fully struck text
  - Partially struck text
  - Overlapping strikethroughs (merge logic)

- ✅ **isRefAtomFullyStruck**: Check if citation is struck through
  - Unstruck citations
  - Fully struck citations
  - Citations within struck ranges

- ✅ **selectionToAtomRange**: Convert user selection to atom coordinates
  - Simple selections
  - Selections across atoms
  - Invalid selections
  - Selections including citations

### FiscalNoteContent Component (`FiscalNoteContent.test.tsx`)

Tests for the main fiscal note component:

- ✅ **Rendering**
  - Fiscal note content display
  - Document citations
  - Financial citations (green brackets)
  - Chunk ID cycling for repeated citations

- ✅ **Strikethrough Mode**
  - Toggle strikethrough mode
  - Persist mode in localStorage
  - Active mode indicator

- ✅ **Strikethrough Operations**
  - Unsaved changes indicator
  - Undo/Redo button states
  - History management

- ✅ **Save and Discard**
  - Save API calls
  - localStorage clearing on discard
  - Backend synchronization

- ✅ **Clear All Strikethroughs**
  - Button visibility based on strikethrough count
  - Confirmation dialog
  - Backend update

- ✅ **Print Functionality**
  - Print button presence
  - window.print() invocation

- ✅ **Split View Controls**
  - Compare button (when enabled)
  - Close button (when in split view)
  - Callback invocations

- ✅ **LocalStorage Management**
  - Clear on new session
  - Preserve during component remounts
  - Session flag management

- ✅ **Citation Chunk Cycling**
  - Different chunks for repeated citations
  - Proper chunk ID display

## Writing New Tests

### Example: Testing a New Component

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import MyComponent from './MyComponent';

describe('MyComponent', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should render correctly', () => {
    render(<MyComponent />);
    expect(screen.getByText('Hello')).toBeInTheDocument();
  });

  it('should handle user interaction', async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    
    render(<MyComponent onClick={onClick} />);
    
    const button = screen.getByRole('button');
    await user.click(button);
    
    expect(onClick).toHaveBeenCalled();
  });
});
```

### Example: Testing a Utility Function

```typescript
import { describe, it, expect } from 'vitest';
import { myUtilFunction } from './myUtil';

describe('myUtilFunction', () => {
  it('should process input correctly', () => {
    const result = myUtilFunction('input');
    expect(result).toBe('expected output');
  });

  it('should handle edge cases', () => {
    expect(myUtilFunction('')).toBe('');
    expect(myUtilFunction(null)).toBe(null);
  });
});
```

## Best Practices

### 1. Test Behavior, Not Implementation
```typescript
// ❌ Bad - Testing implementation details
expect(component.state.count).toBe(5);

// ✅ Good - Testing user-visible behavior
expect(screen.getByText('Count: 5')).toBeInTheDocument();
```

### 2. Use User-Centric Queries
```typescript
// ❌ Bad
const button = container.querySelector('.submit-button');

// ✅ Good
const button = screen.getByRole('button', { name: /submit/i });
```

### 3. Clean Up After Tests
```typescript
beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  sessionStorage.clear();
});
```

### 4. Mock External Dependencies
```typescript
vi.mock('../services/api', () => ({
  saveStrikethroughs: vi.fn().mockResolvedValue({ success: true })
}));
```

### 5. Test Async Operations
```typescript
await waitFor(() => {
  expect(screen.getByText('Loaded')).toBeInTheDocument();
});
```

## Continuous Integration

### Add to Jenkins Pipeline

Add this stage to your `Jenkinsfile`:

```groovy
stage('Run Tests') {
    steps {
        script {
            echo "🧪 Running frontend tests..."
        }
        withCredentials([
            string(credentialsId: env.VM_HOST_CRED_ID, variable: 'VM_HOST')
        ]) {
            sshagent(credentials: [env.SSH_CRED_ID]) {
                sh """
                ssh -o StrictHostKeyChecking=no exouser@${VM_HOST} '
                    set -e
                    cd /home/exouser/RAG-system/frontend
                    npm run test:run
                    npm run test:coverage
                '
                """
            }
        }
    }
}
```

### GitHub Actions Example

```yaml
name: Test

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '18'
      - run: npm install
      - run: npm run test:run
      - run: npm run test:coverage
```

## Coverage Goals

Aim for:
- **80%+ line coverage** for critical components
- **100% coverage** for utility functions
- **All user interactions** tested
- **All edge cases** covered

## Debugging Tests

### Run Single Test File
```bash
npx vitest run src/components/FiscalNoteContent.test.tsx
```

### Run Tests Matching Pattern
```bash
npx vitest run -t "strikethrough"
```

### Debug in VS Code
Add to `.vscode/launch.json`:
```json
{
  "type": "node",
  "request": "launch",
  "name": "Debug Tests",
  "runtimeExecutable": "npm",
  "runtimeArgs": ["run", "test"],
  "console": "integratedTerminal"
}
```

## Common Issues

### Issue: Tests fail with "Cannot find module"
**Solution**: Run `npm install` to ensure all dependencies are installed.

### Issue: localStorage/sessionStorage errors
**Solution**: Mocks are set up in `src/test/setup.ts`. Ensure it's loaded.

### Issue: Async tests timing out
**Solution**: Increase timeout or use `waitFor()` properly:
```typescript
await waitFor(() => {
  expect(screen.getByText('Loaded')).toBeInTheDocument();
}, { timeout: 3000 });
```

## Resources

- [Vitest Documentation](https://vitest.dev/)
- [React Testing Library](https://testing-library.com/react)
- [Testing Library Best Practices](https://kentcdodds.com/blog/common-mistakes-with-react-testing-library)
- [User Event Documentation](https://testing-library.com/docs/user-event/intro)

## Maintenance

- **Update tests** when adding new features
- **Run tests before** committing changes
- **Review coverage reports** regularly
- **Refactor tests** to reduce duplication
- **Document complex test scenarios**

---

**Remember**: Good tests give you confidence to refactor and add features without breaking existing functionality! 🎯
