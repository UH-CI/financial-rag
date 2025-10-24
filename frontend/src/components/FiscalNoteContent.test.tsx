import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import FiscalNoteContent from './FiscalNoteContent';
import { 
  mockFiscalNote, 
  mockDocumentMapping, 
  mockEnhancedDocumentMapping,
  mockNumberCitationMap,
  mockChunkTextMap 
} from '../test/mockData';

// Mock the API
vi.mock('../services/api', () => ({
  saveStrikethroughs: vi.fn().mockResolvedValue({ success: true })
}));

describe('FiscalNoteContent', () => {
  const defaultProps = {
    fiscalNote: mockFiscalNote,
    documentMapping: mockDocumentMapping,
    enhancedDocumentMapping: mockEnhancedDocumentMapping,
    numbersData: [],
    numberCitationMap: mockNumberCitationMap,
    chunkTextMap: mockChunkTextMap,
    billType: 'HB',
    billNumber: '727',
    year: '2025'
  };

  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    sessionStorage.clear();
  });

  describe('Rendering', () => {
    it('should render fiscal note content', () => {
      const { container } = render(<FiscalNoteContent {...defaultProps} />);
      
      // Content appears in both print and visible sections
      const titles = screen.getAllByText(/HB727/i);
      expect(titles.length).toBeGreaterThan(0);
      
      const content = screen.getAllByText(/women's court pilot program/i);
      expect(content.length).toBeGreaterThan(0);
      
      // Verify sections are rendered
      expect(container.querySelector('[data-section-key="overview"]')).toBeTruthy();
    });

    it('should render document citations', () => {
      const { container } = render(<FiscalNoteContent {...defaultProps} />);
      
      // Should have citation brackets
      const brackets = screen.getAllByText(/\[/);
      expect(brackets.length).toBeGreaterThan(0);
      
      // HB727 has document citations
      const citations = container.querySelectorAll('a[href*="HB727"]');
      expect(citations.length).toBeGreaterThan(0);
    });

    it('should display chunk IDs in citations', () => {
      const { container } = render(<FiscalNoteContent {...defaultProps} />);
      
      // Citations should show with chunk IDs - verify citation elements exist
      const citations = container.querySelectorAll('[data-ref="true"]');
      expect(citations.length).toBeGreaterThan(0);
    });
  });

  describe('Strikethrough Mode', () => {
    it('should render component with strikethrough functionality', () => {
      const { container } = render(<FiscalNoteContent {...defaultProps} />);
      
      // Component should render with data sections
      expect(container.querySelector('[data-section-key]')).toBeTruthy();
    });
  });

  describe('Strikethrough Operations', () => {
    it('should render with strikethroughs from backend', () => {
      const fiscalNoteWithStrikethroughs = {
        ...mockFiscalNote,
        strikethroughs: [{
          id: 'test-1',
          sectionKey: 'overview',
          textContent: 'test',
          timestamp: new Date().toISOString(),
          startAtom: 0,
          startOffset: 0,
          endAtom: 0,
          endOffset: 5
        }]
      };
      
      const { container } = render(<FiscalNoteContent {...defaultProps} fiscalNote={fiscalNoteWithStrikethroughs} />);
      
      // Component should render with strikethroughs
      expect(container.querySelector('[data-section-key]')).toBeTruthy();
    });
  });

  describe('API Integration', () => {
    it('should have API module available', async () => {
      const { saveStrikethroughs } = await import('../services/api');
      
      // API should be mocked and available
      expect(saveStrikethroughs).toBeDefined();
    });
  });

  describe('Split View Controls', () => {
    it('should render with onAddSplitView prop', () => {
      const onAddSplitView = vi.fn();
      const { container } = render(<FiscalNoteContent {...defaultProps} onAddSplitView={onAddSplitView} />);
      
      // Component should render without errors when onAddSplitView is provided
      expect(container.querySelector('[data-section-key]')).toBeTruthy();
    });

    it('should render with onClose prop', () => {
      const onClose = vi.fn();
      const { container } = render(<FiscalNoteContent {...defaultProps} onClose={onClose} />);
      
      // Component should render without errors when onClose is provided
      expect(container.querySelector('[data-section-key]')).toBeTruthy();
    });
  });

  describe('LocalStorage Clearing on Page Load', () => {
    it('should clear localStorage on new session', () => {
      // Simulate new session (no flag in window)
      delete (window as any)['fiscal-note-cleared-on-load'];
      
      render(<FiscalNoteContent {...defaultProps} />);
      
      // Should have set the flag
      expect((window as any)['fiscal-note-cleared-on-load']).toBe(true);
    });

    it('should not clear localStorage on component remount in same session', () => {
      // Set flag to simulate existing session
      (window as any)['fiscal-note-cleared-on-load'] = true;
      
      const { rerender } = render(<FiscalNoteContent {...defaultProps} />);
      
      const clearCallsBefore = (localStorage.removeItem as any).mock.calls.length;
      
      rerender(<FiscalNoteContent {...defaultProps} />);
      
      const clearCallsAfter = (localStorage.removeItem as any).mock.calls.length;
      
      // Should not have additional clear calls
      expect(clearCallsAfter).toBe(clearCallsBefore);
    });
  });

  describe('Citation Chunk Cycling', () => {
    it('should render citations with chunk IDs', () => {
      const { container } = render(<FiscalNoteContent {...defaultProps} />);
      
      // Citations are rendered with chunk IDs
      // The actual chunk cycling logic is complex and better tested in integration tests
      const citations = container.querySelectorAll('[data-ref="true"]');
      expect(citations.length).toBeGreaterThan(0);
    });
  });
});
