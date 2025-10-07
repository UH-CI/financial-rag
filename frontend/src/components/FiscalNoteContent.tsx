import React from 'react';
import type { FiscalNoteItem, DocumentReference } from '../types';
import DocumentReferenceComponent from './DocumentReference';

interface FiscalNoteContentProps {
  fiscalNote: FiscalNoteItem;
  documentMapping: Record<string, number>;
}

const FiscalNoteContent: React.FC<FiscalNoteContentProps> = ({
  fiscalNote,
  documentMapping
}) => {
  // Function to parse document references from text
  const parseDocumentReferences = (text: string): React.ReactNode => {
    if (!text || typeof text !== 'string') {
      return text;
    }

    // Split by the DOCREF markers (with single braces)
    const parts = text.split(/\{DOCREF:([^}]+)\}/);
    const result: React.ReactNode[] = [];

    for (let i = 0; i < parts.length; i++) {
      if (i % 2 === 0) {
        // Regular text
        if (parts[i]) {
          result.push(parts[i]);
        }
      } else {
        // Document reference pipe-separated format: number|url|type|name|description|chunk_text|similarity_score
        try {
          const refParts = parts[i].split('|');
          if (refParts.length >= 5) {
            const referenceData: DocumentReference = {
              type: 'document_reference',
              number: parseInt(refParts[0]),
              url: refParts[1],
              document_type: refParts[2].replace(/&#124;/g, '|'), // Unescape pipes
              document_name: refParts[3].replace(/&#124;/g, '|'), // Unescape pipes
              description: refParts[4].replace(/&#124;/g, '|'), // Unescape pipes
              chunk_text: refParts.length > 5 ? refParts[5].replace(/&#124;/g, '|') : undefined,
              similarity_score: refParts.length > 6 ? parseFloat(refParts[6]) : undefined
            };
            result.push(
              <DocumentReferenceComponent
                key={`ref-${i}`}
                reference={referenceData}
              />
            );
          } else {
            console.error('Invalid document reference format:', parts[i]);
            result.push(`[Invalid reference]`);
          }
        } catch (error) {
          console.error('Failed to parse document reference:', error);
          console.error('Raw data:', parts[i]);
          result.push(`[Error parsing reference]`);
        }
      }
    }

    return result.length > 0 ? result : text;
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
