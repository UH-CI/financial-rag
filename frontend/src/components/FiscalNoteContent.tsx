import React from 'react';
import type { FiscalNoteItem, DocumentReference, NumberCitationMapItem, ChunkTextMapItem, DocumentInfo } from '../types';
import DocumentReferenceComponent from './DocumentReference';

interface FiscalNoteContentProps {
  fiscalNote: FiscalNoteItem;
  documentMapping: Record<string, number>;
  enhancedDocumentMapping: Record<number, DocumentInfo>;
  numbersData: any[]; // Keep for API compatibility but not used in current implementation
  numberCitationMap: Record<number, NumberCitationMapItem>;
  chunkTextMap: Record<number, ChunkTextMapItem[]>;
  onClose?: () => void; // Optional close handler for split view
}

const FiscalNoteContent: React.FC<FiscalNoteContentProps> = ({
  fiscalNote,
  documentMapping,
  enhancedDocumentMapping,
  numberCitationMap,
  chunkTextMap,
  onClose
}) => {
  // Print handler - creates a custom print view
  const handlePrint = () => {
    // Get the fiscal note content element
    const printContent = document.getElementById('fiscal-note-print-content');
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

  // Function to parse [number] citations from text
  // Track citation occurrences to cycle through chunks
  const citationOccurrences = React.useRef<{[key: number]: number}>({});

  const parseDocumentReferences = (text: string): React.ReactNode => {
    if (!text || typeof text !== 'string') {
      return text;
    }

    // Reset citation occurrences for each new text parse
    citationOccurrences.current = {};

    // Process both simple [number] and complex [CHUNK X, NUMBER Y] citations
    const citationRegex = /\[([^\]]+)\]/g;
    const textParts: React.ReactNode[] = [];
    let lastIndex = 0;
    let match;
    
    // Collect all citations first to group consecutive ones
    const citations: Array<{ match: RegExpExecArray; citationNumber: number; index: number }> = [];
    while ((match = citationRegex.exec(text)) !== null) {
      const citationContent = match[1].trim();
      const isSimpleNumber = /^\d+$/.test(citationContent);
      if (isSimpleNumber) {
        citations.push({
          match,
          citationNumber: parseInt(citationContent),
          index: match.index
        });
      } else {
        // Keep complex citations as-is
        citations.push({
          match,
          citationNumber: -1, // Special marker for complex citations
          index: match.index
        });
      }
    }
    
    // Group consecutive citations with the same number
    const groupedCitations: Array<{
      citations: typeof citations;
      startIndex: number;
      endIndex: number;
    }> = [];
    
    for (let i = 0; i < citations.length; i++) {
      const current = citations[i];
      const group = [current];
      let endIndex = current.index + current.match[0].length;
      
      // Check if next citations are consecutive and have the same base number
      while (i + 1 < citations.length) {
        const next = citations[i + 1];
        const textBetween = text.substring(endIndex, next.index);
        
        // Only group if they're adjacent (no text or only whitespace between)
        if (textBetween.trim() === '' && current.citationNumber === next.citationNumber && current.citationNumber !== -1) {
          group.push(next);
          endIndex = next.index + next.match[0].length;
          i++;
        } else {
          break;
        }
      }
      
      groupedCitations.push({
        citations: group,
        startIndex: current.index,
        endIndex
      });
    }
    
    // Process grouped citations
    lastIndex = 0;
    for (const group of groupedCitations) {
      const firstCitation = group.citations[0];
      
      // Add text before the citation group
      if (group.startIndex > lastIndex) {
        textParts.push(text.substring(lastIndex, group.startIndex));
      }
      
      if (firstCitation.citationNumber === -1) {
        // Complex citation - render as-is
        const citationContent = firstCitation.match[1].trim();
        textParts.push(
          <span key={`complex-${group.startIndex}`} className="text-blue-600 font-medium bg-blue-50 px-1 py-0.5 rounded text-sm">
            [{citationContent}]
          </span>
        );
      } else {
        // Simple numbered citation(s)
        const citationNumber = firstCitation.citationNumber;
        
        // Check if this citation has financial data
        const hasFinancialData = numberCitationMap[citationNumber];
        
        if (hasFinancialData) {
          // Financial citation - find the document number for this financial citation
          const financialCitation = numberCitationMap[citationNumber];
          const numberData = financialCitation.data;
          const contextText = numberData ? numberData.text : `Amount referenced in ${financialCitation.filename}`;
          
          // Find the document number for this financial citation's document
          let documentNumber = null;
          for (const [docName, docNum] of Object.entries(documentMapping)) {
            if (docName === financialCitation.document_name) {
              documentNumber = docNum;
              break;
            }
          }
          
          // Display as documentNumber.citationNumber (e.g., 1.19)
          const displayNumber = documentNumber ? `${documentNumber}.${citationNumber}` : citationNumber.toString();
          
          const financialReference: DocumentReference = {
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
          };
          
          textParts.push(
            <span key={`financial-${group.startIndex}`} className="inline-flex items-center">
              <span className="text-green-600">[</span>
              <DocumentReferenceComponent reference={financialReference} />
              <span className="text-green-600">]</span>
            </span>
          );
        } else {
          // Regular document citation
          let documentName = 'Unknown Document';
          for (const [docName, docNum] of Object.entries(documentMapping)) {
            if (docNum === citationNumber) {
              documentName = docName;
              break;
            }
          }
          
          // Get chunk data for this citation
          const chunkData = chunkTextMap[citationNumber];
          
          // Get document type information
          const docInfo = enhancedDocumentMapping[citationNumber];
          
          if (group.citations.length > 1 && chunkData && chunkData.length >= group.citations.length) {
            // Multiple consecutive citations with chunk data - render as grouped citation
            // Deduplicate citations by displayNumber
            const uniqueCitations = new Map<string, {citation: typeof citations[0], chunkInfo: ChunkTextMapItem}>();
            
            group.citations.forEach((citation, idx) => {
              const chunkInfo = chunkData[idx];
              const chunkId = chunkInfo?.chunk_id;
              const displayNumber = chunkId ? `${citationNumber}.${chunkId}` : citationNumber.toString();
              
              // Only add if we haven't seen this displayNumber before
              if (!uniqueCitations.has(displayNumber)) {
                uniqueCitations.set(displayNumber, {citation, chunkInfo});
              }
            });
            
            textParts.push(
              <span key={`group-${group.startIndex}`} className="inline-flex items-center">
                <span className="text-blue-600">[</span>
                {Array.from(uniqueCitations.values()).map(({citation, chunkInfo}, arrayIdx) => {
                  const chunkId = chunkInfo?.chunk_id;
                  const displayNumber = chunkId ? `${citationNumber}.${chunkId}` : citationNumber;
                  
                  const documentReference: DocumentReference = {
                    type: 'document_reference',
                    number: citationNumber,
                    displayNumber: displayNumber.toString(),
                    url: generateDocumentUrl(documentName),
                    document_type: 'Document',
                    document_name: documentName,
                    description: `Reference to ${documentName}`,
                    document_category: docInfo?.type || 'Document',
                    document_icon: docInfo?.icon || '📄',
                    chunk_text: chunkInfo?.chunk_text,
                    similarity_score: chunkInfo?.attribution_score,
                    sentence: chunkInfo?.sentence,
                    chunk_id: chunkId
                  };
                  
                  return (
                    <React.Fragment key={`chunk-${citation.index}`}>
                      <DocumentReferenceComponent reference={documentReference} />
                      {arrayIdx < uniqueCitations.size - 1 && <span className="text-blue-600">, </span>}
                    </React.Fragment>
                  );
                })}
                <span className="text-blue-600">]</span>
              </span>
            );
          } else {
            // Single citation or no chunk data - render normally
            if (!citationOccurrences.current[citationNumber]) {
              citationOccurrences.current[citationNumber] = 0;
            }
            const occurrenceIndex = citationOccurrences.current[citationNumber];
            citationOccurrences.current[citationNumber]++;
            
            let chunkText = undefined;
            let sentenceContext = undefined;
            let chunkId = undefined;
            
            if (chunkData && chunkData.length > 0) {
              const chunkIndex = occurrenceIndex % chunkData.length;
              const assignedChunk = chunkData[chunkIndex];
              chunkText = assignedChunk.chunk_text;
              sentenceContext = assignedChunk.sentence;
              chunkId = assignedChunk.chunk_id;
            }
            
            const displayNumber = chunkId ? `${citationNumber}.${chunkId}` : citationNumber;
            
            const documentReference: DocumentReference = {
              type: 'document_reference',
              number: citationNumber,
              displayNumber: displayNumber.toString(),
              url: generateDocumentUrl(documentName),
              document_type: 'Document',
              document_name: documentName,
              description: `Reference to ${documentName}`,
              document_category: docInfo?.type || 'Document',
              document_icon: docInfo?.icon || '📄',
              chunk_text: chunkText,
              similarity_score: chunkData && chunkData.length > 0 ? chunkData[0].attribution_score : undefined,
              sentence: sentenceContext,
              chunk_id: chunkId
            };
            
            textParts.push(
              <span key={`single-${group.startIndex}`} className="inline-flex items-center">
                <span className="text-blue-600">[</span>
                <DocumentReferenceComponent reference={documentReference} />
                <span className="text-blue-600">]</span>
              </span>
            );
          }
        }
      }
      
      lastIndex = group.endIndex;
    }

    // Add remaining text after last citation
    if (lastIndex < text.length) {
      textParts.push(text.substring(lastIndex));
    }

    return textParts.length > 0 ? textParts : text;
  };

  // Function to render any value (string, object, array)
  const renderValue = (value: any, _key?: string): React.ReactNode => {
    if (value === null || value === undefined) {
      return <span className="text-gray-400 italic">Not specified</span>;
    }

    if (typeof value === 'string') {
      return (
        <div className="text-gray-700 leading-relaxed">
          {parseDocumentReferences(value)}
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
  const renderContent = () => (
    <>
      {fiscalNote.data && typeof fiscalNote.data === 'object' ? (
        <div className="divide-y divide-gray-200">
          {Object.entries(fiscalNote.data).map(([key, value]) => (
            <div key={key} className="p-6">
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
    <div className="max-w-4xl mx-auto p-8">
      {/* Hidden print content container */}
      <div id="fiscal-note-print-content" style={{ display: 'none' }}>
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
          <div className="flex items-center gap-2">
            {onClose && (
              <button
                onClick={onClose}
                className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors shadow-sm"
                title="Close Split View"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="18" y1="6" x2="6" y2="18"></line>
                  <line x1="6" y1="6" x2="18" y2="18"></line>
                </svg>
                Close
              </button>
            )}
            <button
              onClick={handlePrint}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors shadow-sm"
              title="Print Fiscal Note"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="6 9 6 2 18 2 18 9"></polyline>
                <path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"></path>
                <rect x="6" y="14" width="12" height="8"></rect>
              </svg>
              Print
            </button>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
        {renderContent()}
      </div>

      {/* Footer with document mapping info */}
      {documentMapping && Object.keys(documentMapping).length > 0 && (
        <div className="mt-8 p-4 bg-gray-50 rounded-lg pb-32">
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
  );
};

export default FiscalNoteContent;
