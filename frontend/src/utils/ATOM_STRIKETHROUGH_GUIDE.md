# Atom-Based Strikethrough: Complete Technical Guide

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [The Atom System](#the-atom-system)
3. [Implementation Details](#implementation-details)
4. [Data Flow](#data-flow)
5. [Code Walkthrough](#code-walkthrough)
6. [Edge Cases](#edge-cases)

---

## Architecture Overview

### The Problem We Solved

**Challenge**: Apply strikethrough to user-selected text in a React application where:
- Text contains citations rendered as React components (`[1.12]`)
- Users can select across text and citations
- Multiple strikethroughs can overlap
- Changes must persist and support undo/redo
- No React reconciliation errors

**Failed Approaches**:
1. **`document.execCommand('strikeThrough')`** - Conflicts with React's virtual DOM
2. **Text matching** - Fails with duplicates and citations
3. **Character positions** - Misalign when citations become components
4. **DOM paths** - Break on React re-renders

**Solution**: **Atom-Based Architecture**

---

## The Atom System

### What is an Atom?

An **atom** is the smallest indivisible unit of content. Think of it as a building block.

```typescript
type Atom =
  | { type: 'text'; text: string }           // Plain text
  | { type: 'ref'; refId: string; display: string }; // Citation
```

### Example Transformation

**Input (raw text)**:
```
"The purpose [1.12] is to establish [2.5] funding."
```

**Output (atom array)**:
```javascript
[
  { type: 'text', text: 'The purpose ' },           // Atom 0
  { type: 'ref', refId: '1.12', display: '[1.12]' }, // Atom 1
  { type: 'text', text: ' is to establish ' },      // Atom 2
  { type: 'ref', refId: '2.5', display: '[2.5]' },   // Atom 3
  { type: 'text', text: ' funding.' }                // Atom 4
]
```

### Why Atoms?

| Problem | Atom Solution |
|---------|---------------|
| Text has duplicates | Atoms have unique indices (0, 1, 2...) |
| Citations are components | Citations are separate atoms |
| DOM changes on render | Atom indices stay constant |
| Hard to match selections | Each rendered atom has `data-atom-index` |

---

## Implementation Details

### Step 1: Parse Text into Atoms

**File**: `src/utils/atomStrikethrough.ts`

```typescript
export function parseToAtoms(text: string): Atom[] {
  if (!text || typeof text !== 'string') {
    return [];
  }

  const atoms: Atom[] = [];
  const citationRegex = /\[([^\]]+)\]/g;
  let lastIndex = 0;
  let match;

  while ((match = citationRegex.exec(text)) !== null) {
    // Add text before citation
    if (match.index > lastIndex) {
      const textBefore = text.substring(lastIndex, match.index);
      atoms.push({ type: 'text', text: textBefore });
    }

    // Add citation as ref atom
    const citationContent = match[1].trim();
    atoms.push({
      type: 'ref',
      refId: citationContent,
      display: `[${citationContent}]`
    });

    lastIndex = match.index + match[0].length;
  }

  // Add remaining text
  if (lastIndex < text.length) {
    atoms.push({ type: 'text', text: text.substring(lastIndex) });
  }

  return atoms;
}
```

**How it works**:
1. Use regex to find all `[...]` patterns
2. Split text into segments between citations
3. Create text atoms for segments
4. Create ref atoms for citations
5. Return ordered array

### Step 2: Render Atoms with Metadata

**File**: `src/components/FiscalNoteContent.tsx`

```typescript
const renderAtomsForSection = (sectionKey: string): React.ReactNode => {
  const atoms = sectionAtoms[sectionKey];
  if (!atoms || atoms.length === 0) return null;

  const sectionStrikethroughs = strikethroughs.filter(st => st.sectionKey === sectionKey);

  return atoms.map((atom, atomIndex) => {
    if (atom.type === 'text') {
      // Get segments for this text atom
      const segments = segmentsForAtom(atomIndex, atom.text.length, sectionStrikethroughs);
      
      return segments.map((seg, segIndex) => (
        <span
          key={`${atomIndex}-${segIndex}`}
          data-atom-index={atomIndex}
          data-char-start={seg.start}
          data-char-end={seg.end}
          className={seg.struck ? 'line-through text-gray-500 italic' : undefined}
        >
          {atom.text.slice(seg.start, seg.end)}
        </span>
      ));
    } else {
      // Ref atom - render citation component
      const isStruck = isRefAtomFullyStruck(atomIndex, sectionStrikethroughs);
      
      return (
        <span
          key={atomIndex}
          data-atom-index={atomIndex}
          data-ref="true"
          className={isStruck ? 'line-through text-gray-500 italic' : 'inline-flex items-center'}
        >
          <span className="text-blue-600">[</span>
          <DocumentReferenceComponent ... />
          <span className="text-blue-600">]</span>
        </span>
      );
    }
  });
};
```

**Key points**:
- Every atom gets `data-atom-index={atomIndex}` attribute
- Text atoms get `data-char-start` and `data-char-end` for partial selections
- Ref atoms get `data-ref="true"` to identify them
- Strikethroughs are applied via `className`, not DOM manipulation

### Step 3: Map DOM Selection to Atom Coordinates

**File**: `src/utils/atomStrikethrough.ts`

```typescript
export function selectionToAtomRange(): {
  startAtom: number;
  startOffset: number;
  endAtom: number;
  endOffset: number;
} | null {
  const sel = window.getSelection();
  if (!sel || sel.rangeCount === 0 || sel.isCollapsed) {
    return null;
  }

  const range = sel.getRangeAt(0);
  
  const start = getAtomPositionFromNode(range.startContainer, range.startOffset);
  const end = getAtomPositionFromNode(range.endContainer, range.endOffset);

  if (!start || !end) return null;

  // Normalize ordering (handle backwards selections)
  if (start.atomIndex > end.atomIndex || 
      (start.atomIndex === end.atomIndex && start.offsetInAtom > end.offsetInAtom)) {
    return {
      startAtom: end.atomIndex,
      startOffset: end.offsetInAtom,
      endAtom: start.atomIndex,
      endOffset: start.offsetInAtom
    };
  }

  return {
    startAtom: start.atomIndex,
    startOffset: start.offsetInAtom,
    endAtom: end.atomIndex,
    endOffset: end.offsetInAtom
  };
}

function getAtomPositionFromNode(
  node: Node,
  offset: number
): { atomIndex: number; offsetInAtom: number } | null {
  // Find nearest ancestor with data-atom-index
  let current: Node | null = node;
  
  while (current && current !== document.body) {
    if (current instanceof HTMLElement && current.hasAttribute('data-atom-index')) {
      const atomIndex = parseInt(current.getAttribute('data-atom-index') || '0');
      
      // Check if it's a ref atom
      if (current.hasAttribute('data-ref')) {
        return { atomIndex, offsetInAtom: offset > 0 ? 1 : 0 };
      }
      
      // Text atom - get char offset
      const charStart = parseInt(current.getAttribute('data-char-start') || '0');
      return { atomIndex, offsetInAtom: charStart + offset };
    }
    current = current.parentElement;
  }

  return null;
}
```

**How it works**:
1. Get browser's `Selection` object
2. Walk up DOM tree from selection nodes
3. Find nearest element with `data-atom-index`
4. Read atom index and character offset
5. Return atom coordinates

### Step 4: Apply Strikethrough on Selection

**File**: `src/components/FiscalNoteContent.tsx`

```typescript
useEffect(() => {
  if (!isStrikeoutMode || !contentRef.current) return;

  const handleMouseUp = () => {
    const selection = window.getSelection();
    if (!selection || selection.isCollapsed) return;

    const selectedText = selection.toString().trim();
    if (!selectedText) return;

    // Map selection to atom range IMMEDIATELY (before it's lost)
    const atomRange = selectionToAtomRange();
    if (!atomRange) {
      console.warn('Could not map selection to atoms');
      return;
    }

    // Find section key
    const sectionKey = findSectionKeyFromSelection(selection);
    if (!sectionKey) {
      console.warn('Could not find section key');
      return;
    }

    // Create strikethrough item with atom coordinates
    const item: StrikethroughItem = {
      id: `st-${Date.now()}-${Math.random()}`,
      sectionKey,
      textContent: selectedText,
      timestamp: new Date().toISOString(),
      startAtom: atomRange.startAtom,
      startOffset: atomRange.startOffset,
      endAtom: atomRange.endAtom,
      endOffset: atomRange.endOffset
    };

    const newStrikethroughs = [...strikethroughs, item];
    addToHistory(newStrikethroughs);
    setHasUnsavedChanges(true);

    // Clear selection
    selection.removeAllRanges();
  };

  const contentElement = contentRef.current;
  contentElement.addEventListener('mouseup', handleMouseUp);
  
  return () => {
    contentElement.removeEventListener('mouseup', handleMouseUp);
  };
}, [isStrikeoutMode, strikethroughs, addToHistory]);
```

**Key points**:
- Capture selection **immediately** on `mouseup`
- Map to atoms **before** selection is lost
- Store atom coordinates in state
- React re-renders with strikethroughs applied

### Step 5: Compute Segments for Rendering

**File**: `src/utils/atomStrikethrough.ts`

```typescript
export function segmentsForAtom(
  atomIndex: number,
  textLength: number,
  annotations: StrikethroughItem[]
): Segment[] {
  // Find all annotations that affect this atom
  const relevant = annotations.filter(ann => 
    ann.startAtom <= atomIndex && ann.endAtom >= atomIndex
  );

  if (relevant.length === 0) {
    return [{ start: 0, end: textLength, struck: false }];
  }

  // Build list of struck ranges within this atom
  const struckRanges: Array<{ start: number; end: number }> = [];
  
  for (const ann of relevant) {
    let rangeStart = 0;
    let rangeEnd = textLength;

    if (ann.startAtom === atomIndex) {
      rangeStart = ann.startOffset;
    }
    if (ann.endAtom === atomIndex) {
      rangeEnd = ann.endOffset;
    }

    if (rangeStart < rangeEnd) {
      struckRanges.push({ start: rangeStart, end: rangeEnd });
    }
  }

  // Merge overlapping ranges
  struckRanges.sort((a, b) => a.start - b.start);
  const merged: typeof struckRanges = [];
  for (const range of struckRanges) {
    if (merged.length === 0 || merged[merged.length - 1].end < range.start) {
      merged.push(range);
    } else {
      merged[merged.length - 1].end = Math.max(merged[merged.length - 1].end, range.end);
    }
  }

  // Build segments
  const segments: Segment[] = [];
  let pos = 0;

  for (const range of merged) {
    if (pos < range.start) {
      segments.push({ start: pos, end: range.start, struck: false });
    }
    segments.push({ start: range.start, end: range.end, struck: true });
    pos = range.end;
  }

  if (pos < textLength) {
    segments.push({ start: pos, end: textLength, struck: false });
  }

  return segments;
}
```

**How it works**:
1. Find all strikethroughs affecting this atom
2. Calculate struck ranges within the atom
3. Merge overlapping ranges
4. Split atom text into struck/non-struck segments
5. Return segments for rendering

---

## Data Flow

### Complete Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Parse: Raw Text → Atoms                                  │
│    "The [1] is" → [text, ref, text]                        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. Render: Atoms → DOM with metadata                        │
│    <span data-atom-index="0">The </span>                   │
│    <span data-atom-index="1" data-ref="true">[1]</span>    │
│    <span data-atom-index="2"> is</span>                    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. User Selects: Browser selection                          │
│    User highlights "The [1]"                                │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. Map: DOM Selection → Atom Coordinates                    │
│    startAtom: 0, startOffset: 0                            │
│    endAtom: 1, endOffset: 1                                │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. Store: Save to State                                     │
│    strikethroughs.push({                                    │
│      startAtom: 0, startOffset: 0,                         │
│      endAtom: 1, endOffset: 1                              │
│    })                                                       │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 6. React Re-renders                                         │
│    Calls renderAtomsForSection()                            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 7. Compute Segments: Which parts are struck?                │
│    Atom 0: [{ start: 0, end: 4, struck: true }]           │
│    Atom 1: [{ start: 0, end: 1, struck: true }]           │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 8. Render with Strikethroughs                               │
│    <span className="line-through">The </span>              │
│    <span className="line-through">[1]</span>               │
│    <span> is</span>                                        │
└─────────────────────────────────────────────────────────────┘
```

---

## Code Walkthrough

### File Structure

```
frontend/
├── src/
│   ├── types.ts                    # Atom and StrikethroughItem types
│   ├── utils/
│   │   └── atomStrikethrough.ts    # Atom parsing and mapping logic
│   └── components/
│       └── FiscalNoteContent.tsx   # Main component with rendering
```

### Key Functions

| Function | Location | Purpose |
|----------|----------|---------|
| `parseToAtoms()` | `utils/atomStrikethrough.ts` | Convert text to atom array |
| `selectionToAtomRange()` | `utils/atomStrikethrough.ts` | Map DOM selection to atoms |
| `segmentsForAtom()` | `utils/atomStrikethrough.ts` | Calculate struck segments |
| `isRefAtomFullyStruck()` | `utils/atomStrikethrough.ts` | Check if citation is struck |
| `renderAtomsForSection()` | `FiscalNoteContent.tsx` | Render atoms with strikethroughs |

---

## Edge Cases

### 1. Overlapping Strikethroughs

**Scenario**: User strikes through "The purpose" then strikes through "purpose is"

**Solution**: `segmentsForAtom()` merges overlapping ranges:
```javascript
// Input ranges: [0-11], [4-14]
// Merged: [0-14]
// Result: Single continuous strikethrough
```

### 2. Partial Text Atom Selection

**Scenario**: User selects "purp" from "The purpose"

**Solution**: Store character offsets within atom:
```javascript
{
  startAtom: 0,
  startOffset: 4,  // Start at 'p'
  endAtom: 0,
  endOffset: 8     // End after 'p'
}
```

### 3. Selection Across Citations

**Scenario**: User selects "purpose [1.12] is"

**Solution**: Span multiple atoms:
```javascript
{
  startAtom: 0,    // "The purpose "
  startOffset: 4,
  endAtom: 2,      // " is to"
  endOffset: 3
}
// Atoms 0 (partial), 1 (full), 2 (partial) all struck
```

### 4. Citation-Only Selection

**Scenario**: User selects just "[1.12]"

**Solution**: Ref atoms are atomic units:
```javascript
{
  startAtom: 1,
  startOffset: 0,  // Always 0 for refs
  endAtom: 1,
  endOffset: 1     // Always 1 for refs (full atom)
}
```

### 5. Same Text Multiple Times

**Scenario**: "The" appears 50 times

**Solution**: Atom indices are unique:
- First "The" is atom 0
- Second "The" is atom 5
- Third "The" is atom 12
- No ambiguity!

---

## Performance Considerations

### Optimizations

1. **Memoized Atom Parsing**:
   ```typescript
   const sectionAtoms = useMemo(() => {
     // Only re-parse when fiscalNote.data changes
   }, [fiscalNote.data]);
   ```

2. **Section-Scoped Rendering**:
   - Each section has its own atom array
   - Only re-render sections with changes

3. **Efficient Segment Calculation**:
   - O(n log n) for sorting ranges
   - O(n) for merging
   - Minimal re-computation

### Memory Usage

- **Atoms**: ~50-200 atoms per section
- **Strikethroughs**: ~10-50 per document
- **Total**: < 1MB for typical fiscal note

---

## Testing

### Unit Tests

```typescript
describe('parseToAtoms', () => {
  it('parses text with citations', () => {
    const atoms = parseToAtoms('The [1] is [2] good');
    expect(atoms).toEqual([
      { type: 'text', text: 'The ' },
      { type: 'ref', refId: '1', display: '[1]' },
      { type: 'text', text: ' is ' },
      { type: 'ref', refId: '2', display: '[2]' },
      { type: 'text', text: ' good' }
    ]);
  });
});

describe('segmentsForAtom', () => {
  it('merges overlapping strikethroughs', () => {
    const annotations = [
      { startAtom: 0, startOffset: 0, endAtom: 0, endOffset: 5 },
      { startAtom: 0, startOffset: 3, endAtom: 0, endOffset: 8 }
    ];
    const segments = segmentsForAtom(0, 10, annotations);
    expect(segments).toEqual([
      { start: 0, end: 8, struck: true },
      { start: 8, end: 10, struck: false }
    ]);
  });
});
```

### Integration Tests

1. Select text → Verify strikethrough appears
2. Undo → Verify strikethrough removed
3. Redo → Verify strikethrough reappears
4. Save → Verify persisted to backend
5. Reload → Verify loaded from backend

---

## Conclusion

The atom-based architecture solves the fundamental conflict between DOM selection and React rendering by:

1. **Creating a stable intermediate representation** (atoms)
2. **Mapping selections to atom coordinates** (not text or DOM)
3. **Rendering atoms with metadata** (data-atom-index)
4. **Applying strikethroughs via React** (no DOM manipulation)

**Result**: Clean, maintainable, error-free strikethrough feature that works seamlessly with React's reconciliation.
