import React, { useState, useEffect, useMemo, useRef } from 'react';
import type { FiscalNoteItem, DocumentInfo, StrikethroughItem, Atom, NumberCitationMapItem, ChunkTextMapItem } from '../types';
import DocumentReferenceComponent from './DocumentReference';
import { parseToAtoms, segmentsForAtom, isRefAtomFullyStruck, selectionToAtomRange } from '../utils/atomStrikethrough';
import { saveStrikethroughs } from '../services/api';

interface FiscalNoteContentProps {
  fiscalNote: FiscalNoteItem;
  documentMapping: Record<string, number>;
  enhancedDocumentMapping: Record<number, DocumentInfo>;
  numbersData: any[]; // Keep for API compatibility but not used in current implementation
  numberCitationMap: Record<number, NumberCitationMapItem>;
  chunkTextMap: Record<number, ChunkTextMapItem[]>;
  billType: string; // NEW: Bill type for saving strikethroughs
  billNumber: string; // NEW: Bill number for saving strikethroughs
  year: string; // NEW: Year for saving strikethroughs
  onClose?: () => void; // Optional close handler for split view
  onAddSplitView?: () => void; // Optional handler to enable split view
  position?: 'left' | 'right' | 'center'; // Position for toolbar in split view
}

const FiscalNoteContent: React.FC<FiscalNoteContentProps> = ({
  fiscalNote,
  documentMapping,
  enhancedDocumentMapping,
  numberCitationMap,
  chunkTextMap,
  billType,
  billNumber,
  year,
  onClose,
  onAddSplitView,
  position = 'center'
}) => {
  // State for edit mode and tracking changes
  // Initialize from localStorage to persist across view changes
  const [isStrikeoutMode, setIsStrikeoutMode] = useState(() => {
    const saved = localStorage.getItem(`strikeout-mode-${fiscalNote.filename}`);
    return saved === 'true';
  });
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  
  // Store strikethroughs as array of items
  const [strikethroughs, setStrikethroughs] = useState<StrikethroughItem[]>([]);
  
  // Parse fiscal note data into atoms (memoized for performance)
  const sectionAtoms = useMemo(() => {
    const atoms: Record<string, Atom[]> = {};
    if (fiscalNote.data && typeof fiscalNote.data === 'object') {
      Object.entries(fiscalNote.data).forEach(([key, value]) => {
        if (typeof value === 'string') {
          atoms[key] = parseToAtoms(value);
        }
      });
    }
    return atoms;
  }, [fiscalNote.data]);
  
  const contentRef = useRef<HTMLDivElement>(null);
  
  // Undo/Redo state
  const [history, setHistory] = useState<StrikethroughItem[][]>([[]]);
  const [historyIndex, setHistoryIndex] = useState(0);
  const canUndo = historyIndex > 0;
  const canRedo = historyIndex < history.length - 1;
  
  // Generate unique ID for this fiscal note instance
  const printContentId = `fiscal-note-print-content-${fiscalNote.filename.replace(/[^a-zA-Z0-9]/g, '-')}`;
  
  // Clear localStorage strikethrough data on page load (not on component remount)
  // Use a module-level flag to ensure this only runs once per page load
  useEffect(() => {
    // Check if we've already cleared localStorage in this page load
    const clearFlagKey = 'fiscal-note-cleared-on-load';
    const alreadyCleared = (window as any)[clearFlagKey];
    
    if (!alreadyCleared) {
      // First component mount of this page load - clear all localStorage strikethrough data
      console.log('🔄 Page load detected - clearing all localStorage strikethrough data');
      const keysToRemove: string[] = [];
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (key && key.startsWith('fiscal-note-strikethroughs-')) {
          keysToRemove.push(key);
        }
      }
      keysToRemove.forEach(key => {
        console.log(`  🗑️ Removing: ${key}`);
        localStorage.removeItem(key);
      });
      
      // Set flag in window object (cleared on page refresh)
      (window as any)[clearFlagKey] = true;
      console.log('✅ localStorage cleared on page load');
    } else {
      console.log('♻️ Component remount - localStorage already cleared this session');
    }
  }, []); // Empty deps - runs once on mount
  
  // Load strikethroughs from backend when fiscal note changes
  // localStorage is only used for temporary persistence during same session (between view changes)
  useEffect(() => {
    console.log(`🔄 Loading fiscal note: ${fiscalNote.filename}`);
    
    // Always prioritize backend data (source of truth)
    const backendStrikethroughs = fiscalNote.strikethroughs || [];
    
    // Check localStorage for unsaved changes from this session
    const localKey = `fiscal-note-strikethroughs-${fiscalNote.filename}`;
    const savedLocal = localStorage.getItem(localKey);
    
    if (savedLocal) {
      try {
        const parsed = JSON.parse(savedLocal);
        
        // Only use localStorage if it's different from backend (indicates unsaved changes)
        const isDifferent = JSON.stringify(parsed) !== JSON.stringify(backendStrikethroughs);
        
        if (isDifferent) {
          setStrikethroughs(parsed);
          setHistory([[], parsed]);
          setHistoryIndex(1);
          setHasUnsavedChanges(true);
          console.log('💾 Loaded UNSAVED strikethroughs from localStorage:', parsed.length);
          return;
        } else {
          // localStorage matches backend, clear it
          localStorage.removeItem(localKey);
          console.log('🧹 Cleared localStorage (matches backend)');
        }
      } catch (e) {
        console.error('Failed to parse localStorage strikethroughs:', e);
        localStorage.removeItem(localKey);
      }
    }
    
    // Load from backend
    if (backendStrikethroughs.length > 0) {
      setStrikethroughs(backendStrikethroughs);
      setHistory([[], backendStrikethroughs]);
      setHistoryIndex(1);
      setHasUnsavedChanges(false);
      console.log('📥 Loaded strikethroughs from backend:', backendStrikethroughs.length);
    } else {
      // Fresh fiscal note, no strikethroughs
      setStrikethroughs([]);
      setHistory([[]]);
      setHistoryIndex(0);
      setHasUnsavedChanges(false);
      console.log('🆕 Fresh fiscal note, no strikethroughs');
    }
  }, [fiscalNote.filename, fiscalNote.strikethroughs]); // Reset when switching notes or backend data changes
  
  // Save strikethroughs to localStorage whenever they change
  useEffect(() => {
    console.log(`📊 Current strikethroughs for ${fiscalNote.filename}:`, strikethroughs.length, strikethroughs);
    
    if (strikethroughs.length > 0) {
      const localKey = `fiscal-note-strikethroughs-${fiscalNote.filename}`;
      localStorage.setItem(localKey, JSON.stringify(strikethroughs));
      console.log('💾 Saved to localStorage:', localKey);
    }
  }, [strikethroughs, fiscalNote.filename]);
  
  // Print handler - creates a custom print view
  const handlePrint = () => {
    // Get the fiscal note content element
    const printContent = document.getElementById(printContentId);
    if (!printContent) return;
    
    // Create a new window for printing
    const printWindow = window.open('', '_blank');
    if (!printWindow) return;
    
    // Write the content to the new window
    printWindow.document.write(`
      <!DOCTYPE html>
      <html>
        <head>
          <title>Fiscal Note - ${fiscalNote.filename}</title>
          <style>
            body {
              font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
              line-height: 1.6;
              color: #111827;
              max-width: 8.5in;
              margin: 0 auto;
              padding: 0.5in;
            }
            h1 {
              font-size: 24pt;
              font-weight: bold;
              margin-bottom: 8pt;
            }
            h2 {
              font-size: 16pt;
              color: #4b5563;
              margin-bottom: 16pt;
            }
            h3 {
              font-size: 14pt;
              font-weight: 600;
              margin-top: 16pt;
              margin-bottom: 8pt;
            }
            h4 {
              font-size: 11pt;
              font-weight: 600;
              margin-top: 12pt;
              margin-bottom: 6pt;
            }
            p {
              margin-bottom: 8pt;
            }
            .citation-references {
              margin-top: 24pt;
              padding-top: 12pt;
              border-top: 1pt solid #d1d5db;
            }
            .citation-references h2 {
              font-size: 12pt;
              margin-bottom: 8pt;
            }
            .citation-item {
              display: flex;
              margin-bottom: 3pt;
              font-size: 8pt;
              line-height: 1.3;
            }
            .citation-number {
              font-family: monospace;
              font-weight: 600;
              min-width: 30pt;
              flex-shrink: 0;
            }
            .citation-name {
              color: #374151;
            }
            a {
              color: #000;
              text-decoration: none;
            }
            ul, ol {
              margin-bottom: 8pt;
              padding-left: 24pt;
            }
            li {
              margin-bottom: 4pt;
            }
            /* Citation colors - preserve in print */
            .text-blue-600 {
              color: #2563eb;
            }
            .bg-blue-50 {
              background-color: #eff6ff;
            }
            .text-green-600 {
              color: #16a34a;
            }
            .bg-green-50 {
              background-color: #f0fdf4;
            }
            .font-medium {
              font-weight: 500;
            }
            .px-1 {
              padding-left: 0.25rem;
              padding-right: 0.25rem;
            }
            .py-0\.5 {
              padding-top: 0.125rem;
              padding-bottom: 0.125rem;
            }
            .rounded {
              border-radius: 0.25rem;
            }
            .text-sm {
              font-size: 0.875rem;
            }
            /* Previous section strikethrough */
            .line-through {
              text-decoration: line-through;
            }
            .text-gray-500 {
              color: #6b7280;
            }
            .italic {
              font-style: italic;
            }
            .opacity-70 {
              opacity: 0.7;
            }
          </style>
        </head>
        <body>
          ${printContent.innerHTML}
        </body>
      </html>
    `);
    
    printWindow.document.close();
    
    // Wait for content to load, then print
    printWindow.onload = () => {
      printWindow.focus();
      printWindow.print();
      printWindow.close();
    };
  };
  // Generate proper URL for documents
  const generateDocumentUrl = (docName: string) => {
    const base_url = "https://www.capitol.hawaii.gov/sessions/session2025";
    
    if (docName.includes("TESTIMONY")) {
      return `${base_url}/Testimony/${docName}.PDF`;
    } else if (docName.startsWith("HB") || docName.startsWith("SB")) {
      if (docName.includes("HSCR") || docName.includes("CCR") || docName.includes("SSCR")) {
        return `${base_url}/CommReports/${docName}.htm`;
      } else {
        return `${base_url}/bills/${docName}_.HTM`;
      }
    } else {
      return `${base_url}/CommReports/${docName}.htm`;
    }
  };

  // Note: Strikethroughs are loaded from fiscalNote.strikethroughs in the effect above
  // No localStorage needed - backend is source of truth

  // Handle saving changes to backend
  const handleSaveChanges = async () => {
    try {
      console.log(`💾 Saving ${strikethroughs.length} strikethroughs to backend...`);
      
      const result = await saveStrikethroughs(fiscalNote.filename, strikethroughs, billType, billNumber, year);
      console.log('✅ Backend response:', result);
      
      setHasUnsavedChanges(false);
      
      // Clear localStorage after successful save
      const localKey = `fiscal-note-strikethroughs-${fiscalNote.filename}`;
      localStorage.removeItem(localKey);
      
      console.log('✅ Strikethroughs saved to backend and localStorage cleared');
      alert(`Successfully saved ${strikethroughs.length} strikethroughs!`);
    } catch (error) {
      console.error('❌ Failed to save:', error);
      alert(`Failed to save changes: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  };

  // Handle discarding changes
  const handleDiscardChanges = () => {
    // Restore from backend (fiscalNote.strikethroughs) or empty if none
    const backendStrikethroughs = fiscalNote.strikethroughs || [];
    setStrikethroughs(backendStrikethroughs);
    setHasUnsavedChanges(false);
    setHistory([[], backendStrikethroughs]);
    setHistoryIndex(backendStrikethroughs.length > 0 ? 1 : 0);
    
    // Clear localStorage
    const localKey = `fiscal-note-strikethroughs-${fiscalNote.filename}`;
    localStorage.removeItem(localKey);
    
    console.log(`🗑️ Discarded changes - restored ${backendStrikethroughs.length} strikethroughs from backend`);
  };

  // Removed unused handleClearStrikethroughs function

  // Handle undo
  const handleUndo = () => {
    if (!canUndo) return;
    const newIndex = historyIndex - 1;
    console.log('↩️ Undo:', {
      from: historyIndex,
      to: newIndex,
      strikethroughs: history[newIndex].length
    });
    setHistoryIndex(newIndex);
    setStrikethroughs(history[newIndex]);
    setHasUnsavedChanges(newIndex > 0);
  };

  // Handle redo
  const handleRedo = () => {
    if (!canRedo) return;
    const newIndex = historyIndex + 1;
    console.log('↪️ Redo:', {
      from: historyIndex,
      to: newIndex,
      strikethroughs: history[newIndex].length
    });
    setHistoryIndex(newIndex);
    setStrikethroughs(history[newIndex]);
    setHasUnsavedChanges(true);
  };

  // Add to history when strikethroughs change
  const addToHistory = (newStrikethroughs: StrikethroughItem[]) => {
    const newHistory = history.slice(0, historyIndex + 1);
    newHistory.push(newStrikethroughs);
    setHistory(newHistory);
    setHistoryIndex(newHistory.length - 1);
    setStrikethroughs(newStrikethroughs);
  };

  // Warn user before leaving if there are unsaved changes
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (hasUnsavedChanges) {
        e.preventDefault();
        e.returnValue = '';
      }
    };

    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [hasUnsavedChanges]);

  // Helper function to find section key from selection
  const findSectionKeyFromSelection = (selection: Selection): string | null => {
    const checkNode = (node: Node | null, label: string): string | null => {
      console.log(`Checking ${label}:`, node);
      let current = node;
      let depth = 0;
      
      // Go all the way up the tree
      while (current && depth < 20) {
        console.log(`  Level ${depth}:`, current.nodeName, current instanceof HTMLElement ? (current as HTMLElement).className : 'not element');
        
        if (current instanceof HTMLElement) {
          // Check if this element has the data-section-key attribute
          const sectionKey = current.getAttribute('data-section-key');
          if (sectionKey) {
            console.log(`  ✅ Found section key at level ${depth}:`, sectionKey);
            return sectionKey;
          }
        }
        // Stop if we've reached contentRef or document
        if (current === contentRef.current || current === document.body) {
          console.log(`  Reached boundary at level ${depth}`);
          break;
        }
        current = current.parentNode;
        depth++;
      }
      return null;
    };
    
    // Try anchor node first
    let result = checkNode(selection.anchorNode, 'anchor node');
    if (result) return result;
    
    // Try focus node
    result = checkNode(selection.focusNode, 'focus node');
    if (result) return result;
    
    // Try range common ancestor
    try {
      const range = selection.getRangeAt(0);
      result = checkNode(range.commonAncestorContainer, 'range container');
      if (result) return result;
    } catch (e) {
      // Ignore
    }
    
    // Last resort: search within contentRef for any element with data-section-key
    if (contentRef.current) {
      const allSections = contentRef.current.querySelectorAll('[data-section-key]');
      if (allSections.length > 0) {
        // Return the first one as a fallback
        const firstSection = allSections[0] as HTMLElement;
        return firstSection.getAttribute('data-section-key');
      }
    }
    
    return null;
  };


  // Apply strikethrough immediately on selection
  useEffect(() => {
    if (!isStrikeoutMode || !contentRef.current) return;

    const handleMouseUp = () => {
      const selection = window.getSelection();
      if (!selection || selection.isCollapsed) {
        return;
      }

      const selectedText = selection.toString().trim();
      if (!selectedText) {
        return;
      }

      // Check if selection is within this component's content
      const range = selection.getRangeAt(0);
      if (!contentRef.current?.contains(range.commonAncestorContainer)) {
        return;
      }

      // Map selection to atom range immediately
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

      // Apply strikethrough immediately
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

      console.log('✏️ Strikethrough applied:', {
        text: selectedText,
        section: sectionKey,
        atomRange,
        total: newStrikethroughs.length
      });

      // Clear selection
      selection.removeAllRanges();
    };

    const contentElement = contentRef.current;
    contentElement.addEventListener('mouseup', handleMouseUp);
    
    return () => {
      contentElement.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isStrikeoutMode, strikethroughs, addToHistory]);

  // Render atoms for a section with strikethroughs applied
  const renderAtomsForSection = (sectionKey: string): React.ReactNode => {
    const atoms = sectionAtoms[sectionKey];
    if (!atoms || atoms.length === 0) {
      return null;
    }

    // Get strikethroughs for this section
    const sectionStrikethroughs = strikethroughs.filter(st => st.sectionKey === sectionKey);
    
    if (sectionStrikethroughs.length > 0) {
      console.log(`📝 Rendering section "${sectionKey}" with ${sectionStrikethroughs.length} strikethroughs:`, sectionStrikethroughs);
    }

    // Track citation occurrences within this section to cycle through chunks
    const citationOccurrences: Record<number, number> = {};

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
        const citationContent = atom.refId;
        
        // Parse citation - could be "5", "5.3", or "CHUNK 1, NUMBER 5"
        let citationNumber: number;
        let chunkId: number | undefined;
        
        // Check if it's a complex citation format
        if (citationContent.includes('CHUNK') && citationContent.includes('NUMBER')) {
          const numberMatch = citationContent.match(/NUMBER\s+(\d+)/);
          const chunkMatch = citationContent.match(/CHUNK\s+(\d+)/);
          citationNumber = numberMatch ? parseInt(numberMatch[1]) : parseFloat(citationContent);
          chunkId = chunkMatch ? parseInt(chunkMatch[1]) : undefined;
        } else if (citationContent.includes('.')) {
          // Format like "5.3" - document.chunk
          const parts = citationContent.split('.');
          citationNumber = parseInt(parts[0]);
          chunkId = parts[1] ? parseInt(parts[1]) : undefined;
        } else {
          // Simple number
          citationNumber = parseFloat(citationContent);
        }
        
        // Check if this is a financial citation
        const financialCitation = numberCitationMap[citationNumber];
        
        if (financialCitation) {
          // Financial citation
          const numberData = financialCitation.data;
          const contextText = numberData ? numberData.text : `Amount referenced in ${financialCitation.filename}`;
          
          // Find the document number for this financial citation's document
          let documentNumber: number | null = null;
          for (const [docName, docNum] of Object.entries(documentMapping)) {
            if (docName === financialCitation.document_name) {
              documentNumber = docNum;
              break;
            }
          }
          
          const displayNumber = documentNumber ? `${documentNumber}.${citationNumber}` : citationNumber.toString();
          
          return (
            <span
              key={atomIndex}
              data-atom-index={atomIndex}
              data-ref="true"
              className={isStruck ? 'line-through text-gray-500 italic' : 'inline-flex items-center'}
            >
              <span className="text-green-600">[</span>
              <DocumentReferenceComponent
                reference={{
                  type: 'document_reference',
                  number: citationNumber,
                  displayNumber: displayNumber,
                  url: generateDocumentUrl(financialCitation.document_name),
                  document_type: 'Financial Citation',
                  document_name: financialCitation.document_name,
                  description: `$${financialCitation.amount.toLocaleString()} from ${financialCitation.document_name}`,
                  chunk_text: contextText,
                  similarity_score: undefined,
                  financial_amount: financialCitation.amount
                }}
              />
              <span className="text-green-600">]</span>
            </span>
          );
        }
        
        // Regular document citation
        const docInfo = enhancedDocumentMapping[citationNumber];
        const chunkData = chunkTextMap[citationNumber];
        
        // Determine which chunk to use
        let chunkInfo = chunkData?.[0];
        
        if (chunkId !== undefined && chunkData) {
          // Citation has explicit chunk ID - find the matching chunk
          chunkInfo = chunkData.find(c => c.chunk_id === chunkId) || chunkData[0];
        } else if (chunkData && chunkData.length > 0) {
          // No explicit chunk ID - cycle through available chunks
          // Track how many times we've seen this citation number
          if (!citationOccurrences[citationNumber]) {
            citationOccurrences[citationNumber] = 0;
          }
          const occurrenceIndex = citationOccurrences[citationNumber];
          citationOccurrences[citationNumber]++;
          
          // Cycle through chunks using modulo
          const chunkIndex = occurrenceIndex % chunkData.length;
          chunkInfo = chunkData[chunkIndex];
        }
        
        const displayNumber = chunkInfo?.chunk_id 
          ? `${citationNumber}.${chunkInfo.chunk_id}` 
          : citationNumber.toString();
        
        return (
          <span
            key={atomIndex}
            data-atom-index={atomIndex}
            data-ref="true"
            className={isStruck ? 'line-through text-gray-500 italic' : 'inline-flex items-center'}
          >
            <span className="text-blue-600">[</span>
            <DocumentReferenceComponent
              reference={{
                type: 'document_reference',
                number: citationNumber,
                displayNumber: displayNumber,
                url: generateDocumentUrl(docInfo?.name || ''),
                document_type: docInfo?.type || 'Document',
                document_name: docInfo?.name || `Document ${citationNumber}`,
                description: docInfo?.description || '',
                document_category: docInfo?.type,
                document_icon: docInfo?.icon,
                chunk_text: chunkInfo?.chunk_text,
                similarity_score: chunkInfo?.attribution_score,
                sentence: chunkInfo?.sentence,
                chunk_id: chunkInfo?.chunk_id
              }}
            />
            <span className="text-blue-600">]</span>
          </span>
        );
      }
    });
  };

  // Function to render any value (string, object, array)
  const renderValue = (value: any, sectionKey?: string): React.ReactNode => {
    if (value === null || value === undefined) {
      return <span className="text-gray-400 italic">Not specified</span>;
    }

    if (typeof value === 'string') {
      // Use atom-based rendering with strikethroughs
      return (
        <div className="text-gray-700 leading-relaxed" data-section-key={sectionKey} style={{ whiteSpace: 'pre-wrap' }}>
          {renderAtomsForSection(sectionKey || '')}
        </div>
      );
    }

    if (typeof value === 'object' && !Array.isArray(value)) {
      return (
        <div className="space-y-4">
          {Object.entries(value).map(([subKey, subValue]) => (
            <div key={subKey}>
              <h4 className="text-sm font-semibold text-gray-800 mb-2 capitalize">
                {subKey.replace(/_/g, ' ')}
              </h4>
              <div className="ml-4">
                {renderValue(subValue, subKey)}
              </div>
            </div>
          ))}
        </div>
      );
    }

    if (Array.isArray(value)) {
      return (
        <ul className="space-y-2">
          {value.map((item, index) => (
            <li key={index} className="flex items-start space-x-2">
              <span className="w-1.5 h-1.5 bg-gray-400 rounded-full mt-2 flex-shrink-0"></span>
              <div className="flex-1">
                {renderValue(item)}
              </div>
            </li>
          ))}
        </ul>
      );
    }

    return <span className="text-gray-700">{String(value)}</span>;
  };

  // Function to format section titles
  const formatSectionTitle = (key: string): string => {
    return key
      .replace(/_/g, ' ')
      .replace(/\b\w/g, l => l.toUpperCase());
  };

  if (!fiscalNote) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="text-gray-400 mb-2">📄</div>
          <div className="text-gray-600">No fiscal note selected</div>
        </div>
      </div>
    );
  }

  // Collect all citations used in the fiscal note (including both document and financial citations)
  const collectCitations = (): Array<{number: number, documentName: string}> => {
    const citationList: Array<{number: number, documentName: string}> = [];
    
    // Add all document citations from documentMapping
    for (const [docName, docNum] of Object.entries(documentMapping)) {
      citationList.push({ number: docNum, documentName: docName });
    }
    
    // Helper to extract financial citations from text
    const extractFinancialCitations = (text: string) => {
      if (!text || typeof text !== 'string') return;
      const citationRegex = /\[(\d+)\]/g;
      let match;
      const foundFinancialCitations = new Set<number>();
      
      while ((match = citationRegex.exec(text)) !== null) {
        const citationNumber = parseInt(match[1]);
        
        // Check if it's a financial citation and not already added
        if (numberCitationMap[citationNumber] && !foundFinancialCitations.has(citationNumber)) {
          foundFinancialCitations.add(citationNumber);
          const documentName = numberCitationMap[citationNumber].document_name;
          
          // Check if this document is already in the list
          const existingDoc = citationList.find(c => c.documentName === documentName);
          if (!existingDoc) {
            // Find the document number
            let docNum = null;
            for (const [dName, dNumber] of Object.entries(documentMapping)) {
              if (dName === documentName) {
                docNum = dNumber;
                break;
              }
            }
            if (docNum) {
              citationList.push({ number: docNum, documentName });
            }
          }
        }
      }
    };
    
    // Extract financial citations from all sections
    const extractFromValue = (value: any): void => {
      if (typeof value === 'string') {
        extractFinancialCitations(value);
      } else if (typeof value === 'object' && value !== null) {
        if (Array.isArray(value)) {
          value.forEach(item => extractFromValue(item));
        } else {
          Object.values(value).forEach(subValue => extractFromValue(subValue));
        }
      }
    };
    
    if (fiscalNote.data) {
      extractFromValue(fiscalNote.data);
    }
    
    // Sort by citation number
    return citationList.sort((a, b) => a.number - b.number);
  };

  // Render the main content (used for both display and print)
  // Note: Not memoized - needs to re-render when strikethroughs change
  const renderContent = () => (
    <>
      {fiscalNote.data && typeof fiscalNote.data === 'object' ? (
        <div className="divide-y divide-gray-200">
          {Object.entries(fiscalNote.data).map(([key, value]) => (
            <div key={key} className="p-6" data-section-key={key}>
              <h3 className="text-lg font-semibold text-gray-900 mb-4">
                {formatSectionTitle(key)}
              </h3>
              <div className="prose max-w-none">
                {renderValue(value, key)}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="p-6">
          <div className="prose max-w-none">
            {renderValue(fiscalNote.data)}
          </div>
        </div>
      )}
    </>
  );

  return (
    <div className="w-full h-full">
      <div className="max-w-4xl mx-auto p-8 pb-32">
        {/* Hidden print content container */}
        <div id={printContentId} style={{ display: 'none' }}>
        <h1>Fiscal Note Analysis</h1>
        <h2>{fiscalNote.filename}</h2>
        {renderContent()}
        <div className="citation-references">
          <h2>Document References</h2>
          <div>
            {collectCitations().map(({ number, documentName }) => (
              <div key={number} className="citation-item">
                <span className="citation-number">[{number}]</span>
                <span className="citation-name">{documentName}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Visible content */}
      <div className="mb-8">
        <div className="flex justify-between items-start">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 mb-2">
              Fiscal Note Analysis
            </h1>
            <h2 className="text-xl text-gray-600">
              {fiscalNote.filename}
            </h2>
          </div>
        </div>
      </div>

      {/* Content */}
      <div 
        className={`bg-white rounded-lg shadow-sm border overflow-hidden transition-all ${
          isStrikeoutMode 
            ? 'border-orange-400 border-2 cursor-text' 
            : 'border-gray-200'
        }`}
        style={{ 
          userSelect: isStrikeoutMode ? 'text' : 'auto',
          cursor: isStrikeoutMode 
            ? `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='20' height='24' viewBox='0 0 20 24'%3E%3Cg stroke='%23000' stroke-width='1.5' fill='none'%3E%3Cline x1='10' y1='2' x2='10' y2='22'/%3E%3Cline x1='6' y1='2' x2='14' y2='2'/%3E%3Cline x1='6' y1='22' x2='14' y2='22'/%3E%3C/g%3E%3Crect x='7' y='10' width='6' height='4' fill='white' stroke='%23f97316' stroke-width='1.5'/%3E%3Cline x1='4' y1='12' x2='16' y2='12' stroke='%23f97316' stroke-width='2' stroke-linecap='round'/%3E%3C/svg%3E") 10 12, text`
            : 'auto'
        }}
      >
        {hasUnsavedChanges && (
          <div className="bg-yellow-50 border-b border-yellow-200 px-4 py-2 text-sm text-yellow-800 font-medium flex items-center gap-2">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10"></circle>
              <line x1="12" y1="8" x2="12" y2="12"></line>
              <line x1="12" y1="16" x2="12.01" y2="16"></line>
            </svg>
            <span>Unsaved Strikethroughs - Click Save to persist changes</span>
          </div>
        )}
        {isStrikeoutMode && (
          <div className="bg-orange-50 border-b border-orange-200 px-4 py-2 text-sm text-orange-700 font-medium">
            ✏️ Strikeout Mode Active - Select text to mark as removed
          </div>
        )}
        <div ref={contentRef}>
          {renderContent()}
        </div>
      </div>

      {/* Footer with document mapping info */}
      {documentMapping && Object.keys(documentMapping).length > 0 && (
        <div className="mt-8 p-4 bg-gray-50 rounded-lg">
          <h4 className="text-sm font-semibold text-gray-700 mb-2">
            Document Reference Guide
          </h4>
          <p className="text-xs text-gray-600">
            Numbers in brackets like [1], [2] are clickable references to source documents. 
            Hover over them to see document details, or click to open the full document.
          </p>
        </div>
      )}
      </div>

      {/* Floating Edit Toolbar - Fixed at bottom of viewport, always visible, aligned with content */}
      <div 
        className="fixed bottom-4 z-50 pointer-events-none"
        style={{
          left: position === 'left' ? '0' : position === 'right' ? '75%' : '0',
          right: position === 'right' ? '0' : position === 'left' ? '0%' : '0'
        }}
      >
        <div className="max-w-4xl mx-auto px-8 flex justify-center pointer-events-auto">
        <div className="bg-white rounded-full shadow-2xl border-2 border-gray-300 px-2 py-2 flex items-center gap-1">
          {/* Strikeout Mode Toggle */}
          <div className="relative group">
            <button
              onClick={() => {
                const newMode = !isStrikeoutMode;
                setIsStrikeoutMode(newMode);
                localStorage.setItem(`strikeout-mode-${fiscalNote.filename}`, String(newMode));
              }}
              className={`p-2 rounded-full transition-all ${
                isStrikeoutMode
                  ? 'bg-orange-600 text-white hover:bg-orange-700'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M16 4H9a3 3 0 0 0-2.83 4"></path>
                <path d="M14 12a4 4 0 0 1 0 8H6"></path>
                <line x1="4" y1="12" x2="20" y2="12"></line>
              </svg>
            </button>
            <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 bg-gray-900 text-white text-xs rounded whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
              {isStrikeoutMode ? 'Exit Strikeout Mode' : 'Enable Strikeout Mode'}
            </div>
          </div>

          {/* Divider */}
          <div className="w-px h-6 bg-gray-300"></div>

          {/* Clear All Strikethroughs Button */}
          {strikethroughs.length > 0 && (
            <>
              <div className="relative group">
                <button
                  onClick={async () => {
                    if (window.confirm(`Are you sure you want to clear all ${strikethroughs.length} strikethroughs from this fiscal note? This will permanently remove them.`)) {
                      try {
                        console.log('🗑️ Clearing all strikethroughs and saving...');
                        
                        // Clear strikethroughs
                        const newStrikethroughs: StrikethroughItem[] = [];
                        setStrikethroughs(newStrikethroughs);
                        setHistory([[], newStrikethroughs]);
                        setHistoryIndex(1);
                        
                        // Clear localStorage
                        const localKey = `fiscal-note-strikethroughs-${fiscalNote.filename}`;
                        localStorage.removeItem(localKey);
                        
                        // Save immediately to backend
                        const result = await saveStrikethroughs(fiscalNote.filename, newStrikethroughs, billType, billNumber, year);
                        console.log('✅ Cleared and saved:', result);
                        
                        setHasUnsavedChanges(false);
                        alert('All strikethroughs cleared and saved!');
                      } catch (error) {
                        console.error('❌ Failed to clear strikethroughs:', error);
                        alert(`Failed to clear strikethroughs: ${error instanceof Error ? error.message : 'Unknown error'}`);
                        // Revert on error
                        setStrikethroughs(fiscalNote.strikethroughs || []);
                      }
                    }
                  }}
                  className="p-2 rounded-full bg-red-100 text-red-600 hover:bg-red-200 transition-all"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M3 6h18"></path>
                    <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"></path>
                    <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path>
                    <line x1="10" y1="11" x2="10" y2="17"></line>
                    <line x1="14" y1="11" x2="14" y2="17"></line>
                  </svg>
                </button>
                <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 bg-gray-900 text-white text-xs rounded whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                  Clear All ({strikethroughs.length})
                </div>
              </div>
              {/* Divider */}
              <div className="w-px h-6 bg-gray-300"></div>
            </>
          )}

          {/* Undo Button */}
          <div className="relative group">
            <button
              onClick={handleUndo}
              disabled={!canUndo}
              className={`p-2 rounded-full transition-all ${
                canUndo
                  ? 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  : 'bg-gray-50 text-gray-300 cursor-not-allowed'
              }`}
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M3 7v6h6"></path>
                <path d="M21 17a9 9 0 0 0-9-9 9 9 0 0 0-6 2.3L3 13"></path>
              </svg>
            </button>
            <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 bg-gray-900 text-white text-xs rounded whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
              Undo
            </div>
          </div>

          {/* Redo Button */}
          <div className="relative group">
            <button
              onClick={handleRedo}
              disabled={!canRedo}
              className={`p-2 rounded-full transition-all ${
                canRedo
                  ? 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  : 'bg-gray-50 text-gray-300 cursor-not-allowed'
              }`}
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 7v6h-6"></path>
                <path d="M3 17a9 9 0 0 1 9-9 9 9 0 0 1 6 2.3l3 2.7"></path>
              </svg>
            </button>
            <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 bg-gray-900 text-white text-xs rounded whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
              Redo
            </div>
          </div>

          {/* Divider */}
          {hasUnsavedChanges && (
            <div className="w-px h-6 bg-gray-300"></div>
          )}

          {/* Discard Button */}
          {hasUnsavedChanges && (
            <div className="relative group">
              <button
                onClick={handleDiscardChanges}
                className="p-2 rounded-full bg-gray-100 text-gray-700 hover:bg-red-100 hover:text-red-600 transition-all"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="3 6 5 6 21 6"></polyline>
                  <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                  <line x1="10" y1="11" x2="10" y2="17"></line>
                  <line x1="14" y1="11" x2="14" y2="17"></line>
                </svg>
              </button>
              <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 bg-gray-900 text-white text-xs rounded whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                Discard Changes
              </div>
            </div>
          )}

          {/* Save Button */}
          {hasUnsavedChanges && (
            <div className="relative group">
              <button
                onClick={handleSaveChanges}
                className="p-2 rounded-full bg-green-600 text-white hover:bg-green-700 transition-all"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path>
                  <polyline points="17 21 17 13 7 13 7 21"></polyline>
                  <polyline points="7 3 7 8 15 8"></polyline>
                </svg>
              </button>
              <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 bg-gray-900 text-white text-xs rounded whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                Save Changes
              </div>
            </div>
          )}

          {/* Divider */}
          <div className="w-px h-6 bg-gray-300"></div>

          {/* Print Button */}
          <div className="relative group">
            <button
              onClick={handlePrint}
              className="p-2 rounded-full bg-blue-100 text-blue-600 hover:bg-blue-200 transition-all"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="6 9 6 2 18 2 18 9"></polyline>
                <path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"></path>
                <rect x="6" y="14" width="12" height="8"></rect>
              </svg>
            </button>
            <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 bg-gray-900 text-white text-xs rounded whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
              Print
            </div>
          </div>

          {/* Compare Button */}
          {onAddSplitView && (
            <div className="relative group">
              <button
                onClick={onAddSplitView}
                className="p-2 rounded-full bg-green-100 text-green-600 hover:bg-green-200 transition-all"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="2" y="4" width="8" height="16" rx="1" opacity="0.3"></rect>
                  <rect x="14" y="4" width="8" height="16" rx="1" opacity="0.3"></rect>
                  <path d="M7 12h4"></path>
                  <polyline points="9 10 11 12 9 14"></polyline>
                  <path d="M17 12h-4"></path>
                  <polyline points="15 10 13 12 15 14"></polyline>
                </svg>
              </button>
              <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 bg-gray-900 text-white text-xs rounded whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                Compare
              </div>
            </div>
          )}

          {/* Close Button */}
          {onClose && (
            <div className="relative group">
              <button
                onClick={onClose}
                className="p-2 rounded-full bg-red-100 text-red-600 hover:bg-red-200 transition-all"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="18" y1="6" x2="6" y2="18"></line>
                  <line x1="6" y1="6" x2="18" y2="18"></line>
                </svg>
              </button>
              <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 bg-gray-900 text-white text-xs rounded whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                Close
              </div>
            </div>
          )}

          {/* Unsaved indicator dot */}
          {hasUnsavedChanges && (
            <div className="absolute -top-1 -right-1 w-3 h-3 bg-orange-500 rounded-full border-2 border-white"></div>
          )}
        </div>
        </div>
      </div>
    </div>
  );
};

export default FiscalNoteContent;
