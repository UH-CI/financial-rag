import React, { useMemo } from 'react';
import type { NumberTrackingSegment, ChronologicalTracking } from '../types';
import NumberTrackingTable from './NumberTrackingTable';
import { buildNumberHistoryForSegments } from '../utils/buildNumberHistory';

interface NumberTrackingSectionProps {
  tracking?: NumberTrackingSegment;
  fiscalNoteName: string;
  allTrackingData?: ChronologicalTracking; // Full tracking data to get all numbers
  documentMapping?: Record<string, number>; // Document name -> reference number
}

const NumberTrackingSection: React.FC<NumberTrackingSectionProps> = ({ tracking, fiscalNoteName, allTrackingData, documentMapping }) => {
  // Build complete history for all numbers by comparing segments
  const numbersWithHistory = useMemo(() => {
    if (!allTrackingData || !tracking) {
      return tracking?.numbers || [];
    }
    
    return buildNumberHistoryForSegments(allTrackingData.segments, tracking.segment_id);
  }, [allTrackingData, tracking]);
  
  // Debug logging
  console.log('🔍 NumberTrackingSection Debug:');
  console.log('  fiscalNoteName:', fiscalNoteName);
  console.log('  currentSegmentId:', tracking?.segment_id);
  console.log('  original numbers count:', tracking?.numbers?.length);
  console.log('  enhanced numbers count:', numbersWithHistory.length);
  console.log('  first enhanced number:', numbersWithHistory[0]);
  
  if (!tracking) {
    return (
      <div className="mt-8 bg-gray-50 border border-gray-200 rounded-lg p-6">
        <div className="text-center text-gray-500">
          <svg className="w-12 h-12 mx-auto mb-3 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <p className="text-sm font-medium">Number tracking not available for this version</p>
          <p className="text-xs mt-1">This feature requires steps 6 and 7 of the pipeline to be completed</p>
        </div>
      </div>
    );
  }
  
  return (
    <div className="mb-64">
      <div className="bg-white rounded-lg shadow-md p-6 border border-gray-200">
        {/* Title and Legend */}
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900">Amounts Table</h3>
          
          {/* Minimal Legend */}
          <div className="flex items-center gap-3 text-xs">
            <div className="flex items-center gap-1">
              <div className="w-2 h-4 rounded-full bg-blue-500"></div>
              <span className="text-gray-600">New</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-2 h-4 rounded-full bg-green-500"></div>
              <span className="text-gray-600">Continued</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-2 h-4 rounded-full bg-amber-500"></div>
              <span className="text-gray-600">Modified</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-2 h-4 rounded-full bg-gray-500"></div>
              <span className="text-gray-600">Carried</span>
            </div>
          </div>
        </div>
        
        {/* Table */}
        <NumberTrackingTable 
          numbers={numbersWithHistory}
          fiscalNoteName={fiscalNoteName}
          currentSegmentId={tracking.segment_id}
          documentMapping={documentMapping}
        />
      </div>
    </div>
  );
};

export default NumberTrackingSection;
