import React, { useState, useEffect } from 'react';
import type { FiscalNoteData } from '../types';
import { getFiscalNoteData } from '../services/api';
import TimelineNavigation from './TimelineNavigation';
import FiscalNoteContent from './FiscalNoteContent';

interface FiscalNoteViewerProps {
  billType: 'HB' | 'SB';
  billNumber: string;
  year?: string;
}

const FiscalNoteViewer: React.FC<FiscalNoteViewerProps> = ({
  billType,
  billNumber,
  year = '2025'
}) => {
  const [fiscalNoteData, setFiscalNoteData] = useState<FiscalNoteData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedNoteIndex, setSelectedNoteIndex] = useState(0);

  useEffect(() => {
    const loadFiscalNoteData = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await getFiscalNoteData(billType, billNumber, year);
        setFiscalNoteData(data);
        
        if (data.status === 'generating') {
          setError(data.message || 'Fiscal note generation in progress');
        }
      } catch (err: any) {
        setError(err.message || 'Failed to load fiscal note data');
      } finally {
        setLoading(false);
      }
    };

    loadFiscalNoteData();
  }, [billType, billNumber, year]);

  const handleTimelineItemClick = (filename: string) => {
    if (fiscalNoteData) {
      const index = fiscalNoteData.fiscal_notes.findIndex(note => note.filename === filename);
      if (index !== -1) {
        setSelectedNoteIndex(index);
        // Scroll the selected tab into view if there are multiple notes
        if (fiscalNoteData.fiscal_notes.length > 1) {
          setTimeout(() => {
            const tabElement = document.querySelector(`[data-tab-index="${index}"]`);
            if (tabElement) {
              tabElement.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }
          }, 100);
        }
      }
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        <span className="ml-2">Loading fiscal note...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="text-red-600 mb-2">⚠️ Error</div>
          <div className="text-gray-600">{error}</div>
        </div>
      </div>
    );
  }

  if (!fiscalNoteData || fiscalNoteData.fiscal_notes.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="text-gray-400 mb-2">📄</div>
          <div className="text-gray-600">No fiscal note data available</div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col lg:flex-row h-full w-full bg-gray-50">
      {/* Left Sidebar - Timeline and Document References */}
      <div className="w-full lg:w-96 lg:flex-shrink-0 bg-white shadow-lg border-b lg:border-b-0 lg:border-r border-gray-200 flex flex-col max-h-64 lg:max-h-screen lg:sticky lg:top-0 overflow-y-auto">
        <div className="p-6 border-b border-gray-200">
          <h2 className="text-xl font-bold text-gray-900">
            {billType} {billNumber} ({year})
          </h2>
          <p className="text-sm text-gray-600 mt-1">Fiscal Note Analysis</p>
        </div>

        {/* Document Reference Key */}
        {fiscalNoteData.document_mapping && Object.keys(fiscalNoteData.document_mapping).length > 0 && (
          <div className="p-4 border-b border-gray-200">
            <h3 className="text-sm font-semibold text-gray-700 mb-3">Document References</h3>
            <div className="space-y-2 max-h-48 overflow-y-auto">
              {Object.entries(fiscalNoteData.document_mapping).map(([docName, docNumber]) => {
                // Check if this document was used in the currently selected fiscal note
                const selectedFiscalNote = fiscalNoteData.fiscal_notes[selectedNoteIndex];
                const isUsedInSelectedNote = selectedFiscalNote?.new_documents_processed?.includes(docName) || false;
                
                return (
                  <div key={docName} className="flex items-start space-x-2 text-xs">
                    <span className={`font-mono min-w-[24px] ${isUsedInSelectedNote ? 'text-blue-700 font-bold' : 'text-blue-600'}`}>
                      [{docNumber}]
                    </span>
                    <span className={`leading-tight ${isUsedInSelectedNote ? 'text-gray-900 font-semibold bg-blue-50 px-1 py-0.5 rounded' : 'text-gray-600'}`}>
                      {docName}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Timeline Navigation */}
        <div className="flex-1 overflow-y-auto">
          <TimelineNavigation
            timeline={fiscalNoteData.timeline}
            fiscalNotes={fiscalNoteData.fiscal_notes}
            selectedNoteIndex={selectedNoteIndex}
            onTimelineItemClick={handleTimelineItemClick}
          />
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 min-w-0 w-full overflow-y-auto">
        {fiscalNoteData.fiscal_notes.length > 1 ? (
          <div className="h-full">
            {/* Tabs for multiple fiscal notes - Sticky at top */}
            <div className="bg-white border-b border-gray-200 px-4 lg:px-6 py-3 sticky top-0 z-20 shadow-sm">
              <div className="flex space-x-2 lg:space-x-4 overflow-x-auto">
                {fiscalNoteData.fiscal_notes.map((note, index) => (
                  <button
                    key={note.filename}
                    data-tab-index={index}
                    onClick={() => setSelectedNoteIndex(index)}
                    className={`px-3 lg:px-4 py-2 text-xs lg:text-sm font-medium rounded-lg whitespace-nowrap transition-colors ${
                      selectedNoteIndex === index
                        ? 'bg-blue-100 text-blue-700 border border-blue-200'
                        : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                    }`}
                  >
                    {note.filename}
                  </button>
                ))}
              </div>
            </div>
            
            {/* Content */}
            <FiscalNoteContent
              fiscalNote={fiscalNoteData.fiscal_notes[selectedNoteIndex]}
              documentMapping={fiscalNoteData.document_mapping}
              enhancedDocumentMapping={fiscalNoteData.enhanced_document_mapping || {}}
              numbersData={fiscalNoteData.numbers_data || []}
              numberCitationMap={fiscalNoteData.number_citation_map || {}}
              chunkTextMap={fiscalNoteData.chunk_text_map || {}}
            />
          </div>
        ) : (
          <FiscalNoteContent
            fiscalNote={fiscalNoteData.fiscal_notes[selectedNoteIndex]}
            documentMapping={fiscalNoteData.document_mapping}
            enhancedDocumentMapping={fiscalNoteData.enhanced_document_mapping || {}}
            numbersData={fiscalNoteData.numbers_data || []}
            numberCitationMap={fiscalNoteData.number_citation_map || {}}
            chunkTextMap={fiscalNoteData.chunk_text_map || {}}
          />
        )}
      </div>
    </div>
  );
};

export default FiscalNoteViewer;
