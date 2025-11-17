import React, { useState, useMemo, useEffect } from 'react';
import type { TrackedNumber } from '../../../types';
import NumberHistoryTimeline from './NumberHistoryTimeline';

interface NumberTrackingTableProps {
  numbers: TrackedNumber[];
  fiscalNoteName: string;
  currentSegmentId: number; // To show cumulative numbers up to this segment
  documentMapping?: Record<string, number>; // Document name -> reference numbera
}

type FilterType = 'all' | 'new' | 'continued' | 'modified' | 'no_change' | 'from_previous';
type SortBy = 'amount' | 'change_type' | 'first_appeared';

const NumberTrackingTable: React.FC<NumberTrackingTableProps> = ({ numbers, currentSegmentId, documentMapping, fiscalNoteName }) => {
  const [filterType, setFilterType] = useState<FilterType>('all');
  const [sortBy, ] = useState<SortBy>('amount');
  const [sortDirection, ] = useState<'asc' | 'desc'>('desc');
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set());
  
  // Collapse all rows when fiscal note changes
  useEffect(() => {
    setExpandedRows(new Set());
  }, [currentSegmentId, fiscalNoteName]);
  
  // Debug logging
  console.log('📊 NumberTrackingTable Debug:', {
    currentSegmentId,
    totalNumbers: numbers.length,
    documentMapping: documentMapping,
    firstNumber: numbers[0],
    firstNumberSourceDocs: numbers[0]?.source_documents,
    // Show the transformation for first source doc
    firstSourceDocTransformation: numbers[0]?.source_documents?.[0] ? {
      original: numbers[0].source_documents[0],
      afterSplit: numbers[0].source_documents[0].split('.')[0],
      foundInMapping: !!(documentMapping && documentMapping[numbers[0].source_documents[0].split('.')[0]]),
      refNumber: documentMapping?.[numbers[0].source_documents[0].split('.')[0]]
    } : null
  });
  
  // Get all available property keys from the numbers - show ALL columns except specified ones
  const availableColumns = useMemo(() => {
    const columns = new Set<string>();
    const excludedColumns = [
      'history', 
      'all_merged_numbers', 
      'exact_match_low_similarity',
      'first_appeared_in_segment',
      'history_length',
      'carried_forward',
      'change_type' // Will be shown above number instead
    ];
    
    numbers.forEach(num => {
      Object.keys(num).forEach(key => {
        if (!excludedColumns.includes(key)) {
          columns.add(key);
        }
      });
    });
    return Array.from(columns);
  }, [numbers]);
  
  // Toggle row expansion
  const toggleRow = (index: number) => {
    setExpandedRows(prev => {
      const newSet = new Set(prev);
      if (newSet.has(index)) {
        newSet.delete(index);
      } else {
        newSet.add(index);
      }
      return newSet;
    });
  };

  // Filter and sort numbers
  const processedNumbers = useMemo(() => {
    // Filter - show cumulative numbers (all numbers up to and including current segment)
    let filtered = numbers.filter(num => {
      // Show all numbers that appeared in or before this segment
      const appearedInOrBefore = num.first_appeared_in_segment <= currentSegmentId;
      
      if (filterType === 'all') return appearedInOrBefore;
      if (filterType === 'from_previous') return appearedInOrBefore && num.first_appeared_in_segment < currentSegmentId;
      return appearedInOrBefore && num.change_type === filterType;
    });
    
    // Sort
    filtered = [...filtered].sort((a, b) => {
      let comparison = 0;
      
      switch (sortBy) {
        case 'amount':
          comparison = a.number - b.number;
          break;
        case 'change_type':
          comparison = a.change_type.localeCompare(b.change_type);
          break;
        case 'first_appeared':
          comparison = a.first_appeared_in_segment - b.first_appeared_in_segment;
          break;
      }
      
      return sortDirection === 'desc' ? -comparison : comparison;
    });
    
    return filtered;
  }, [numbers, filterType, sortBy, sortDirection]);
  
  
  // Helper to render cell value
  const renderCellValue = (value: any) => {
    if (value === null || value === undefined) return <span className="text-gray-400">-</span>;
    if (typeof value === 'boolean') return value ? '✓' : '✗';
    if (Array.isArray(value)) return value.join(', ');
    if (typeof value === 'object') return JSON.stringify(value);
    return String(value);
  };
  
  return (
    <div className="number-tracking-table mt-4">
      {/* Filters and Controls */}
      <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
        <div className="flex gap-2 flex-wrap">
          <button 
            onClick={() => setFilterType('all')}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              filterType === 'all' 
                ? 'bg-blue-600 text-white shadow-sm' 
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            All ({numbers.length})
          </button>
          <button 
            onClick={() => setFilterType('new')}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              filterType === 'new' 
                ? 'bg-blue-600 text-white shadow-sm' 
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            🆕 New ({numbers.filter(n => n.change_type === 'new' && n.first_appeared_in_segment <= currentSegmentId).length})
          </button>
          <button 
            onClick={() => setFilterType('continued')}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              filterType === 'continued' 
                ? 'bg-blue-600 text-white shadow-sm' 
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            ✓ Continued ({numbers.filter(n => n.change_type === 'continued' && n.first_appeared_in_segment <= currentSegmentId).length})
          </button>
          <button 
            onClick={() => setFilterType('modified')}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              filterType === 'modified' 
                ? 'bg-blue-600 text-white shadow-sm' 
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            ⚡ Modified ({numbers.filter(n => n.change_type === 'modified' && n.first_appeared_in_segment <= currentSegmentId).length})
          </button>
          <button 
            onClick={() => setFilterType('no_change')}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              filterType === 'no_change' 
                ? 'bg-blue-600 text-white shadow-sm' 
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            📋 Carried ({numbers.filter(n => n.change_type === 'no_change' && n.first_appeared_in_segment <= currentSegmentId).length})
          </button>
          <button 
            onClick={() => setFilterType('from_previous')}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              filterType === 'from_previous' 
                ? 'bg-blue-600 text-white shadow-sm' 
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            📂 From Previous ({numbers.filter(n => n.first_appeared_in_segment < currentSegmentId).length})
          </button>
        </div>
      </div>
      
      {/* Results count */}
      <div className="text-sm text-gray-600 mb-3">
        Showing {processedNumbers.length} numbers (cumulative up to this version)
      </div>
      
      {/* Table with dynamic columns */}
      <div className="overflow-x-auto border border-gray-200 rounded-lg shadow-sm">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              {/* Change type column - minimal */}
              <th className="px-1 py-2 text-center text-xs font-semibold text-gray-700 uppercase tracking-wider whitespace-nowrap w-8">
                
              </th>
              {/* Expand/collapse column */}
              <th className="px-2 py-2 text-center text-xs font-semibold text-gray-700 uppercase tracking-wider whitespace-nowrap w-10">
                
              </th>
              {/* Dynamic columns based on available data */}
              {availableColumns.map(column => (
                <th 
                  key={column}
                  className="px-3 py-2 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider whitespace-nowrap"
                >
                  {column.replace(/_/g, ' ')}
                </th>
              ))}
              <th className="px-3 py-2 text-center text-xs font-semibold text-gray-700 uppercase tracking-wider whitespace-nowrap">
                History
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {processedNumbers.length === 0 ? (
              <tr>
                <td colSpan={availableColumns.length + 3} className="px-4 py-8 text-center text-gray-500">
                  No numbers match the selected filter
                </td>
              </tr>
            ) : (
              processedNumbers.map((num, idx) => (
                <React.Fragment key={idx}>
                  {/* Main Row */}
                  <tr 
                    className={`hover:bg-gray-50 transition-colors ${
                      expandedRows.has(idx) ? 'bg-blue-50' : ''
                    } ${
                      num.first_appeared_in_segment < currentSegmentId ? 'bg-blue-50/20' : ''
                    }`}
                  >
                    {/* Change type indicator - minimal */}
                    <td className="px-1 py-2 text-center">
                      <div className="w-2 h-8 rounded-full mx-auto" style={{
                        backgroundColor: 
                          num.change_type === 'new' ? '#3b82f6' :
                          num.change_type === 'continued' ? '#10b981' :
                          num.change_type === 'modified' ? '#f59e0b' :
                          '#6b7280'
                      }} title={
                        num.change_type === 'new' ? 'New' :
                        num.change_type === 'continued' ? 'Continued' :
                        num.change_type === 'modified' ? 'Modified' :
                        'Carried'
                      } />
                    </td>
                    
                    {/* Expand/collapse button - Only if has history */}
                    <td className="px-2 py-2 text-center">
                      {num.history && num.history.length > 0 ? (
                        <button
                          onClick={() => toggleRow(idx)}
                          className="text-gray-600 hover:text-gray-900 transition-colors p-1"
                          title={expandedRows.has(idx) ? 'Collapse history' : 'Expand history'}
                        >
                          {expandedRows.has(idx) ? '▼' : '▶'}
                        </button>
                      ) : (
                        <span className="text-gray-300">—</span>
                      )}
                    </td>
                    
                    {/* Dynamic cells based on available columns */}
                    {availableColumns.map(column => (
                      <td key={column} className="px-3 py-2 text-sm">
                        {column === 'number' ? (
                          <div className="flex flex-col">
                            <span className="text-lg font-bold text-gray-900">
                              ${(num as any)[column].toLocaleString()}
                            </span>
                            {num.previous_number && (
                              <span className="text-xs text-gray-500">
                                was ${num.previous_number.toLocaleString()}
                              </span>
                            )}
                          </div>
                        ) : column === 'summary' || column === 'text' ? (
                          <p className="text-sm text-gray-700 line-clamp-2 max-w-md">
                            {(num as any)[column] || <span className="text-gray-400 italic">-</span>}
                          </p>
                        ) : column === 'source_documents' ? (
                          <span className="text-sm text-blue-600 font-mono">
                            {Array.isArray((num as any)[column]) && documentMapping ? (
                              (num as any)[column].map((doc: string, i: number) => {
                                // Try multiple matching strategies
                                const docBase = doc.split('.')[0]; // Keep trailing underscore
                                const docBaseNoUnderscore = docBase.replace(/_$/, ''); // Remove trailing underscore
                                
                                // Try exact match first, then without underscore, then original
                                const refNum = documentMapping[docBase] || 
                                               documentMapping[docBaseNoUnderscore] || 
                                               documentMapping[doc];
                                
                                return (
                                  <span key={i} className="mr-1">
                                    [{refNum || '?'}]
                                  </span>
                                );
                              })
                            ) : Array.isArray((num as any)[column]) ? (
                              (num as any)[column].join(', ')
                            ) : (
                              renderCellValue((num as any)[column])
                            )}
                          </span>
                        ) : column === 'fiscal_year' ? (
                          <span className="text-sm">
                            {Array.isArray((num as any)[column]) ? (num as any)[column].join(', ') : renderCellValue((num as any)[column])}
                          </span>
                        ) : (
                          renderCellValue((num as any)[column])
                        )}
                      </td>
                    ))}
                    <td className="px-3 py-2 text-center whitespace-nowrap">
                      {num.history && num.history.length > 0 ? (
                        <span className="inline-flex items-center justify-center w-6 h-6 text-sm font-semibold text-blue-600 bg-blue-100 rounded-full">
                          {num.history.length}
                        </span>
                      ) : (
                        <span className="text-xs text-gray-400">0</span>
                      )}
                    </td>
                  </tr>
                  
                  {/* Expanded History Row - Show for ALL expanded rows */}
                  {expandedRows.has(idx) && (
                    <tr className="bg-gray-50">
                      <td colSpan={availableColumns.length + 3} className="p-0">
                        {num.history && num.history.length > 0 ? (
                          <NumberHistoryTimeline 
                            history={num.history}
                            currentNumber={num}
                            currentSegmentId={currentSegmentId}
                            documentMapping={documentMapping}
                          />
                        ) : (
                          <div className="bg-gray-50 p-6 text-center">
                            <p className="text-gray-500 text-sm">No history available for this number</p>
                            <p className="text-gray-400 text-xs mt-1">This number appeared for the first time in this segment</p>
                          </div>
                        )}
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default NumberTrackingTable;
