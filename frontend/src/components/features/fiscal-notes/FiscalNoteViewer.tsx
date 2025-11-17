import React, { useState, useEffect } from 'react';
import type { FiscalNoteData } from '../../../types';
import { getFiscalNoteData } from '../../../services/api';
import TimelineNavigation from '../../ui/Navigation/TimelineNavigation';
import FiscalNoteContent from './FiscalNoteContent/FiscalNoteContent';
import ErrorBoundary from '../../ui/ErrorBoundary/ErrorBoundary';
import NumberTrackingSection from '../numbers/NumberTrackingSection';

interface FiscalNoteViewerProps {
  billType: 'HB' | 'SB';
  billNumber: string;
  year?: string;
  availableBills?: { name: string; status: string }[];
  onBillChange?: (fileName: string) => void;
}

const FiscalNoteViewer: React.FC<FiscalNoteViewerProps> = ({
  billType,
  billNumber,
  year = '2025',
  availableBills = [],
  onBillChange
}) => {
  const [fiscalNoteData, setFiscalNoteData] = useState<FiscalNoteData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedNoteIndex, setSelectedNoteIndex] = useState(0);
  
  // Load sidebar collapsed state from localStorage
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    const saved = localStorage.getItem('fiscal-note-sidebar-collapsed');
    return saved === 'true';
  });
  
  const [mobileReferencesExpanded, setMobileReferencesExpanded] = useState(false);
  
  // Split view state - store per bill and persist to localStorage
  const [splitViewState, setSplitViewState] = useState<Record<string, {
    enabled: boolean;
    leftIndex: number;
    rightIndex: number;
  }>>(() => {
    const saved = localStorage.getItem('fiscal-note-split-view-state');
    return saved ? JSON.parse(saved) : {};
  });
  
  const billKey = `${billType}${billNumber}_${year}`;
  const currentSplitView = splitViewState[billKey] || { enabled: false, leftIndex: 0, rightIndex: 1 };

  // Extract loadFiscalNoteData so it can be called from save callback and split view close
  const loadFiscalNoteData = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getFiscalNoteData(billType, billNumber, year);
      setFiscalNoteData(data);
      console.log(data)
      // Debug: Log tracking data
      console.log('📊 Fiscal Note Data Loadasdasdasdased:', {
        has_tracking: data.has_tracking,
        chronological_tracking: data.chronological_tracking ? 'Present' : 'Missing',
        fiscal_notes_count: data.fiscal_notes?.length,
        first_note_has_tracking: data.fiscal_notes?.[0]?.number_tracking ? 'Yes' : 'No'
      });
      
      // Debug: Log each fiscal note's tracking status
      data.fiscal_notes?.forEach((note, idx) => {
        console.log(`📋 Fiscal Note ${idx}: ${note.filename}`, {
          has_number_tracking: !!note.number_tracking,
          segment_id: note.number_tracking?.segment_id,
          numbers_count: note.number_tracking?.numbers?.length || 0
        });
      });
      
      // Reset split view indices if they're out of bounds for the new data
      if (data.fiscal_notes && data.fiscal_notes.length > 0) {
        const maxIndex = data.fiscal_notes.length - 1;
        setSplitViewState(prev => {
          const currentState = prev[billKey];
          if (currentState && (currentState.leftIndex > maxIndex || currentState.rightIndex > maxIndex)) {
            return {
              ...prev,
              [billKey]: {
                enabled: false,
                leftIndex: 0,
                rightIndex: Math.min(1, maxIndex)
              }
            };
          }
          return prev;
        });
      }
      
      if (data.status === 'generating') {
        setError(data.message || 'Fiscal note generation in progress');
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load fiscal note data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Reset index to 0 when loading new bill to prevent out of bounds errors
    setSelectedNoteIndex(0);
    loadFiscalNoteData();
  }, [billType, billNumber, year]);
  
  // Persist split view state to localStorage whenever it changes
  useEffect(() => {
    localStorage.setItem('fiscal-note-split-view-state', JSON.stringify(splitViewState));
  }, [splitViewState]);
  
  // Callback to refresh data after save
  const handleSaveSuccess = () => {
    console.log('🔄 Refreshing fiscal note data after save...');
    loadFiscalNoteData();
  };

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
    // Refresh data when closing split view to ensure we have latest changes
    console.log('🔄 Refreshing data after closing split view...');
    loadFiscalNoteData();
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

  // Safety check: Ensure selectedNoteIndex is within bounds
  const safeSelectedIndex = Math.min(selectedNoteIndex, fiscalNoteData.fiscal_notes.length - 1);
  const safeSplitViewLeftIndex = Math.min(currentSplitView.leftIndex, fiscalNoteData.fiscal_notes.length - 1);
  const safeSplitViewRightIndex = Math.min(currentSplitView.rightIndex, fiscalNoteData.fiscal_notes.length - 1);

  return (
    <div className="flex flex-col lg:flex-row h-full w-full bg-gray-50">
      {/* Mobile Top Dropdowns - Only visible on mobile */}
      <div className="lg:hidden bg-white border-b border-gray-200 p-3 space-y-2 sticky top-0 z-30">
        {/* Bill Selection Dropdown */}
        {availableBills.length > 0 && onBillChange && (
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              Select Bill
            </label>
            <select
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
              value={`${billType}_${billNumber}_${year}`}
              onChange={(e) => onBillChange(e.target.value)}
            >
              {availableBills.map((bill) => (
                <option key={bill.name} value={bill.name}>
                  {bill.name.replace(/_/g, ' ')}
                </option>
              ))}
            </select>
          </div>
        )}
        
        {/* Fiscal Note Selection Dropdown */}
        {fiscalNoteData.fiscal_notes.length > 1 && (
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              Select Fiscal Note Version
            </label>
            <select
              value={safeSelectedIndex}
              onChange={(e) => setSelectedNoteIndex(parseInt(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
            >
              {fiscalNoteData.fiscal_notes.map((note, index) => (
                <option key={index} value={index}>
                  {note.filename}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* Desktop Sidebar - Hidden on mobile */}
      <div className="hidden lg:block relative lg:flex-shrink-0">
        {/* Desktop Collapse/Expand Button */}
        <button
          onClick={() => {
            const newState = !sidebarCollapsed;
            setSidebarCollapsed(newState);
            localStorage.setItem('fiscal-note-sidebar-collapsed', String(newState));
          }}
          className="absolute left-full top-1/2 -translate-y-1/2 -ml-3 z-50 w-8 h-8 flex items-center justify-center bg-blue-600 text-white rounded-full shadow-lg hover:bg-blue-700 transition-colors"
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

        {/* Desktop Sidebar */}
        <div className={`transition-all duration-300 bg-white shadow-lg border-gray-200 flex flex-col overflow-y-auto border-r max-h-screen sticky top-0 mb-2 ${
          sidebarCollapsed ? 'w-0 border-0' : 'w-96'
        }`}>
          <div className={`p-6 border-b border-gray-200 ${sidebarCollapsed ? 'hidden' : ''}`}>
            <h2 className="text-xl font-bold text-gray-900">
              {billType} {billNumber} ({year})
            </h2>
            <p className="text-sm text-gray-600 mt-1 mb-10">Fiscal Note Analysis</p>
          </div>

          {/* Document References */}
          {!sidebarCollapsed && fiscalNoteData.document_mapping && Object.keys(fiscalNoteData.document_mapping).length > 0 && (
          <div className="p-4 border-b border-gray-200">
            <h3 className="text-sm font-semibold text-gray-700 mb-3">Document References</h3>
            <div className="space-y-2 max-h-48 overflow-y-auto">
              {Object.entries(fiscalNoteData.document_mapping).map(([docName, docNumber]) => {
                const selectedFiscalNote = fiscalNoteData.fiscal_notes[safeSelectedIndex];
                const isUsedInSelectedNote = selectedFiscalNote?.new_documents_processed?.includes(docName) || false;
                
                return (
                  <div key={docName} className="flex items-start space-x-2 text-xs">
                    <span className={`font-mono min-w-[24px] ${isUsedInSelectedNote ? 'text-blue-700 font-bold' : 'text-blue-600'}`}>
                      [{docNumber}]
                    </span>
                    <span className={`leading-tight break-words ${isUsedInSelectedNote ? 'text-gray-900 font-semibold bg-blue-50 px-1 py-0.5 rounded' : 'text-gray-600'}`}>
                      {docName}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

          {/* Timeline Navigation */}
          <div className={`flex-1 overflow-y-auto scroll-smooth mobile-scroll ${sidebarCollapsed ? 'hidden' : ''}`}>
            <TimelineNavigation
              timeline={fiscalNoteData.timeline}
              fiscalNotes={fiscalNoteData.fiscal_notes}
              selectedNoteIndex={safeSelectedIndex}
              onTimelineItemClick={handleTimelineItemClick}
            />
          </div>
        </div>
      </div>

      {/* Main Content Area - Full width on mobile */}
      <div className="flex-1 min-w-0 w-full relative pb-20 lg:pb-0 flex flex-col overflow-hidden">

        {currentSplitView.enabled ? (
          /* Split View - Two fiscal notes side by side on desktop, single view on mobile */
          <div className="flex flex-col lg:flex-row h-full">
            {/* Left Panel */}
            <div className="flex-1 border-b lg:border-b-0 lg:border-r border-gray-300 relative h-full flex flex-col min-h-[50vh] lg:min-h-0">
              <div className="z-20 bg-white border-b border-gray-200 p-2 lg:p-3 shadow-sm flex-shrink-0">
                <select
                  value={safeSplitViewLeftIndex}
                  onChange={(e) => updateSplitViewIndex('left', parseInt(e.target.value))}
                  className="w-full px-2 lg:px-3 py-1.5 lg:py-2 border border-gray-300 rounded-lg text-xs lg:text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {fiscalNoteData.fiscal_notes.map((note, index) => (
                    <option key={index} value={index}>
                      {note.filename}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex-1 overflow-y-auto scroll-smooth mobile-scroll relative">
                <ErrorBoundary>
                  <FiscalNoteContent
                    key={fiscalNoteData.fiscal_notes[safeSplitViewLeftIndex].filename}
                    fiscalNote={fiscalNoteData.fiscal_notes[safeSplitViewLeftIndex]}
                    documentMapping={fiscalNoteData.document_mapping}
                    enhancedDocumentMapping={fiscalNoteData.enhanced_document_mapping || {}}
                    numbersData={fiscalNoteData.numbers_data || []}
                    numberCitationMap={fiscalNoteData.number_citation_map || {}}
                    chunkTextMap={fiscalNoteData.chunk_text_map || {}}
                    billType={billType}
                    billNumber={billNumber}
                    year={year}
                    onSaveSuccess={handleSaveSuccess}
                    position="left"
                  />
                </ErrorBoundary>
              </div>
            </div>

            {/* Right Panel - Hidden on mobile, visible on desktop */}
            <div className="hidden lg:flex flex-1 relative h-full flex-col min-h-[50vh] lg:min-h-0">
              <div className="z-20 bg-white border-b border-gray-200 p-2 lg:p-3 shadow-sm flex-shrink-0">
                <select
                  value={safeSplitViewRightIndex}
                  onChange={(e) => updateSplitViewIndex('right', parseInt(e.target.value))}
                  className="w-full px-2 lg:px-3 py-1.5 lg:py-2 border border-gray-300 rounded-lg text-xs lg:text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {fiscalNoteData.fiscal_notes.map((note, index) => (
                    <option key={index} value={index}>
                      {note.filename}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex-1 overflow-y-auto scroll-smooth mobile-scroll relative">
                <ErrorBoundary>
                  <FiscalNoteContent
                    key={fiscalNoteData.fiscal_notes[safeSplitViewRightIndex].filename}
                    fiscalNote={fiscalNoteData.fiscal_notes[safeSplitViewRightIndex]}
                    documentMapping={fiscalNoteData.document_mapping}
                    enhancedDocumentMapping={fiscalNoteData.enhanced_document_mapping || {}}
                    numbersData={fiscalNoteData.numbers_data || []}
                    numberCitationMap={fiscalNoteData.number_citation_map || {}}
                    chunkTextMap={fiscalNoteData.chunk_text_map || {}}
                    billType={billType}
                    billNumber={billNumber}
                    year={year}
                    onSaveSuccess={handleSaveSuccess}
                    onClose={disableSplitView}
                    position="right"
                  />
                </ErrorBoundary>
              </div>
            </div>
          </div>
        ) : (
          /* Single View */
          fiscalNoteData.fiscal_notes.length > 1 ? (
            <div className="h-full flex flex-col overflow-hidden">
              {/* Tabs for multiple fiscal notes - Desktop only, hidden on mobile */}
              <div className="hidden lg:block bg-white border-b border-gray-200 px-6 py-3 flex-shrink-0 z-20 shadow-sm">
                <div className="flex space-x-4 overflow-x-auto scrollbar-hide">
                  {fiscalNoteData.fiscal_notes.map((note, index) => (
                    <button
                      key={note.filename}
                      data-tab-index={index}
                      onClick={() => setSelectedNoteIndex(index)}
                      className={`px-2 lg:px-4 py-1.5 lg:py-2 text-[10px] lg:text-sm font-medium rounded-lg whitespace-nowrap transition-colors flex-shrink-0 ${
                        safeSelectedIndex === index
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
              <div className="flex-1 overflow-y-auto overflow-x-hidden scroll-smooth mobile-scroll">
                <ErrorBoundary>
                  <FiscalNoteContent
                    key={fiscalNoteData.fiscal_notes[safeSelectedIndex].filename}
                    fiscalNote={fiscalNoteData.fiscal_notes[safeSelectedIndex]}
                    documentMapping={fiscalNoteData.document_mapping}
                    enhancedDocumentMapping={fiscalNoteData.enhanced_document_mapping || {}}
                    numbersData={fiscalNoteData.numbers_data || []}
                    numberCitationMap={fiscalNoteData.number_citation_map || {}}
                    chunkTextMap={fiscalNoteData.chunk_text_map || {}}
                    billType={billType}
                    billNumber={billNumber}
                    year={year}
                    onSaveSuccess={handleSaveSuccess}
                    onAddSplitView={enableSplitView}
                  />
                  
                  {/* Number Tracking Section - Only show if tracking is available */}
                  {fiscalNoteData.has_tracking && (
                    <div className="max-w-4xl mx-auto px-4 lg:px-8">
                      <NumberTrackingSection
                        tracking={fiscalNoteData.fiscal_notes[safeSelectedIndex].number_tracking}
                        fiscalNoteName={fiscalNoteData.fiscal_notes[safeSelectedIndex].filename}
                        allTrackingData={fiscalNoteData.chronological_tracking}
                        documentMapping={fiscalNoteData.document_mapping}
                      />
                    </div>
                  )}
                </ErrorBoundary>
              </div>
            </div>
          ) : (
            <div className="flex-1 overflow-y-auto overflow-x-hidden scroll-smooth mobile-scroll">
              <ErrorBoundary>
                <FiscalNoteContent
                  key={fiscalNoteData.fiscal_notes[safeSelectedIndex].filename}
                  fiscalNote={fiscalNoteData.fiscal_notes[safeSelectedIndex]}
                  documentMapping={fiscalNoteData.document_mapping}
                  enhancedDocumentMapping={fiscalNoteData.enhanced_document_mapping || {}}
                  numbersData={fiscalNoteData.numbers_data || []}
                  numberCitationMap={fiscalNoteData.number_citation_map || {}}
                  chunkTextMap={fiscalNoteData.chunk_text_map || {}}
                  billType={billType}
                  billNumber={billNumber}
                  year={year}
                  onSaveSuccess={handleSaveSuccess}
                />
                
                {/* Number Tracking Section - Only show if tracking is available */}
                {fiscalNoteData.has_tracking && (
                  <div className="max-w-4xl mx-auto px-4 lg:px-8">
                    <NumberTrackingSection
                      tracking={fiscalNoteData.fiscal_notes[safeSelectedIndex].number_tracking}
                      fiscalNoteName={fiscalNoteData.fiscal_notes[safeSelectedIndex].filename}
                      allTrackingData={fiscalNoteData.chronological_tracking}
                      documentMapping={fiscalNoteData.document_mapping}
                    />
                  </div>
                )}
              </ErrorBoundary>
            </div>
          )
        )}

        {/* Mobile Document References - Expandable panel at bottom, only on mobile */}
        {fiscalNoteData.document_mapping && Object.keys(fiscalNoteData.document_mapping).length > 0 && (
          <>
            {/* Expandable References Panel */}
            <div 
              className={`lg:hidden fixed bottom-0 left-0 right-0 bg-white border-t-2 border-gray-300 shadow-2xl transition-transform duration-300 ease-in-out z-40 ${
                mobileReferencesExpanded ? 'translate-y-0' : 'translate-y-full'
              }`}
              style={{ maxHeight: '70vh' }}
            >
              <div className="flex flex-col h-full">
                {/* Header with close button */}
                <div className="flex items-center justify-between p-4 border-b border-gray-200 bg-gray-50">
                  <h3 className="text-sm font-semibold text-gray-900">Document References</h3>
                  <button
                    onClick={() => setMobileReferencesExpanded(false)}
                    className="p-1 rounded-full hover:bg-gray-200 transition-colors"
                  >
                    <svg className="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
                
                {/* References list */}
                <div className="flex-1 overflow-y-auto scroll-smooth mobile-scroll p-4 space-y-2">
                  {Object.entries(fiscalNoteData.document_mapping).map(([docName, docNumber]) => {
                    const selectedFiscalNote = fiscalNoteData.fiscal_notes[safeSelectedIndex];
                    const isUsedInSelectedNote = selectedFiscalNote?.new_documents_processed?.includes(docName) || false;
                    
                    return (
                      <div key={docName} className="flex items-start space-x-2 text-xs p-2 rounded hover:bg-gray-50">
                        <span className={`font-mono min-w-[24px] flex-shrink-0 ${isUsedInSelectedNote ? 'text-blue-700 font-bold' : 'text-blue-600'}`}>
                          [{docNumber}]
                        </span>
                        <span className={`leading-tight break-words ${isUsedInSelectedNote ? 'text-gray-900 font-semibold bg-blue-50 px-1 py-0.5 rounded' : 'text-gray-600'}`}>
                          {docName}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
            
            {/* Floating button to open references */}
            <button
              onClick={() => setMobileReferencesExpanded(!mobileReferencesExpanded)}
              className={`lg:hidden fixed bottom-20 right-4 z-50 flex items-center space-x-2 px-4 py-3 bg-blue-600 text-white rounded-full shadow-lg hover:bg-blue-700 transition-all ${
                mobileReferencesExpanded ? 'opacity-0 pointer-events-none' : 'opacity-100'
              }`}
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <span className="text-sm font-medium">References</span>
              <span className="bg-white text-blue-600 text-xs font-bold rounded-full w-5 h-5 flex items-center justify-center">
                {Object.keys(fiscalNoteData.document_mapping).length}
              </span>
            </button>
            
            {/* Backdrop overlay when expanded */}
            {mobileReferencesExpanded && (
              <div 
                className="lg:hidden fixed inset-0 bg-black bg-opacity-50 z-30"
                onClick={() => setMobileReferencesExpanded(false)}
              />
            )}
          </>
        )}
      </div>
    </div>
  );
};

export default FiscalNoteViewer;
