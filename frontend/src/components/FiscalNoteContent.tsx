import React, { useState, useEffect, useMemo, useRef } from 'react';
import type { FiscalNoteItem, DocumentInfo, AnnotationItem, AnnotationType, Atom, NumberCitationMapItem, ChunkTextMapItem } from '../types';
import DocumentReferenceComponent from './DocumentReference';
import { parseToAtoms, segmentsForAtom, isRefAtomAnnotated, selectionToAtomRange } from '../utils/atomAnnotations';
import { saveStrikethroughs } from '../services/api';

interface FiscalNoteContentProps {
  fiscalNote: FiscalNoteItem;
  documentMapping: Record<string, number>;
  enhancedDocumentMapping: Record<number, DocumentInfo>;
  numbersData: any[]; // Keep for API compatibility but not used in current implementation
  numberCitationMap: Record<number, NumberCitationMapItem>;
  chunkTextMap: Record<number, ChunkTextMapItem[]>;
  billType: string; // NEW: Bill type for saving annotations
  billNumber: string; // NEW: Bill number for saving annotations
  year: string; // NEW: Year for saving annotations
  onClose?: () => void; // Optional close handler for split view
  onAddSplitView?: () => void; // Optional handler to enable split view
  onSaveSuccess?: () => void; // Optional callback after successful save to refresh data
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
  onSaveSuccess,
  position = 'center'
}) => {
  // State for edit mode and tracking changes
  // Annotation mode: null = off, 'strikethrough' = strikethrough mode, 'underline' = underline mode
  const [annotationMode, setAnnotationMode] = useState<AnnotationType | null>(null);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  
  // Store annotations as array of items (annotations + underlines)
  const [annotations, setAnnotations] = useState<AnnotationItem[]>([]);
  
  // Derived state: edit mode is active if annotationMode is not null
  const isStrikeoutMode = annotationMode !== null;
  
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
  const [history, setHistory] = useState<AnnotationItem[][]>([[]]);
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
        if (key && key.startsWith('fiscal-note-annotations-')) {
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
  
  // Load annotations from backend when fiscal note changes
  // localStorage is only used for temporary persistence during same session (between view changes)
  useEffect(() => {
    console.log(`🔄 Loading fiscal note: ${fiscalNote.filename}`);
    
    // Always prioritize backend data (source of truth)
    // Prefer annotations, fall back to annotations for backward compatibility
    let backendAnnotations = fiscalNote.annotations || [];
    
    // Migration: Convert legacy annotations to annotations if needed
    if (backendAnnotations.length === 0 && fiscalNote.annotations && fiscalNote.annotations.length > 0) {
      backendAnnotations = fiscalNote.annotations.map(st => ({
        ...st,
        type: st.type || 'strikethrough' as AnnotationType
      }));
      console.log(`🔄 Migrated ${backendAnnotations.length} legacy annotations to annotations`);
    }
    
    // Check localStorage for unsaved changes from this session
    const localKey = `fiscal-note-annotations-${fiscalNote.filename}`;
    const savedLocal = localStorage.getItem(localKey);
    
    if (savedLocal) {
      try {
        const parsed = JSON.parse(savedLocal);
        
        // Only use localStorage if it's different from backend (indicates unsaved changes)
        const isDifferent = JSON.stringify(parsed) !== JSON.stringify(backendAnnotations);
        
        if (isDifferent) {
          setAnnotations(parsed);
          setHistory([[], parsed]);
          setHistoryIndex(1);
          setHasUnsavedChanges(true);
          console.log('💾 Loaded UNSAVED annotations from localStorage:', parsed.length);
          return;
        } else {
          // localStorage matches backend, clear it
          localStorage.removeItem(localKey);
          console.log('🧹 Cleared localStorage (matches backend)');
        }
      } catch (e) {
        console.error('Failed to parse localStorage annotations:', e);
        localStorage.removeItem(localKey);
      }
    }
    
    // Load from backend
    if (backendAnnotations.length > 0) {
      setAnnotations(backendAnnotations);
      setHistory([[], backendAnnotations]);
      setHistoryIndex(1);
      setHasUnsavedChanges(false);
      console.log('📥 Loaded annotations from backend:', backendAnnotations.length);
    } else {
      // Fresh fiscal note, no annotations
      setAnnotations([]);
      setHistory([[]]);
      setHistoryIndex(0);
      setHasUnsavedChanges(false);
      console.log('🆕 Fresh fiscal note, no annotations');
    }
  }, [fiscalNote.filename, fiscalNote.annotations, fiscalNote.annotations]); // Reset when switching notes or backend data changes
  
  // Save annotations to localStorage whenever they change
  useEffect(() => {
    console.log(`📊 Current annotations for ${fiscalNote.filename}:`, annotations.length, annotations);
    
    if (annotations.length > 0) {
      const localKey = `fiscal-note-annotations-${fiscalNote.filename}`;
      localStorage.setItem(localKey, JSON.stringify(annotations));
      console.log('💾 Saved to localStorage:', localKey);
    }
  }, [annotations, fiscalNote.filename]);
  
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
            /* Strikethrough styling */
            .line-through {
              text-decoration: line-through;
            }
            .text-gray-500 {
              color: #6b7280;
            }
            .italic {
              font-style: italic;
            }
            /* Underline styling */
            .underline {
              text-decoration: underline;
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

  // Note: Annotations are loaded from fiscalNote.annotations in the effect above
  // No localStorage needed - backend is source of truth

  // Handle saving changes to backend
  const handleSaveChanges = async () => {
    try {
      console.log(`💾 Saving ${annotations.length} annotations to backend...`);
      
      const result = await saveStrikethroughs(fiscalNote.filename, annotations, billType, billNumber, year);
      console.log('✅ Backend response:', result);
      
      setHasUnsavedChanges(false);
      
      // Update the fiscalNote object to reflect the saved annotations
      // This prevents stale data when Compare is clicked
      fiscalNote.annotations = annotations;
      
      // Clear localStorage after successful save
      const localKey = `fiscal-note-annotations-${fiscalNote.filename}`;
      localStorage.removeItem(localKey);
      
      console.log('✅ Annotations saved to backend and localStorage cleared');
      
      // Notify parent to refresh data if callback provided
      if (onSaveSuccess) {
        console.log('🔄 Triggering parent refresh...');
        onSaveSuccess();
      }
      
      alert(`Successfully saved ${annotations.length} annotations!`);
    } catch (error) {
      console.error('❌ Failed to save:', error);
      alert(`Failed to save changes: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  };

  // Handle discarding changes
  const handleDiscardChanges = () => {
    // Restore from backend (fiscalNote.annotations) or empty if none
    const backendAnnotations = fiscalNote.annotations || [];
    setAnnotations(backendAnnotations);
    setHasUnsavedChanges(false);
    setHistory([[], backendAnnotations]);
    setHistoryIndex(backendAnnotations.length > 0 ? 1 : 0);
    
    // Clear localStorage
    const localKey = `fiscal-note-annotations-${fiscalNote.filename}`;
    localStorage.removeItem(localKey);
    
    console.log(`🗑️ Discarded changes - restored ${backendAnnotations.length} annotations from backend`);
  };

  // Removed unused handleClearAnnotations function

  // Handle undo
  const handleUndo = () => {
    if (!canUndo) return;
    const newIndex = historyIndex - 1;
    console.log('↩️ Undo:', {
      from: historyIndex,
      to: newIndex,
      annotations: history[newIndex].length
    });
    setHistoryIndex(newIndex);
    setAnnotations(history[newIndex]);
    setHasUnsavedChanges(newIndex > 0);
  };

  // Handle redo
  const handleRedo = () => {
    if (!canRedo) return;
    const newIndex = historyIndex + 1;
    console.log('↪️ Redo:', {
      from: historyIndex,
      to: newIndex,
      annotations: history[newIndex].length
    });
    setHistoryIndex(newIndex);
    setAnnotations(history[newIndex]);
    setHasUnsavedChanges(true);
  };

  // Add to history when annotations change
  const addToHistory = (newAnnotations: AnnotationItem[]) => {
    const newHistory = history.slice(0, historyIndex + 1);
    newHistory.push(newAnnotations);
    setHistory(newHistory);
    setHistoryIndex(newHistory.length - 1);
    setAnnotations(newAnnotations);
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
      const item: AnnotationItem = {
        type: annotationMode,
        id: `st-${Date.now()}-${Math.random()}`,
        sectionKey,
        textContent: selectedText,
        timestamp: new Date().toISOString(),
        startAtom: atomRange.startAtom,
        startOffset: atomRange.startOffset,
        endAtom: atomRange.endAtom,
        endOffset: atomRange.endOffset
      };

      const newAnnotations = [...annotations, item];
      addToHistory(newAnnotations);
      setHasUnsavedChanges(true);

      console.log('✏️ Strikethrough applied:', {
        text: selectedText,
        section: sectionKey,
        atomRange,
        total: newAnnotations.length
      });

      // Clear selection
      selection.removeAllRanges();
    };

    const contentElement = contentRef.current;
    contentElement.addEventListener('mouseup', handleMouseUp);
    
    return () => {
      contentElement.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isStrikeoutMode, annotations, addToHistory]);

  // Track citation occurrences across ALL sections to properly cycle through chunks
  // This needs to be outside renderAtomsForSection so it persists across all sections
  const citationOccurrencesRef = useRef<Record<number, number>>({});

  // Reset citation occurrences when fiscal note DATA changes (not just mode changes)
  useEffect(() => {
    citationOccurrencesRef.current = {};
    console.log('🔄 Reset citation occurrences for new fiscal note');
  }, [fiscalNote.filename, fiscalNote.data]);

  // Render atoms for a section with annotations applied
  // Use useCallback to memoize and prevent unnecessary re-creation
  const renderAtomsForSection = React.useCallback((sectionKey: string): React.ReactNode => {
    const atoms = sectionAtoms[sectionKey];
    if (!atoms || atoms.length === 0) {
      return null;
    }

    // Get annotations for this section
    const sectionAnnotations = annotations.filter(st => st.sectionKey === sectionKey);
    
    if (sectionAnnotations.length > 0) {
      console.log(`📝 Rendering section "${sectionKey}" with ${sectionAnnotations.length} annotations:`, sectionAnnotations);
    }

    // Use the ref to track citation occurrences across all sections
    const citationOccurrences = citationOccurrencesRef.current;

    return atoms.map((atom, atomIndex) => {
      if (atom.type === 'text') {
        // Get segments for this text atom
        const segments = segmentsForAtom(atomIndex, atom.text.length, sectionAnnotations);
        
        return segments.map((seg, segIndex) => {
          // Determine className based on annotation type
          let className = '';
          let textContent = atom.text.slice(seg.start, seg.end);
          
          if (seg.type === 'strikethrough') {
            className = 'line-through text-gray-500 italic';
            // Add brackets for Ramseyer format
            textContent = `[${textContent}]`;
          } else if (seg.type === 'underline') {
            className = 'underline';
          }
          
          return (
            <span
              key={`${atomIndex}-${segIndex}`}
              data-atom-index={atomIndex}
              data-char-start={seg.start}
              data-char-end={seg.end}
              className={className || undefined}
            >
              {textContent}
            </span>
          );
        });
      } else {
        // Ref atom - render citation component
        const annotationType = isRefAtomAnnotated(atomIndex, sectionAnnotations);
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
              className={annotationType === 'strikethrough' ? 'line-through text-gray-500 italic' : (annotationType === 'underline' ? 'underline inline-flex items-center' : 'inline-flex items-center')}
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
        
        // DEBUG: Log citation data for inspection
        console.log('🔍 Citation Debug Info:', {
          citationNumber,
          chunkId,
          refId: atom.refId,
          display: atom.display,
          docInfo,
          chunkDataAvailable: !!chunkData,
          chunkDataLength: chunkData?.length || 0,
          allChunks: chunkData,
          enhancedDocumentMappingKeys: Object.keys(enhancedDocumentMapping),
          chunkTextMapKeys: Object.keys(chunkTextMap)
        });
        
        // Determine which chunk to use
        let chunkInfo = chunkData?.[0];
        
        if (chunkId !== undefined && chunkData) {
          // Citation has explicit chunk ID - find the matching chunk
          const foundChunk = chunkData.find(c => c.chunk_id === chunkId);
          console.log('  🔎 Looking for chunk ID:', chunkId, 'in', chunkData.length, 'chunks');
          console.log('  🔎 Available chunk IDs:', chunkData.map(c => c.chunk_id));
          console.log('  🔎 Found matching chunk:', foundChunk ? `Yes (chunk_id: ${foundChunk.chunk_id})` : 'No, using fallback');
          chunkInfo = foundChunk || chunkData[0];
          console.log('  ✓ Using explicit chunk ID:', chunkId, 'Found:', !!foundChunk, 'Selected chunk_id:', chunkInfo?.chunk_id);
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
          console.log('  ✓ Cycling chunks - occurrence:', occurrenceIndex, 'chunkIndex:', chunkIndex, 'of', chunkData.length, 'chunks, selected chunk_id:', chunkInfo?.chunk_id);
        } else {
          console.warn('  ⚠️ No chunk data available for citation:', citationNumber);
        }
        
        console.log('  → Selected chunkInfo:', {
          chunk_text_preview: chunkInfo?.chunk_text?.substring(0, 100),
          attribution_score: chunkInfo?.attribution_score,
          chunk_id: chunkInfo?.chunk_id,
          document_name: chunkInfo?.document_name,
          sentence: chunkInfo?.sentence
        });
        
        const displayNumber = chunkInfo?.chunk_id 
          ? `${citationNumber}.${chunkInfo.chunk_id}` 
          : citationNumber.toString();
        
        console.log('  📊 Final Display Calculation:', {
          citationNumber,
          'chunkInfo?.chunk_id': chunkInfo?.chunk_id,
          calculatedDisplayNumber: displayNumber,
          formula: `${citationNumber}.${chunkInfo?.chunk_id}`
        });
        
        return (
          <span
            key={atomIndex}
            data-atom-index={atomIndex}
            data-ref="true"
            className={annotationType === 'strikethrough' ? 'line-through text-gray-500 italic' : (annotationType === 'underline' ? 'underline text-blue-600 inline-flex items-center' : 'inline-flex items-center')}
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
  }, [sectionAtoms, annotations, numberCitationMap, chunkTextMap, enhancedDocumentMapping, documentMapping, generateDocumentUrl]);

  // Reset citation counter before rendering content (but not on every state change)
  const renderContent = React.useCallback(() => {
    // Reset citation occurrences at the start of each render cycle
    citationOccurrencesRef.current = {};
    
    return (
      <>
        {renderFiscalNoteContent()}
      </>
    );
  }, [fiscalNote.data, annotations]);

  // Function to render any value (string, object, array)
  const renderValue = (value: any, sectionKey?: string): React.ReactNode => {
    if (value === null || value === undefined) {
      return <span className="text-gray-400 italic">Not specified</span>;
    }

    if (typeof value === 'string') {
      // Use atom-based rendering with annotations
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

  // Main render function for fiscal note content
  const renderFiscalNoteContent = () => (
    <>
      {fiscalNote.data && typeof fiscalNote.data === 'object' ? (
        <div className="divide-y divide-gray-200">
          {Object.entries(fiscalNote.data).map(([key, value]) => (
            <div key={key} className="p-3 lg:p-6" data-section-key={key}>
              <h3 className="text-base lg:text-lg font-semibold text-gray-900 mb-2 lg:mb-4">
                {formatSectionTitle(key)}
              </h3>
              <div className="prose prose-sm lg:prose max-w-none">
                {renderValue(value, key)}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="p-3 lg:p-6">
          <div className="prose prose-sm lg:prose max-w-none">
            {renderValue(fiscalNote.data)}
          </div>
        </div>
      )}
    </>
  );

  return (
    <div className="w-full h-full">
      <div className="max-w-4xl mx-auto p-4 lg:p-8 pb-24 lg:pb-32">
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
      <div className="mb-4 lg:mb-8">
        <div className="flex justify-between items-start">
          <div>
            <h1 className="text-xl lg:text-3xl font-bold text-gray-900 mb-1 lg:mb-2">
              Fiscal Note Analysis
            </h1>
            <h2 className="text-sm lg:text-xl text-gray-600 break-words">
              {fiscalNote.filename}
            </h2>
          </div>
        </div>
      </div>

      {/* Content */}
      {/* Outer container with horizontal scroll for mobile */}
      <div className="overflow-x-auto -mx-4 lg:mx-0 px-4 lg:px-0">
      <div 
        className={`bg-white rounded-lg shadow-sm border transition-all min-w-[320px] ${
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
            <span>Unsaved Annotations - Click Save to persist changes</span>
          </div>
        )}
        {isStrikeoutMode && (
          <div className={`border-b px-4 py-2 text-sm font-medium ${
            annotationMode === 'strikethrough'
              ? 'bg-red-50 border-red-200 text-red-700'
              : 'bg-blue-50 border-blue-200 text-blue-700'
          }`}>
            {annotationMode === 'strikethrough' 
              ? '✏️ Strikethrough Mode - Select text to mark as [deleted]'
              : '✏️ Underline Mode - Select text to mark as new material'
            }
          </div>
        )}
        <div ref={contentRef}>
          {renderContent()}
        </div>
      </div>
      </div>

      {/* Enhanced Numbers Table */}
      {fiscalNote.enhanced_numbers && fiscalNote.enhanced_numbers.count > 0 && (
        <div className="mt-8 bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
          <div className="px-4 py-3 bg-gradient-to-r from-green-50 to-blue-50 border-b border-gray-200">
            <h4 className="text-base font-semibold text-gray-900">
              💰 Enhanced Financial Numbers ({fiscalNote.enhanced_numbers.count})
            </h4>
            <p className="text-xs text-gray-600 mt-1">
              Detailed breakdown of financial amounts, fees, and fines referenced in this fiscal note
            </p>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Amount
                  </th>
                  <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Type
                  </th>
                  <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Summary
                  </th>
                  <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Category
                  </th>
                  <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Unit
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {fiscalNote.enhanced_numbers.numbers.map((item, index) => (
                  <tr key={index} className="hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-3 whitespace-nowrap">
                      <div className="flex items-center">
                        <span className={`text-sm font-semibold ${
                          item.sentiment === 'penalty' ? 'text-red-600' : 
                          item.sentiment === 'neutral' ? 'text-blue-600' : 
                          'text-green-600'
                        }`}>
                          ${item.number.toLocaleString()}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                        item.amount_type === 'fine' ? 'bg-red-100 text-red-800' :
                        item.amount_type === 'fee' ? 'bg-blue-100 text-blue-800' :
                        'bg-gray-100 text-gray-800'
                      }`}>
                        {item.amount_type || 'N/A'}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="text-sm text-gray-900 max-w-md">
                        {item.summary}
                      </div>
                      {item.service_description && (
                        <div className="text-xs text-gray-500 mt-1 italic">
                          {item.service_description}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      <span className="text-sm text-gray-600 capitalize">
                        {item.category || '-'}
                      </span>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      <span className="text-xs text-gray-500">
                        {item.unit?.replace(/_/g, ' ') || '-'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

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

      {/* Floating Edit Toolbar - Hidden on mobile, visible on desktop */}
      <div 
        className={`hidden lg:block fixed z-40 pointer-events-none ${
          position === 'left' ? 'bottom-4 left-50% right-auto' :
          position === 'right' ? 'bottom-4 right-25% left-auto' :
          'bottom-20 left-0 right-0'
        }`}
      >
        <div className={`${
          position === 'center' ? 'max-w-4xl mx-auto px-8 flex justify-center' : ''
        } pointer-events-auto`}>
        <div className="bg-white rounded-full shadow-2xl border-2 border-gray-300 px-2 py-2 flex items-center gap-1 overflow-x-auto scrollbar-hide max-w-full">
          {/* Strikethrough Button */}
          <div className="relative group">
            <button
              onClick={() => {
                // If already in strikethrough mode, turn off edit mode
                // Otherwise, switch to strikethrough mode
                setAnnotationMode(annotationMode === 'strikethrough' ? null : 'strikethrough');
              }}
              className={`p-2 rounded-full transition-all ${
                annotationMode === 'strikethrough'
                  ? 'bg-red-600 text-white hover:bg-red-700'
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
              {annotationMode === 'strikethrough' ? 'Exit Strikethrough Mode' : 'Strikethrough (Delete)'}
            </div>
          </div>

          {/* Underline Button */}
          <div className="relative group">
            <button
              onClick={() => {
                // If already in underline mode, turn off edit mode
                // Otherwise, switch to underline mode
                setAnnotationMode(annotationMode === 'underline' ? null : 'underline');
              }}
              className={`p-2 rounded-full transition-all ${
                annotationMode === 'underline'
                  ? 'bg-blue-600 text-white hover:bg-blue-700'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M6 3v7a6 6 0 0 0 6 6 6 6 0 0 0 6-6V3"></path>
                <line x1="4" y1="21" x2="20" y2="21"></line>
              </svg>
            </button>
            <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 bg-gray-900 text-white text-xs rounded whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
              {annotationMode === 'underline' ? 'Exit Underline Mode' : 'Underline (New)'}
            </div>
          </div>

          {/* Divider */}
          <div className="w-px h-6 bg-gray-300"></div>

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
          <div className="w-px h-6 bg-gray-300"></div>

          {/* Clear My Edits Button */}
          <div className="relative group">
            <button
              onClick={handleDiscardChanges}
              disabled={!hasUnsavedChanges}
              className={`p-2 rounded-full transition-all ${
                hasUnsavedChanges
                  ? 'bg-red-50 text-red-400 hover:bg-red-100 hover:text-red-600'
                  : 'bg-gray-50 text-gray-300 cursor-not-allowed'
              }`}
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"></path>
                <circle cx="12" cy="12" r="10" strokeWidth="2"></circle>
                <line x1="6" y1="6" x2="18" y2="18" strokeWidth="2.5"></line>
              </svg>
            </button>
            <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 bg-gray-900 text-white text-xs rounded whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
              Clear My Edits
            </div>
          </div>

          {/* Save Button with unsaved indicator - Always enabled */}
          <div className="relative group">
            <button
              onClick={handleSaveChanges}
              className="p-2 rounded-full transition-all relative bg-green-600 text-white hover:bg-green-700"
            >
              {/* Unsaved changes indicator */}
              {hasUnsavedChanges && (
                <span className="absolute -top-1 -right-1 w-3 h-3 bg-orange-500 rounded-full border-2 border-white"></span>
              )}
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path>
                <polyline points="17 21 17 13 7 13 7 21"></polyline>
                <polyline points="7 3 7 8 15 8"></polyline>
              </svg>
            </button>
            <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 bg-gray-900 text-white text-xs rounded whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
              {hasUnsavedChanges ? 'Save Changes (Unsaved)' : 'Save Changes'}
            </div>
          </div>

          {/* Clear All Annotations Button (Trash) */}
          <div className="relative group">
            <button
              onClick={async () => {
                if (window.confirm(`Are you sure you want to clear all ${annotations.length} annotations from this fiscal note? This will permanently remove them.`)) {
                  try {
                    console.log('🗑️ Clearing all annotations and saving...');
                    
                    // Clear annotations
                    const newAnnotations: AnnotationItem[] = [];
                    setAnnotations(newAnnotations);
                    setHistory([[], newAnnotations]);
                    setHistoryIndex(1);
                    
                    // Clear localStorage
                    const localKey = `fiscal-note-annotations-${fiscalNote.filename}`;
                    localStorage.removeItem(localKey);
                    
                    // Save immediately to backend
                    const result = await saveStrikethroughs(fiscalNote.filename, newAnnotations, billType, billNumber, year);
                    console.log('✅ Cleared and saved:', result);
                    
                    setHasUnsavedChanges(false);
                    alert('All annotations cleared and saved!');
                  } catch (error) {
                    console.error('❌ Failed to clear annotations:', error);
                    alert(`Failed to clear annotations: ${error instanceof Error ? error.message : 'Unknown error'}`);
                    // Revert on error
                    setAnnotations(fiscalNote.annotations || []);
                  }
                }
              }}
              disabled={annotations.length === 0}
              className={`p-2 rounded-full transition-all ${
                annotations.length > 0
                  ? 'bg-red-100 text-red-600 hover:bg-red-200'
                  : 'bg-gray-50 text-gray-300 cursor-not-allowed'
              }`}
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
              {annotations.length > 0 ? `Clear All (${annotations.length})` : 'Clear All'}
            </div>
          </div>

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
        </div>
        </div>
      </div>
    </div>
  );
};

export default FiscalNoteContent;
