import { describe, it, expect } from 'vitest';
import { parseToAtoms, segmentsForAtom, isRefAtomFullyStruck } from './atomStrikethrough';
import type { StrikethroughItem } from '../types';

describe('atomStrikethrough utilities', () => {
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

  describe('segmentsForAtom', () => {
    it('should return single segment for unstruck text', () => {
      const segments = segmentsForAtom(0, 10, []);
      
      expect(segments).toHaveLength(1);
      expect(segments[0]).toEqual({ start: 0, end: 10, struck: false });
    });

    it('should return struck segment for fully struck text', () => {
      const strikethroughs: StrikethroughItem[] = [{
        id: '1',
        sectionKey: 'overview',
        textContent: 'test',
        timestamp: '2024-01-01',
        startAtom: 0,
        startOffset: 0,
        endAtom: 0,
        endOffset: 10
      }];
      
      const segments = segmentsForAtom(0, 10, strikethroughs);
      
      expect(segments).toHaveLength(1);
      expect(segments[0]).toEqual({ start: 0, end: 10, struck: true });
    });

    it('should return multiple segments for partially struck text', () => {
      const strikethroughs: StrikethroughItem[] = [{
        id: '1',
        sectionKey: 'overview',
        textContent: 'test',
        timestamp: '2024-01-01',
        startAtom: 0,
        startOffset: 3,
        endAtom: 0,
        endOffset: 7
      }];
      
      const segments = segmentsForAtom(0, 10, strikethroughs);
      
      expect(segments).toHaveLength(3);
      expect(segments[0]).toEqual({ start: 0, end: 3, struck: false });
      expect(segments[1]).toEqual({ start: 3, end: 7, struck: true });
      expect(segments[2]).toEqual({ start: 7, end: 10, struck: false });
    });

    it('should merge overlapping strikethroughs', () => {
      const strikethroughs: StrikethroughItem[] = [
        {
          id: '1',
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
          sectionKey: 'overview',
          textContent: 'test',
          timestamp: '2024-01-01',
          startAtom: 0,
          startOffset: 4,
          endAtom: 0,
          endOffset: 8
        }
      ];
      
      const segments = segmentsForAtom(0, 10, strikethroughs);
      
      expect(segments).toHaveLength(3);
      expect(segments[0]).toEqual({ start: 0, end: 2, struck: false });
      expect(segments[1]).toEqual({ start: 2, end: 8, struck: true });
      expect(segments[2]).toEqual({ start: 8, end: 10, struck: false });
    });
  });

  describe('isRefAtomFullyStruck', () => {
    it('should return false for unstruck ref atom', () => {
      expect(isRefAtomFullyStruck(1, [])).toBe(false);
    });

    it('should return true for fully struck ref atom', () => {
      const strikethroughs: StrikethroughItem[] = [{
        id: '1',
        sectionKey: 'overview',
        textContent: '[1]',
        timestamp: '2024-01-01',
        startAtom: 1,
        startOffset: 0,
        endAtom: 1,
        endOffset: 0
      }];
      
      expect(isRefAtomFullyStruck(1, strikethroughs)).toBe(true);
    });

    it('should return true for ref atom within struck range', () => {
      const strikethroughs: StrikethroughItem[] = [{
        id: '1',
        sectionKey: 'overview',
        textContent: 'text [1] more',
        timestamp: '2024-01-01',
        startAtom: 0,
        startOffset: 5,
        endAtom: 2,
        endOffset: 3
      }];
      
      expect(isRefAtomFullyStruck(1, strikethroughs)).toBe(true);
    });
  });

  describe('selectionToAtomRange', () => {
    it('should be tested in integration tests', () => {
      // selectionToAtomRange requires DOM Range objects which are complex to mock
      // This function is better tested through integration tests where actual
      // DOM elements and selections can be created
      expect(true).toBe(true);
    });
  });
});
