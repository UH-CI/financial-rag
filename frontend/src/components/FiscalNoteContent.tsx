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
  const parseDocumentReferences = (text: string): React.ReactNode => {
    if (!text || typeof text !== 'string') {
      return text;
    }

    // Process [number] citations
    const citationRegex = /\[(\d+)\]/g;
    const textParts: React.ReactNode[] = [];
    let lastIndex = 0;
    let match;

    while ((match = citationRegex.exec(text)) !== null) {
      // Add text before the citation
      if (match.index > lastIndex) {
        textParts.push(text.substring(lastIndex, match.index));
      }

      const citationNumber = parseInt(match[1]);
      
      // Check if this citation has financial data
      const hasFinancialData = numberCitationMap[citationNumber];
      
      if (hasFinancialData) {
        // This is a citation with financial data - create a reference for the specific amount
        const financialCitation = numberCitationMap[citationNumber];
        const numberData = financialCitation.data;
        
        // Use the actual context text from the number data
        const contextText = numberData ? numberData.text : `Amount referenced in ${financialCitation.filename}`;
        
        // Create a reference object similar to DocumentReference
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
          <DocumentReferenceComponent
            key={`financial-${match.index}`}
            reference={financialReference}
          />
        );
      } else {
        // Regular document citation - use DocumentReferenceComponent with document info
        let documentName = 'Unknown Document';
        for (const [docName, docNum] of Object.entries(documentMapping)) {
          if (docNum === citationNumber) {
            documentName = docName;
            break;
          }
        }
        
        // Get chunk text for this document citation
        let chunkText = undefined;
        let sentenceContext = undefined;
        const chunkData = chunkTextMap[citationNumber];
        if (chunkData && chunkData.length > 0) {
          // Use the chunk with the highest attribution score
          const bestChunk = chunkData.reduce((best, current) => 
            current.attribution_score > best.attribution_score ? current : best
          );
          chunkText = bestChunk.chunk_text;
          sentenceContext = bestChunk.sentence;
        }
        
        // Get document type information from enhanced mapping
        const docInfo = enhancedDocumentMapping[citationNumber];
        
        const documentReference: DocumentReference = {
          type: 'document_reference',
          number: citationNumber,
          url: generateDocumentUrl(documentName),
          document_type: 'Document',
          document_name: documentName,
          description: `Reference to ${documentName}`,
          document_category: docInfo?.type || 'Document',
          document_icon: docInfo?.icon || '📄',
          chunk_text: chunkText,
          similarity_score: chunkData && chunkData.length > 0 ? chunkData[0].attribution_score : undefined,
          sentence: sentenceContext
        };
        
        textParts.push(
          <DocumentReferenceComponent
            key={`doc-${match.index}`}
            reference={documentReference}
          />
        );
      }

      lastIndex = match.index + match[0].length;
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
