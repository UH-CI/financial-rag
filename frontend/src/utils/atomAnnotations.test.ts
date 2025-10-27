import { describe, it, expect } from 'vitest';
import { parseToAtoms, segmentsForAtom, isRefAtomAnnotated } from './atomAnnotations';
import type { AnnotationItem } from '../types';

describe('atomAnnotations utilities - Ramseyer Format', () => {
  describe('parseToAtoms', () => {
    it('should parse text without citations', () => {
      const text = 'This is plain text without citations.';
      const atoms = parseToAtoms(text);
      
      expect(atoms).toHaveLength(1);
      expect(atoms[0]).toEqual({
        type: 'text',
        text: 'This is plain text without citations.'
      });
    });

    it('should parse text with single citation', () => {
      const text = 'This bill [1] proposes changes.';
      const atoms = parseToAtoms(text);
      
      expect(atoms).toHaveLength(3);
      expect(atoms[0]).toEqual({ type: 'text', text: 'This bill ' });
      expect(atoms[1]).toEqual({ type: 'ref', refId: '1', display: '[1]' });
      expect(atoms[2]).toEqual({ type: 'text', text: ' proposes changes.' });
    });

    it('should parse text with multiple citations', () => {
      const text = 'See [1] and [2] for details.';
      const atoms = parseToAtoms(text);
      
      expect(atoms).toHaveLength(5);
      expect(atoms[1]).toEqual({ type: 'ref', refId: '1', display: '[1]' });
      expect(atoms[3]).toEqual({ type: 'ref', refId: '2', display: '[2]' });
    });

    it('should parse chunk citations', () => {
      const text = 'Reference [5.3] shows data.';
      const atoms = parseToAtoms(text);
      
      expect(atoms).toHaveLength(3);
      expect(atoms[1]).toEqual({ type: 'ref', refId: '5.3', display: '[5.3]' });
    });

    it('should parse complex citations', () => {
      const text = 'See [CHUNK 1, NUMBER 5] for more.';
      const atoms = parseToAtoms(text);
      
      expect(atoms).toHaveLength(3);
      expect(atoms[1]).toEqual({ 
        type: 'ref', 
        refId: 'CHUNK 1, NUMBER 5', 
        display: '[CHUNK 1, NUMBER 5]' 
      });
    });

    it('should handle empty text', () => {
      expect(parseToAtoms('')).toEqual([]);
      expect(parseToAtoms(null as any)).toEqual([]);
      expect(parseToAtoms(undefined as any)).toEqual([]);
    });
  });

  describe('segmentsForAtom - Strikethrough (Deleted Material)', () => {
    it('should return single segment for unannotated text', () => {
      const segments = segmentsForAtom(0, 10, []);
      
      expect(segments).toHaveLength(1);
      expect(segments[0]).toEqual({ start: 0, end: 10, type: null });
    });

    it('should return strikethrough segment for deleted material', () => {
      const annotations: AnnotationItem[] = [{
        id: '1',
        type: 'strikethrough',
        sectionKey: 'overview',
        textContent: 'deleted',
        timestamp: '2024-01-01',
        startAtom: 0,
        startOffset: 0,
        endAtom: 0,
        endOffset: 10
      }];
      
      const segments = segmentsForAtom(0, 10, annotations);
      
      expect(segments).toHaveLength(1);
      expect(segments[0]).toEqual({ start: 0, end: 10, type: 'strikethrough' });
    });

    it('should return multiple segments for partially struck text', () => {
      const annotations: AnnotationItem[] = [{
        id: '1',
        type: 'strikethrough',
        sectionKey: 'overview',
        textContent: 'test',
        timestamp: '2024-01-01',
        startAtom: 0,
        startOffset: 3,
        endAtom: 0,
        endOffset: 7
      }];
      
      const segments = segmentsForAtom(0, 10, annotations);
      
      expect(segments).toHaveLength(3);
      expect(segments[0]).toEqual({ start: 0, end: 3, type: null });
      expect(segments[1]).toEqual({ start: 3, end: 7, type: 'strikethrough' });
      expect(segments[2]).toEqual({ start: 7, end: 10, type: null });
    });

    it('should merge overlapping strikethroughs', () => {
      const annotations: AnnotationItem[] = [
        {
          id: '1',
          type: 'strikethrough',
          sectionKey: 'overview',
          textContent: 'test',
          timestamp: '2024-01-01',
          startAtom: 0,
          startOffset: 2,
          endAtom: 0,
          endOffset: 6
        },
        {
          id: '2',
          type: 'strikethrough',
          sectionKey: 'overview',
          textContent: 'test',
          timestamp: '2024-01-01',
          startAtom: 0,
          startOffset: 4,
          endAtom: 0,
          endOffset: 8
        }
      ];
      
      const segments = segmentsForAtom(0, 10, annotations);
      
      expect(segments).toHaveLength(3);
      expect(segments[0]).toEqual({ start: 0, end: 2, type: null });
      expect(segments[1]).toEqual({ start: 2, end: 8, type: 'strikethrough' });
      expect(segments[2]).toEqual({ start: 8, end: 10, type: null });
    });
  });

  describe('segmentsForAtom - Underline (New Material)', () => {
    it('should return underline segment for new material', () => {
      const annotations: AnnotationItem[] = [{
        id: '1',
        type: 'underline',
        sectionKey: 'overview',
        textContent: 'new text',
        timestamp: '2024-01-01',
        startAtom: 0,
        startOffset: 0,
        endAtom: 0,
        endOffset: 10
      }];
      
      const segments = segmentsForAtom(0, 10, annotations);
      
      expect(segments).toHaveLength(1);
      expect(segments[0]).toEqual({ start: 0, end: 10, type: 'underline' });
    });

    it('should return multiple segments for partially underlined text', () => {
      const annotations: AnnotationItem[] = [{
        id: '1',
        type: 'underline',
        sectionKey: 'overview',
        textContent: 'new',
        timestamp: '2024-01-01',
        startAtom: 0,
        startOffset: 3,
        endAtom: 0,
        endOffset: 7
      }];
      
      const segments = segmentsForAtom(0, 10, annotations);
      
      expect(segments).toHaveLength(3);
      expect(segments[0]).toEqual({ start: 0, end: 3, type: null });
      expect(segments[1]).toEqual({ start: 3, end: 7, type: 'underline' });
      expect(segments[2]).toEqual({ start: 7, end: 10, type: null });
    });

    it('should merge overlapping underlines', () => {
      const annotations: AnnotationItem[] = [
        {
          id: '1',
          type: 'underline',
          sectionKey: 'overview',
          textContent: 'new',
          timestamp: '2024-01-01',
          startAtom: 0,
          startOffset: 2,
          endAtom: 0,
          endOffset: 6
        },
        {
          id: '2',
          type: 'underline',
          sectionKey: 'overview',
          textContent: 'text',
          timestamp: '2024-01-01',
          startAtom: 0,
          startOffset: 4,
          endAtom: 0,
          endOffset: 8
        }
      ];
      
      const segments = segmentsForAtom(0, 10, annotations);
      
      expect(segments).toHaveLength(3);
      expect(segments[0]).toEqual({ start: 0, end: 2, type: null });
      expect(segments[1]).toEqual({ start: 2, end: 8, type: 'underline' });
      expect(segments[2]).toEqual({ start: 8, end: 10, type: null });
    });
  });

  describe('segmentsForAtom - Mixed Annotations', () => {
    it('should handle adjacent strikethrough and underline', () => {
      const annotations: AnnotationItem[] = [
        {
          id: '1',
          type: 'strikethrough',
          sectionKey: 'overview',
          textContent: 'old',
          timestamp: '2024-01-01',
          startAtom: 0,
          startOffset: 0,
          endAtom: 0,
          endOffset: 5
        },
        {
          id: '2',
          type: 'underline',
          sectionKey: 'overview',
          textContent: 'new',
          timestamp: '2024-01-01',
          startAtom: 0,
          startOffset: 5,
          endAtom: 0,
          endOffset: 10
        }
      ];
      
      const segments = segmentsForAtom(0, 10, annotations);
      
      expect(segments).toHaveLength(2);
      expect(segments[0]).toEqual({ start: 0, end: 5, type: 'strikethrough' });
      expect(segments[1]).toEqual({ start: 5, end: 10, type: 'underline' });
    });

    it('should handle interleaved annotations', () => {
      const annotations: AnnotationItem[] = [
        {
          id: '1',
          type: 'strikethrough',
          sectionKey: 'overview',
          textContent: 'old',
          timestamp: '2024-01-01',
          startAtom: 0,
          startOffset: 0,
          endAtom: 0,
          endOffset: 3
        },
        {
          id: '2',
          type: 'underline',
          sectionKey: 'overview',
          textContent: 'new',
          timestamp: '2024-01-01',
          startAtom: 0,
          startOffset: 3,
          endAtom: 0,
          endOffset: 6
        },
        {
          id: '3',
          type: 'strikethrough',
          sectionKey: 'overview',
          textContent: 'old2',
          timestamp: '2024-01-01',
          startAtom: 0,
          startOffset: 6,
          endAtom: 0,
          endOffset: 10
        }
      ];
      
      const segments = segmentsForAtom(0, 10, annotations);
      
      expect(segments).toHaveLength(3);
      expect(segments[0]).toEqual({ start: 0, end: 3, type: 'strikethrough' });
      expect(segments[1]).toEqual({ start: 3, end: 6, type: 'underline' });
      expect(segments[2]).toEqual({ start: 6, end: 10, type: 'strikethrough' });
    });

    it('should prioritize strikethrough when overlapping with underline', () => {
      // In Ramseyer format, if text is both deleted and new (edge case),
      // strikethrough takes precedence
      const annotations: AnnotationItem[] = [
        {
          id: '1',
          type: 'strikethrough',
          sectionKey: 'overview',
          textContent: 'text',
          timestamp: '2024-01-01',
          startAtom: 0,
          startOffset: 2,
          endAtom: 0,
          endOffset: 8
        },
        {
          id: '2',
          type: 'underline',
          sectionKey: 'overview',
          textContent: 'text',
          timestamp: '2024-01-01',
          startAtom: 0,
          startOffset: 4,
          endAtom: 0,
          endOffset: 6
        }
      ];
      
      const segments = segmentsForAtom(0, 10, annotations);
      
      // Should merge and prioritize strikethrough
      expect(segments).toHaveLength(3);
      expect(segments[0]).toEqual({ start: 0, end: 2, type: null });
      expect(segments[1]).toEqual({ start: 2, end: 8, type: 'strikethrough' });
      expect(segments[2]).toEqual({ start: 8, end: 10, type: null });
    });
  });

  describe('isRefAtomAnnotated', () => {
    it('should return null for unannotated ref atom', () => {
      expect(isRefAtomAnnotated(1, [])).toBe(null);
    });

    it('should return "strikethrough" for struck ref atom', () => {
      const annotations: AnnotationItem[] = [{
        id: '1',
        type: 'strikethrough',
        sectionKey: 'overview',
        textContent: '[1]',
        timestamp: '2024-01-01',
        startAtom: 1,
        startOffset: 0,
        endAtom: 1,
        endOffset: 0
      }];
      
      expect(isRefAtomAnnotated(1, annotations)).toBe('strikethrough');
    });

    it('should return "underline" for underlined ref atom', () => {
      const annotations: AnnotationItem[] = [{
        id: '1',
        type: 'underline',
        sectionKey: 'overview',
        textContent: '[1]',
        timestamp: '2024-01-01',
        startAtom: 1,
        startOffset: 0,
        endAtom: 1,
        endOffset: 0
      }];
      
      expect(isRefAtomAnnotated(1, annotations)).toBe('underline');
    });

    it('should return "strikethrough" for ref atom within struck range', () => {
      const annotations: AnnotationItem[] = [{
        id: '1',
        type: 'strikethrough',
        sectionKey: 'overview',
        textContent: 'text [1] more',
        timestamp: '2024-01-01',
        startAtom: 0,
        startOffset: 5,
        endAtom: 2,
        endOffset: 3
      }];
      
      expect(isRefAtomAnnotated(1, annotations)).toBe('strikethrough');
    });

    it('should prioritize strikethrough when ref has both annotations', () => {
      const annotations: AnnotationItem[] = [
        {
          id: '1',
          type: 'strikethrough',
          sectionKey: 'overview',
          textContent: '[1]',
          timestamp: '2024-01-01',
          startAtom: 1,
          startOffset: 0,
          endAtom: 1,
          endOffset: 0
        },
        {
          id: '2',
          type: 'underline',
          sectionKey: 'overview',
          textContent: '[1]',
          timestamp: '2024-01-01',
          startAtom: 1,
          startOffset: 0,
          endAtom: 1,
          endOffset: 0
        }
      ];
      
      expect(isRefAtomAnnotated(1, annotations)).toBe('strikethrough');
    });
  });

  describe('Backward Compatibility', () => {
    it('should handle legacy strikethrough items without type field', () => {
      // Legacy items should be treated as strikethrough
      const legacyAnnotations: any[] = [{
        id: '1',
        // No type field - should default to strikethrough
        sectionKey: 'overview',
        textContent: 'test',
        timestamp: '2024-01-01',
        startAtom: 0,
        startOffset: 0,
        endAtom: 0,
        endOffset: 10
      }];
      
      const segments = segmentsForAtom(0, 10, legacyAnnotations);
      
      expect(segments).toHaveLength(1);
      expect(segments[0]).toEqual({ start: 0, end: 10, type: 'strikethrough' });
    });
  });
});
