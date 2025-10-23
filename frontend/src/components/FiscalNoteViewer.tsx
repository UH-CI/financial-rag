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
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  
  // Split view state - store per bill
  const [splitViewState, setSplitViewState] = useState<Record<string, {
    enabled: boolean;
    leftIndex: number;
    rightIndex: number;
  }>>({});
  
  const billKey = `${billType}${billNumber}_${year}`;
  const currentSplitView = splitViewState[billKey] || { enabled: false, leftIndex: 0, rightIndex: 1 };

  // Enable split view
  const enableSplitView = () => {
    setSplitViewState(prev => ({
      ...prev,
      [billKey]: {
        enabled: true,
        leftIndex: selectedNoteIndex,
        rightIndex: selectedNoteIndex === 0 ? 1 : 0
      }
    }));
  };
  
  // Disable split view
  const disableSplitView = () => {
    setSplitViewState(prev => ({
      ...prev,
      [billKey]: {
        ...prev[billKey],
        enabled: false
      }
    }));
  };
  
  // Update split view indices
  const updateSplitViewIndex = (side: 'left' | 'right', index: number) => {
    setSplitViewState(prev => ({
      ...prev,
      [billKey]: {
        ...prev[billKey],
        enabled: true,
        [side === 'left' ? 'leftIndex' : 'rightIndex']: index
      }
    }));
  };

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
    // Find the index of the fiscal note with this filename
    const index = fiscalNoteData?.fiscal_notes.findIndex(note => note.filename === filename) ?? 0;
    
    if (currentSplitView.enabled) {
      // In split view, update the left panel
      updateSplitViewIndex('left', index);
    } else {
      setSelectedNoteIndex(index);
      
      // Scroll to the selected tab if it exists
      if (fiscalNoteData && fiscalNoteData.fiscal_notes.length > 1) {
        setTimeout(() => {
          const tabElement = document.querySelector(`[data-tab-index="${index}"]`);
          if (tabElement) {
            tabElement.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
          }
        }, 100);
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
      {/* Sidebar Container with relative positioning to allow button overflow */}
      <div className="relative lg:flex-shrink-0">
        {/* Collapse/Expand Button - positioned outside the sidebar */}
        <button
          onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
          className="hidden lg:flex absolute left-full top-1/2 -translate-y-1/2 -ml-3 z-50 w-8 h-8 items-center justify-center bg-blue-600 text-white rounded-full shadow-lg hover:bg-blue-700 transition-colors"
          title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          <svg 
            xmlns="http://www.w3.org/2000/svg" 
            className={`h-5 w-5 transition-transform duration-300 ${sidebarCollapsed ? 'rotate-180' : ''}`}
            viewBox="0 0 24 24" 
            fill="none" 
            stroke="currentColor" 
            strokeWidth="2" 
            strokeLinecap="round" 
            strokeLinejoin="round"
          >
            <polyline points="15 18 9 12 15 6"></polyline>
          </svg>
        </button>

        {/* Left Sidebar - Timeline and Document References */}
        <div className={`transition-all duration-300 bg-white shadow-lg border-b lg:border-b-0 lg:border-r border-gray-200 flex flex-col lg:max-h-screen lg:sticky lg:top-0 overflow-y-auto ${
          sidebarCollapsed 
            ? 'w-0 lg:w-0 border-0' 
            : 'w-full lg:w-96 max-h-64'
        }`}>
          <div className={`p-6 border-b border-gray-200 ${sidebarCollapsed ? 'hidden' : ''}`}>
          <h2 className="text-xl font-bold text-gray-900">
            {billType} {billNumber} ({year})
          </h2>
          <p className="text-sm text-gray-600 mt-1">Fiscal Note Analysis</p>
        </div>

          {/* Document Reference Key */}
          {!sidebarCollapsed && fiscalNoteData.document_mapping && Object.keys(fiscalNoteData.document_mapping).length > 0 && (
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
          <div className={`flex-1 overflow-y-auto ${sidebarCollapsed ? 'hidden' : ''}`}>
            <TimelineNavigation
              timeline={fiscalNoteData.timeline}
              fiscalNotes={fiscalNoteData.fiscal_notes}
              selectedNoteIndex={selectedNoteIndex}
              onTimelineItemClick={handleTimelineItemClick}
            />
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 min-w-0 w-full overflow-y-auto relative">

        {currentSplitView.enabled ? (
          /* Split View - Two fiscal notes side by side */
          <div className="flex h-full">
            {/* Left Panel */}
            <div className="flex-1 border-r border-gray-300 overflow-y-auto">
              <div className="sticky top-0 z-20 bg-white border-b border-gray-200 p-3 shadow-sm">
                <select
                  value={currentSplitView.leftIndex}
                  onChange={(e) => updateSplitViewIndex('left', parseInt(e.target.value))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {fiscalNoteData.fiscal_notes.map((note, index) => (
                    <option key={index} value={index}>
                      {note.filename}
                    </option>
                  ))}
                </select>
              </div>
              <FiscalNoteContent
                fiscalNote={fiscalNoteData.fiscal_notes[currentSplitView.leftIndex]}
                documentMapping={fiscalNoteData.document_mapping}
                enhancedDocumentMapping={fiscalNoteData.enhanced_document_mapping || {}}
                numbersData={fiscalNoteData.numbers_data || []}
                numberCitationMap={fiscalNoteData.number_citation_map || {}}
                chunkTextMap={fiscalNoteData.chunk_text_map || {}}
              />
            </div>

            {/* Right Panel */}
            <div className="flex-1 overflow-y-auto">
              <div className="sticky top-0 z-20 bg-white border-b border-gray-200 p-3 shadow-sm">
                <select
                  value={currentSplitView.rightIndex}
                  onChange={(e) => updateSplitViewIndex('right', parseInt(e.target.value))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {fiscalNoteData.fiscal_notes.map((note, index) => (
                    <option key={index} value={index}>
                      {note.filename}
                    </option>
                  ))}
                </select>
              </div>
              <FiscalNoteContent
                fiscalNote={fiscalNoteData.fiscal_notes[currentSplitView.rightIndex]}
                documentMapping={fiscalNoteData.document_mapping}
                enhancedDocumentMapping={fiscalNoteData.enhanced_document_mapping || {}}
                numbersData={fiscalNoteData.numbers_data || []}
                numberCitationMap={fiscalNoteData.number_citation_map || {}}
                chunkTextMap={fiscalNoteData.chunk_text_map || {}}
                onClose={disableSplitView}
              />
            </div>
          </div>
        ) : (
          /* Single View */
          fiscalNoteData.fiscal_notes.length > 1 ? (
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
              
              {/* Content with floating Add button */}
              <div className="overflow-y-auto h-full relative">
                <FiscalNoteContent
                  fiscalNote={fiscalNoteData.fiscal_notes[selectedNoteIndex]}
                  documentMapping={fiscalNoteData.document_mapping}
                  enhancedDocumentMapping={fiscalNoteData.enhanced_document_mapping || {}}
                  numbersData={fiscalNoteData.numbers_data || []}
                  numberCitationMap={fiscalNoteData.number_citation_map || {}}
                  chunkTextMap={fiscalNoteData.chunk_text_map || {}}
                />
                
                {/* Add Split View Button - Floating button centered between content and right edge */}
                <button
                  onClick={enableSplitView}
                  className="fixed opacity-75 top-1/2 -translate-y-1/2 flex flex-col items-center justify-center gap-2 w-32 h-32 bg-gray-200 hover:bg-gray-300 text-gray-700 rounded-lg transition-colors shadow-lg z-20"
                  title="Compare fiscal notes side by side"
                  style={{ left: 'calc(50% + 32rem + ((100vw - 50% - 32rem) / 2) - 2rem)' }}
                >
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="12" y1="5" x2="12" y2="19"></line>
                    <line x1="5" y1="12" x2="19" y2="12"></line>
                  </svg>
                  <span className="text-xs font-medium">Add Fiscal Note</span>
                </button>
              </div>
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
          )
        )}
      </div>
    </div>
  );
};

export default FiscalNoteViewer;
