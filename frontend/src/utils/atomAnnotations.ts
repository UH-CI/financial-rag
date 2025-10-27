import type { Atom, AnnotationItem, AnnotationType } from '../types';

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
 * Segment: a contiguous piece of a text atom with annotation type
 */
export interface Segment {
  start: number;
  end: number;
  type: AnnotationType | null; // null = no annotation, 'strikethrough' or 'underline'
}

/**
 * Compute segments for a text atom based on annotations
 * Supports both strikethrough and underline annotations
 * When annotations overlap, strikethrough takes precedence
 */
export function segmentsForAtom(
  atomIndex: number,
  textLength: number,
  annotations: AnnotationItem[]
): Segment[] {
  // Find all annotations that affect this atom
  const relevant = annotations.filter(ann => 
    ann.startAtom <= atomIndex && ann.endAtom >= atomIndex
  );

  if (relevant.length === 0) {
    return [{ start: 0, end: textLength, type: null }];
  }

  // Build list of annotated ranges within this atom, grouped by type
  const strikethroughRanges: Array<{ start: number; end: number }> = [];
  const underlineRanges: Array<{ start: number; end: number }> = [];
  
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
      // Default to strikethrough for backward compatibility (legacy items without type)
      const annotationType = ann.type || 'strikethrough';
      
      if (annotationType === 'strikethrough') {
        strikethroughRanges.push({ start: rangeStart, end: rangeEnd });
      } else if (annotationType === 'underline') {
        underlineRanges.push({ start: rangeStart, end: rangeEnd });
      }
    }
  }

  // Merge overlapping ranges for each type
  const mergedStrikethrough = mergeRanges(strikethroughRanges);
  const mergedUnderline = mergeRanges(underlineRanges);

  // Build segments, prioritizing strikethrough over underline
  const segments: Segment[] = [];
  let pos = 0;

  // Combine all ranges with their types
  const allRanges: Array<{ start: number; end: number; type: AnnotationType }> = [
    ...mergedStrikethrough.map(r => ({ ...r, type: 'strikethrough' as AnnotationType })),
    ...mergedUnderline.map(r => ({ ...r, type: 'underline' as AnnotationType }))
  ];

  // Sort by start position
  allRanges.sort((a, b) => a.start - b.start);

  // Process ranges, handling overlaps (strikethrough takes precedence)
  for (const range of allRanges) {
    // Add unannotated segment before this range
    if (pos < range.start) {
      segments.push({ start: pos, end: range.start, type: null });
    }

    // Check if this range overlaps with existing strikethrough
    const lastSegment = segments[segments.length - 1];
    if (lastSegment && lastSegment.type === 'strikethrough' && lastSegment.end > range.start) {
      // Overlap with strikethrough - extend strikethrough if needed
      if (range.type === 'strikethrough' && range.end > lastSegment.end) {
        lastSegment.end = range.end;
        pos = range.end;
      } else {
        // Underline overlaps with strikethrough - strikethrough wins, skip this range
        pos = Math.max(pos, lastSegment.end);
      }
    } else {
      // No overlap or overlap with underline
      if (lastSegment && lastSegment.end > range.start) {
        // Overlaps with underline
        if (range.type === 'strikethrough') {
          // Strikethrough wins - truncate underline and add strikethrough
          lastSegment.end = range.start;
          segments.push({ start: range.start, end: range.end, type: 'strikethrough' });
          pos = range.end;
        } else {
          // Both underline - extend
          lastSegment.end = Math.max(lastSegment.end, range.end);
          pos = lastSegment.end;
        }
      } else {
        // No overlap - add new segment
        segments.push({ start: range.start, end: range.end, type: range.type });
        pos = range.end;
      }
    }
  }

  // Add remaining unannotated segment
  if (pos < textLength) {
    segments.push({ start: pos, end: textLength, type: null });
  }

  return segments;
}

/**
 * Merge overlapping ranges
 */
function mergeRanges(ranges: Array<{ start: number; end: number }>): Array<{ start: number; end: number }> {
  if (ranges.length === 0) return [];
  
  ranges.sort((a, b) => a.start - b.start);
  const merged: typeof ranges = [];
  
  for (const range of ranges) {
    if (merged.length === 0 || merged[merged.length - 1].end < range.start) {
      merged.push({ ...range });
    } else {
      merged[merged.length - 1].end = Math.max(merged[merged.length - 1].end, range.end);
    }
  }
  
  return merged;
}

/**
 * Check if a ref atom has any annotation and return the type
 * If multiple annotations, strikethrough takes precedence
 */
export function isRefAtomAnnotated(
  atomIndex: number,
  annotations: AnnotationItem[]
): AnnotationType | null {
  const relevantAnnotations = annotations.filter(ann =>
    ann.startAtom <= atomIndex && ann.endAtom >= atomIndex
  );

  if (relevantAnnotations.length === 0) {
    return null;
  }

  // Check for strikethrough first (priority)
  const hasStrikethrough = relevantAnnotations.some(ann => 
    (ann.type || 'strikethrough') === 'strikethrough'
  );
  
  if (hasStrikethrough) {
    return 'strikethrough';
  }

  // Otherwise return underline if present
  const hasUnderline = relevantAnnotations.some(ann => ann.type === 'underline');
  return hasUnderline ? 'underline' : null;
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
