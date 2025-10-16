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
}

const FiscalNoteContent: React.FC<FiscalNoteContentProps> = ({
  fiscalNote,
  documentMapping,
  enhancedDocumentMapping,
  numberCitationMap,
  chunkTextMap
}) => {
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
          // Financial citation - render as single citation
          const financialCitation = numberCitationMap[citationNumber];
          const numberData = financialCitation.data;
          const contextText = numberData ? numberData.text : `Amount referenced in ${financialCitation.filename}`;
          
          const financialReference: DocumentReference = {
            type: 'document_reference',
            number: citationNumber,
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

  return (
    <div className="max-w-4xl mx-auto p-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">
          Fiscal Note Analysis
        </h1>
        <h2 className="text-xl text-gray-600">
          {fiscalNote.filename}
        </h2>
      </div>

      {/* Content */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
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
