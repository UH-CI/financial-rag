import type { TrackedNumber, NumberTrackingSegment, HistoryEntry } from '../types';

interface EnhancedTrackedNumber extends TrackedNumber {
  history: HistoryEntry[];
}

/**
 * Build complete history for numbers by comparing segments sequentially
 */
export function buildNumberHistoryForSegments(
  allSegments: NumberTrackingSegment[],
  currentSegmentId: number
): EnhancedTrackedNumber[] {
  // Sort segments by ID to ensure chronological order
  const sortedSegments = [...allSegments].sort((a, b) => a.segment_id - b.segment_id);
  
  // Filter to only segments up to and including current
  const relevantSegments = sortedSegments.filter(s => s.segment_id <= currentSegmentId);
  
  // Map to track all numbers we've seen: number value -> full history
  const numberHistoryMap = new Map<number, {
    appearances: Array<{
      segment_id: number;
      segment_name: string;
      number: number;
      summary?: string;
      source_documents?: string[];
      change_type: string;
      amount_type?: string;
      category?: string;
      fiscal_year?: string[];
      expending_agency?: string;
      filename?: string;
      document_type?: string;
    }>;
    firstAppeared: number;
  }>();
  
  // Process each segment sequentially
  relevantSegments.forEach(segment => {
    segment.numbers.forEach(num => {
      const value = num.number;
      
      if (!numberHistoryMap.has(value)) {
        // First time seeing this number
        numberHistoryMap.set(value, {
          appearances: [{
            segment_id: segment.segment_id,
            segment_name: segment.segment_name,
            number: num.number,
            summary: num.summary,
            source_documents: num.source_documents,
            change_type: num.change_type,
            amount_type: num.amount_type,
            category: num.category,
            fiscal_year: num.fiscal_year,
            expending_agency: num.expending_agency,
            filename: num.filename,
            document_type: num.document_type
          }],
          firstAppeared: segment.segment_id
        });
      } else {
        // We've seen this number before - add to history
        const history = numberHistoryMap.get(value)!;
        history.appearances.push({
          segment_id: segment.segment_id,
          segment_name: segment.segment_name,
          number: num.number,
          summary: num.summary,
          source_documents: num.source_documents,
          change_type: num.change_type,
          amount_type: num.amount_type,
          category: num.category,
          fiscal_year: num.fiscal_year,
          expending_agency: num.expending_agency,
          filename: num.filename,
          document_type: num.document_type
        });
      }
    });
  });
  
  // Now build the final array for the current segment
  const currentSegment = relevantSegments.find(s => s.segment_id === currentSegmentId);
  if (!currentSegment) {
    return [];
  }
  
  // Get all unique numbers that should be in this segment (current + carried)
  const allNumbersForSegment = new Map<number, EnhancedTrackedNumber>();
  
  // First, add all numbers from current segment
  currentSegment.numbers.forEach(num => {
    const history = numberHistoryMap.get(num.number);
    const appearances = history?.appearances || [];
    
    // Build history array (exclude current segment)
    const historyEntries: HistoryEntry[] = appearances
      .filter(app => app.segment_id < currentSegmentId)
      .map(app => ({
        segment_id: app.segment_id,
        number: app.number,
        summary: app.summary,
        similarity_score: 1.0, // We don't have this from backend, default to 1.0
        amount_type: app.amount_type,
        category: app.category,
        fiscal_year: app.fiscal_year,
        expending_agency: app.expending_agency,
        source_documents: app.source_documents,
        filename: app.filename,
        document_type: app.document_type
      }));
    
    allNumbersForSegment.set(num.number, {
      ...num,
      history: historyEntries
    });
  });
  
  // Then, check for carried numbers (in previous segments but not current)
  numberHistoryMap.forEach((history, numberValue) => {
    // If this number appeared before but NOT in current segment
    const inCurrentSegment = allNumbersForSegment.has(numberValue);
    const appearedBefore = history.firstAppeared < currentSegmentId;
    
    if (!inCurrentSegment && appearedBefore) {
      // This number should be carried forward - use NEWEST (last) appearance
      const newestAppearance = history.appearances[history.appearances.length - 1];
      
      // Build history array (all previous appearances)
      const historyEntries: HistoryEntry[] = history.appearances.map(app => ({
        segment_id: app.segment_id,
        number: app.number,
        summary: app.summary,
        similarity_score: 1.0,
        amount_type: app.amount_type,
        category: app.category,
        fiscal_year: app.fiscal_year,
        expending_agency: app.expending_agency,
        source_documents: app.source_documents,
        filename: app.filename,
        document_type: app.document_type
      }));
      
      // Create a carried number entry using the NEWEST version
      allNumbersForSegment.set(numberValue, {
        ...newestAppearance,
        change_type: 'no_change',
        carried_forward: true,
        first_appeared_in_segment: history.firstAppeared,
        history: historyEntries,
        text: newestAppearance.summary || '',
        filename: newestAppearance.source_documents?.[0] || '',
        document_type: 'carried'
      } as EnhancedTrackedNumber);
    }
  });
  
  return Array.from(allNumbersForSegment.values());
}
