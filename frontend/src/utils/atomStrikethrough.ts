import type { Atom, StrikethroughItem } from '../types';

/**
 * Parse text into atoms (text chunks and citation references)
 * This creates a stable, deterministic representation
 */
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

/**
 * Segment: a contiguous piece of a text atom with strike status
 */
interface Segment {
  start: number;
  end: number;
  struck: boolean;
}

/**
 * Compute segments for a text atom based on annotations
 */
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

/**
 * Check if a ref atom is fully struck
 */
export function isRefAtomFullyStruck(
  atomIndex: number,
  annotations: StrikethroughItem[]
): boolean {
  return annotations.some(ann =>
    ann.startAtom <= atomIndex && ann.endAtom >= atomIndex
  );
}

/**
 * Map DOM selection to atom coordinates
 */
export function selectionToAtomRange(): {
  startAtom: number;
  startOffset: number;
  endAtom: number;
  endOffset: number;
} | null {
  const sel = window.getSelection();
  if (!sel || sel.rangeCount === 0 || sel.isCollapsed) {
    console.log('❌ No valid selection');
    return null;
  }

  const range = sel.getRangeAt(0);
  console.log('📍 Selection range:', {
    startContainer: range.startContainer,
    startOffset: range.startOffset,
    endContainer: range.endContainer,
    endOffset: range.endOffset
  });
  
  const start = getAtomPositionFromNode(range.startContainer, range.startOffset);
  const end = getAtomPositionFromNode(range.endContainer, range.endOffset);

  if (!start) {
    console.log('❌ Could not find start atom position');
    return null;
  }
  
  if (!end) {
    console.log('❌ Could not find end atom position');
    return null;
  }

  // Normalize ordering
  if (start.atomIndex > end.atomIndex || 
      (start.atomIndex === end.atomIndex && start.offsetInAtom > end.offsetInAtom)) {
    console.log('✅ Atom range (reversed):', {
      startAtom: end.atomIndex,
      startOffset: end.offsetInAtom,
      endAtom: start.atomIndex,
      endOffset: start.offsetInAtom
    });
    return {
      startAtom: end.atomIndex,
      startOffset: end.offsetInAtom,
      endAtom: start.atomIndex,
      endOffset: start.offsetInAtom
    };
  }

  console.log('✅ Atom range:', {
    startAtom: start.atomIndex,
    startOffset: start.offsetInAtom,
    endAtom: end.atomIndex,
    endOffset: end.offsetInAtom
  });
  
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
  console.log('getAtomPositionFromNode:', { node, offset });
  
  // Find nearest ancestor with data-atom-index
  let current: Node | null = node;
  let depth = 0;
  
  while (current && current !== document.body && depth < 20) {
    console.log(`  Level ${depth}:`, current.nodeName, current instanceof HTMLElement ? (current as HTMLElement).className : 'not element');
    
    if (current instanceof HTMLElement && current.hasAttribute('data-atom-index')) {
      const atomIndex = parseInt(current.getAttribute('data-atom-index') || '0');
      console.log(`  ✅ Found atom index: ${atomIndex}`);
      
      // Check if it's a ref atom
      if (current.hasAttribute('data-ref')) {
        console.log(`  → Ref atom, offset: ${offset > 0 ? 1 : 0}`);
        return { atomIndex, offsetInAtom: offset > 0 ? 1 : 0 };
      }
      
      // Text atom - get char offset
      const charStart = parseInt(current.getAttribute('data-char-start') || '0');
      console.log(`  → Text atom, charStart: ${charStart}, final offset: ${charStart + offset}`);
      return { atomIndex, offsetInAtom: charStart + offset };
    }
    current = current.parentElement;
    depth++;
  }

  console.log('  ❌ No atom index found');
  return null;
}
