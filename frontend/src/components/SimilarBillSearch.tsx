import React, { useState, useEffect } from 'react';
import { Search, Loader2, Brain, AlertCircle, ChevronDown, ChevronUp, X } from 'lucide-react';
import { getBillSimilaritySearch, askLLM } from '../services/api';
import type { BillSimilaritySearch, BillVectors } from '../types';
import ReactMarkdown from 'react-markdown';

const SimilarBillSearch = () => {
  const [billType, setBillType] = useState<'HB' | 'SB'>('HB');
  const [billNumber, setBillNumber] = useState('');
  const [searchResults, setSearchResults] = useState<BillSimilaritySearch>({tfidf_results: [], vector_results: [], search_bill: {bill_name: '', summary: '', score: 0}});
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedSummaries, setExpandedSummaries] = useState<Set<string>>(new Set());
  const [llmAnalysis, setLlmAnalysis] = useState<string | null>(null);
  const [billClassification, setBillClassification] = useState<any>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [selectedBill, setSelectedBill] = useState<BillVectors | null>(null);
  const [tooltipPosition, setTooltipPosition] = useState<{x: number, y: number} | null>(null);

  // Close tooltip on scroll
  useEffect(() => {
    const handleScroll = () => {
      if (selectedBill) {
        setSelectedBill(null);
        setTooltipPosition(null);
      }
    };

    window.addEventListener('scroll', handleScroll, true);
    return () => window.removeEventListener('scroll', handleScroll, true);
  }, [selectedBill]);

  const handleSearch = async () => {
    if (!billNumber.trim()) {
      setError('Please enter a bill number');
      return;
    }

    setIsLoading(true);
    setError(null);
    // Reset visualization and AI analysis fields
    setLlmAnalysis(null);
    setBillClassification(null);
    setAnalysisError(null);
    setSelectedBill(null);
    setTooltipPosition(null);
    
    try {
      const results = await getBillSimilaritySearch(billType, billNumber.trim());
      console.log(results);
      setSearchResults(results);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to search for similar bills');
      setSearchResults({tfidf_results: [], vector_results: [], search_bill: {bill_name: '', summary: '', score: 0}});
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSearch();
    }
  };

  const toggleSummary = (billName: string, tableTitle: string) => {
    const key = `${tableTitle}-${billName}`;
    const newExpanded = new Set(expandedSummaries);
    if (newExpanded.has(key)) {
      newExpanded.delete(key);
    } else {
      newExpanded.add(key);
    }
    setExpandedSummaries(newExpanded);
  };

  // Helper function to get cluster colors
  const getClusterColor = (cluster: number) => {
    const colors = [
      '#3B82F6', // blue
      '#10B981', // emerald
      '#F59E0B', // amber
      '#EF4444', // red
      '#8B5CF6', // violet
      '#06B6D4', // cyan
      '#84CC16', // lime
      '#F97316', // orange
      '#EC4899', // pink
      '#6B7280', // gray
    ];
    return colors[cluster % colors.length];
  };

  // Helper function to handle bill click
  const handleBillClick = (bill: BillVectors, event: React.MouseEvent) => {
    // If clicking the same bill, close tooltip
    if (selectedBill && selectedBill.bill_name === bill.bill_name) {
      setSelectedBill(null);
      setTooltipPosition(null);
      return;
    }

    // Simple viewport positioning
    const rect = event.currentTarget.getBoundingClientRect();
    const tooltipX = rect.left + rect.width / 2;
    const tooltipY = rect.bottom + 10;

    setSelectedBill(bill);
    setTooltipPosition({ x: tooltipX, y: tooltipY });
  };

  // Helper function to get bill classification
  const getBillClassification = (billName: string) => {
    if (!billClassification) return null;
    return billClassification.find((b: any) => b.bill_name === billName);
  };


  const handleLLMAnalysis = async () => {
    if (!searchResults || (searchResults.tfidf_results.length === 0 && searchResults.vector_results.length === 0)) {
      return;
    }

    setIsAnalyzing(true);
    setAnalysisError(null);
    
    try {
      // Combine all search results into a unique array
      const allBills = [...searchResults.tfidf_results, ...searchResults.vector_results];
      const uniqueBills = allBills.filter((bill, index, self) => 
        index === self.findIndex(b => b.bill_name === bill.bill_name)
      );

      // Single comprehensive prompt for analysis and classification
      const prompt = `
Analyze the following similar bills found for ${searchResults.search_bill.bill_name}:

**Search Bill:**
${searchResults.search_bill.bill_name}: ${searchResults.search_bill.summary}

**Similar Bills:**
${uniqueBills.map((bill, index) => 
  `${index + 1}. ${bill.bill_name}: ${bill.summary}`
).join('\n')}

Please provide a comprehensive analysis with clear sections, then follow with structured data for parsing.

Format your response as follows:

## Analysis

[Your comprehensive analysis here explaining the relationships and themes]

## Supporting Bills
[List and explain bills that support or advance the same cause as the original bill]

## Contracting/Competing Bills  
[List and explain bills that oppose or contradict the original bill's cause]

## Unrelated Bills
[List and explain bills that are unrelated to the original bill's cause]

## JSON_DATA_START
{
  "supporting_bills": [
    {
      "bill_name": "exact_bill_name_here",
      "cluster_name": "descriptive_theme_name",
      "explanation": "brief explanation"
    }
  ],
  "contracting_bills": [
    {
      "bill_name": "exact_bill_name_here", 
      "cluster_name": "descriptive_theme_name",
      "explanation": "brief explanation"
    }
  ],
  "unrelated_bills": [
    {
      "bill_name": "exact_bill_name_here",
      "cluster_name": "descriptive_theme_name", 
      "explanation": "brief explanation"
    }
  ]
}
## JSON_DATA_END

IMPORTANT: 
- Use the exact bill names as they appear in the list above
- Each bill should appear in exactly one category
- Cluster names should be 2-3 words describing the common theme
- Include both the readable analysis sections AND the JSON data between the markers`;

      console.log('Sending comprehensive analysis prompt to LLM...');
      const response = await askLLM(prompt);
      console.log('Received comprehensive response:', response);
      
      try {
        // Extract the readable analysis (everything before JSON_DATA_START)
        const jsonStartMarker = '## JSON_DATA_START';
        const jsonEndMarker = '## JSON_DATA_END';
        
        const jsonStartIndex = response.indexOf(jsonStartMarker);
        const jsonEndIndex = response.indexOf(jsonEndMarker);
        
        if (jsonStartIndex === -1 || jsonEndIndex === -1) {
          throw new Error('JSON data markers not found in response');
        }
        
        // Extract the readable analysis text (everything before JSON_DATA_START)
        const analysisText = response.substring(0, jsonStartIndex).trim();
        setLlmAnalysis(analysisText);
        
        // Extract and parse the JSON data
        const jsonData = response.substring(
          jsonStartIndex + jsonStartMarker.length, 
          jsonEndIndex
        ).trim();
        
        console.log('Extracted JSON data:', jsonData);
        const parsedResponse = JSON.parse(jsonData);
        
        // Convert the structured response to the format expected by the visualization
        const billClassification: any[] = [];
        
        // Create a map of cluster names to cluster IDs to ensure same cluster_name gets same color
        const clusterNameToId = new Map<string, number>();
        let nextClusterId = 0;
        
        const getClusterIdForName = (clusterName: string) => {
          if (!clusterNameToId.has(clusterName)) {
            clusterNameToId.set(clusterName, nextClusterId++);
          }
          return clusterNameToId.get(clusterName)!;
        };
        
        // Process supporting bills
        parsedResponse.supporting_bills?.forEach((bill: any) => {
          billClassification.push({
            bill_name: bill.bill_name,
            relationship: 'supporting',
            cluster: getClusterIdForName(bill.cluster_name),
            cluster_name: bill.cluster_name
          });
        });
        
        // Process contracting bills
        parsedResponse.contracting_bills?.forEach((bill: any) => {
          billClassification.push({
            bill_name: bill.bill_name,
            relationship: 'contracting',
            cluster: getClusterIdForName(bill.cluster_name),
            cluster_name: bill.cluster_name
          });
        });
        
        // Process unrelated bills
        parsedResponse.unrelated_bills?.forEach((bill: any) => {
          billClassification.push({
            bill_name: bill.bill_name,
            relationship: 'unrelated',
            cluster: getClusterIdForName(bill.cluster_name),
            cluster_name: bill.cluster_name
          });
        });
        
        setBillClassification(billClassification);
        console.log('Processed classification:', billClassification);
      } catch (parseError) {
        console.error('Failed to parse comprehensive response JSON:', parseError);
        setAnalysisError('Failed to parse comprehensive analysis response as JSON');
      }
    } catch (err) {
      console.error('LLM Analysis error:', err);
      setAnalysisError(err instanceof Error ? err.message : 'Failed to analyze bills with LLM');
    } finally {
      setIsAnalyzing(false);
    }
  };

  // Bill Visualization Component
  const BillVisualization = () => {
    if (!searchResults || !billClassification || (searchResults.tfidf_results.length === 0 && searchResults.vector_results.length === 0)) {
      return null;
    }

    // Combine results and remove duplicates, keeping highest score
    const combinedBills = new Map();
    
    // Add TF-IDF results
    searchResults.tfidf_results.forEach(bill => {
      if (!combinedBills.has(bill.bill_name) || combinedBills.get(bill.bill_name).score < bill.score) {
        combinedBills.set(bill.bill_name, { ...bill, source: 'tfidf' });
      }
    });
    
    // Add vector results
    searchResults.vector_results.forEach(bill => {
      if (!combinedBills.has(bill.bill_name) || combinedBills.get(bill.bill_name).score < bill.score) {
        combinedBills.set(bill.bill_name, { ...bill, source: 'vector' });
      }
    });
    
    // Convert to array
    const uniqueBills = Array.from(combinedBills.values());

    // Find min and max scores for normalization
    const scores = uniqueBills.map(bill => bill.score);
    const minScore = Math.min(...scores);
    const maxScore = Math.max(...scores);

    // Normalize scores to 0-1 range
    const normalizeScore = (score: number) => {
      if (maxScore === minScore) return 0.5;
      return (score - minScore) / (maxScore - minScore);
    };

    // Create 10 bins and categorize bills (flipped: higher similarity at top)
    const getSimilarityLabel = (binIndex: number) => {
      if (binIndex === 0) return "Very Similar";
      if (binIndex === 9) return "Not Very Similar";
      return "|";
    };

    const bins = Array.from({ length: 10 }, (_, i) => ({
      index: i,
      label: getSimilarityLabel(i),
      leftBills: [] as any[],
      rightBills: [] as any[]
    }));

    // Separate unrelated bills
    const unrelatedBills: any[] = [];

    // Assign bills to bins based on normalized scores (flipped order)
    uniqueBills.forEach(bill => {
      const classification = getBillClassification(bill.bill_name);
      const normalizedScore = normalizeScore(bill.score);
      // Flip the bin assignment: higher scores (more similar) go to lower indices (top)
      const binIndex = Math.min(Math.floor((1 - normalizedScore) * 10), 9);
      
      const billWithClassification = {
        ...bill,
        classification,
        normalizedScore
      };

      // Separate unrelated bills to show at bottom
      if (classification?.relationship === 'unrelated') {
        unrelatedBills.push(billWithClassification);
      } else if (classification?.relationship === 'supporting') {
        bins[binIndex].rightBills.push(billWithClassification);
      } else {
        bins[binIndex].leftBills.push(billWithClassification);
      }
    });

    return (
      <div className="bg-white rounded-lg shadow p-6 relative">
        <h3 className="text-lg font-semibold text-gray-900 mb-6 flex items-center">
          <Brain className="w-5 h-5 mr-2 text-purple-600" />
          Bill Relationship Visualization
        </h3>
        
        {/* Vertical layout container */}
        <div className="flex flex-col items-center space-y-4">
          {/* Original bill at top */}
          <div className="flex flex-col items-center mb-4">
            <div 
              className="w-24 h-24 rounded-full bg-gray-800 flex items-center justify-center text-white text-lg font-bold cursor-pointer hover:bg-gray-700 transition-colors shadow-lg"
              onClick={(e) => handleBillClick(searchResults.search_bill, e)}
              title={searchResults.search_bill.bill_name}
            >
              {searchResults.search_bill.bill_name.replace(/_/g, '')}
            </div>
            <div className="text-sm text-center mt-2 font-semibold">Original Bill</div>
            <div className="text-xs text-center text-gray-600">{searchResults.search_bill.bill_name}</div>
          </div>

          {/* Vertical line */}
          <div className="w-1 h-8 bg-gray-300 rounded"></div>

          {/* Bins container */}
          <div className="w-full max-w-6xl">
            {/* Column headers */}
            <div className="flex justify-between mb-4 text-sm font-semibold text-gray-700">
              <div className="w-1/3 text-center">Contracting</div>
              <div className="w-1/3 text-center">Similarity Level</div>
              <div className="w-1/3 text-center">Supporting</div>
            </div>

            {/* Bins */}
            {bins.map((bin, binIndex) => {
              // Show labels for "Very Similar", "Not Very Similar", and every "|" 
              const showLabel = bin.label === "Very Similar" || bin.label === "Not Very Similar" || bin.label === "|";
              
              return (
                <div key={binIndex} className="flex items-center justify-between mb-3 min-h-[60px] border-b border-gray-100 pb-3">
                  {/* Left side - Contracting bills */}
                  <div className="w-1/3 flex flex-wrap justify-end gap-2 pr-4">
                    {bin.leftBills.map((bill, billIndex) => {
                      const cluster = bill.classification?.cluster || 0;
                      const color = getClusterColor(cluster);
                      
                      return (
                        <div
                          key={billIndex}
                          className="cursor-pointer hover:scale-110 transition-transform"
                          onClick={(e) => handleBillClick(bill, e)}
                          title={`${bill.bill_name} - ${bill.classification?.relationship || 'unknown'}`}
                        >
                          <div 
                            className="w-16 h-16 rounded-full flex items-center justify-center text-white text-base font-bold shadow-lg"
                            style={{ backgroundColor: color }}
                          >
                            {bill.bill_name.replace(/_/g, '')}
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  {/* Center - Similarity label (only show for first occurrence) */}
                  <div className="w-1/3 text-center">
                    {showLabel && (
                      <div className="text-xs text-gray-600 bg-gray-50 px-3 py-2 rounded-full inline-block">
                        {bin.label}
                      </div>
                    )}
                  </div>

                  {/* Right side - Supporting bills */}
                  <div className="w-1/3 flex flex-wrap justify-start gap-2 pl-4">
                    {bin.rightBills.map((bill, billIndex) => {
                      const cluster = bill.classification?.cluster || 0;
                      const color = getClusterColor(cluster);
                      
                      return (
                        <div
                          key={billIndex}
                          className="cursor-pointer hover:scale-110 transition-transform"
                          onClick={(e) => handleBillClick(bill, e)}
                          title={`${bill.bill_name} - ${bill.classification?.relationship || 'unknown'}`}
                        >
                          <div 
                            className="w-16 h-16 rounded-full flex items-center justify-center text-white text-base font-bold shadow-lg"
                            style={{ backgroundColor: color }}
                          >
                            {bill.bill_name.replace(/_/g, '')}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Unrelated Bills Section - Below the chart */}
          {unrelatedBills.length > 0 && (
            <div className="w-full max-w-6xl mt-8">
              <div className="text-center mb-4">
                <h4 className="text-sm font-semibold text-gray-700">Unrelated Bills</h4>
              </div>
              <div className="flex flex-wrap justify-center gap-3">
                {unrelatedBills.map((bill, billIndex) => {
                  const cluster = bill.classification?.cluster || 0;
                  const color = getClusterColor(cluster);
                  
                  return (
                    <div
                      key={billIndex}
                      className="cursor-pointer hover:scale-110 transition-transform"
                      onClick={(e) => handleBillClick(bill, e)}
                      title={`${bill.bill_name} - ${bill.classification?.relationship || 'unknown'}`}
                    >
                      <div 
                        className="w-16 h-16 rounded-full flex items-center justify-center text-white text-base font-bold shadow-lg"
                        style={{ backgroundColor: color }}
                      >
                        {bill.bill_name.replace(/_/g, '')}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>

      </div>
    );
  };


  return (
    <div className="h-full flex flex-col bg-gray-50">
      {/* Search Controls */}
      <div className="bg-white border-b border-gray-200 p-6">
        <div className="max-w-4xl mx-auto">
          
          <div className="flex items-center space-x-4">
          <h2 className="text-2xl font-bold text-gray-900 pt-5">Similar Bill Search</h2>

            {/* Bill Type Dropdown */}
            <div className="flex-shrink-0">
              <label htmlFor="billType" className="block text-sm font-medium text-gray-700 mb-1">
                Bill Type
              </label>
              <select
                id="billType"
                value={billType}
                onChange={(e) => setBillType(e.target.value as 'HB' | 'SB')}
                className="block w-20 px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
              >
                <option value="HB">HB</option>
                <option value="SB">SB</option>
              </select>
            </div>

            {/* Bill Number Input */}
            <div className="flex-1 max-w-xs">
              <label htmlFor="billNumber" className="block text-sm font-medium text-gray-700 mb-1">
                Bill Number
              </label>
              <input
                type="number"
                id="billNumber"
                value={billNumber}
                onChange={(e) => setBillNumber(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Enter bill number (e.g., 400)"
                min="1"
                step="1"
                className="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
              />
            </div>

            {/* Search Button */}
            <div className="flex-shrink-0 pt-6">
              <button
                onClick={handleSearch}
                disabled={isLoading}
                className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isLoading ? (
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                ) : (
                  <Search className="w-4 h-4 mr-2" />
                )}
                Search
              </button>
            </div>

            {/* LLM Analysis Button */}
            <div className="flex-shrink-0 pt-6">
              <button
                onClick={handleLLMAnalysis}
                disabled={isAnalyzing || !searchResults || (searchResults.tfidf_results.length === 0 && searchResults.vector_results.length === 0)}
                className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-purple-600 hover:bg-purple-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-purple-500 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isAnalyzing ? (
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                ) : (
                  <Brain className="w-4 h-4 mr-2" />
                )}
                Analyze with AI
              </button>
            </div>
          </div>

          {/* Error Messages */}
          {error && (
            <div className="mt-4 flex items-center space-x-2 text-red-600">
              <AlertCircle className="w-4 h-4" />
              <span className="text-sm">{error}</span>
            </div>
          )}
          {analysisError && (
            <div className="mt-4 flex items-center space-x-2 text-red-600">
              <AlertCircle className="w-4 h-4" />
              <span className="text-sm">Analysis Error: {analysisError}</span>
            </div>
          )}
        </div>
      </div>

      {/* Results Section */}
      <div className="flex-1 overflow-auto p-6 relative">
        {isLoading ? (
          <div className="flex items-center justify-center h-64">
            <div className="text-center">
              <Loader2 className="w-8 h-8 text-blue-600 animate-spin mx-auto mb-4" />
              <p className="text-gray-600">Searching for similar bills...</p>
            </div>
          </div>
        ) : searchResults ? (
          <div className="w-full max-w-none mx-auto space-y-6">
            {/* Combined Results Table */}
            <div className="bg-white rounded-lg shadow p-6 max-w-7xl mx-auto">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Similar Bills Found</h3>
              <div className="overflow-x-auto">
                <table className="w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider w-8">
                        #
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-8">
                        Bill Name
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-2/3">
                        Summary
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-12">
                        
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {(() => {
                      const combinedMap = new Map<string, BillVectors>();
                      searchResults.tfidf_results.forEach(bill => combinedMap.set(bill.bill_name, bill));
                      searchResults.vector_results.forEach(bill => combinedMap.set(bill.bill_name, bill));
                      
                      return Array.from(combinedMap.values())
                        .sort((a, b) => b.score - a.score)
                        .map((result, index) => {
                          const tableTitle = "Combined";
                          const key = `${tableTitle}-${result.bill_name}`;
                          const isExpanded = expandedSummaries.has(key);
                          
                          return (
                            <tr key={index} className="hover:bg-gray-50">
                              <td className="px-2 py-1 text-center text-sm font-medium text-gray-500">
                                {index + 1}
                              </td>
                              <td className="px-2 py-1 text-sm font-medium">
                                <a
                                  href={`https://www.capitol.hawaii.gov/session/measure_indiv.aspx?billtype=${result.bill_name.match(/^(HB|SB)/)?.[0] || 'HB'}&billnumber=${result.bill_name.match(/\d+/)?.[0] || ''}&year=2025`}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-blue-600 hover:text-blue-800 hover:underline transition-colors"
                                >
                                  {result.bill_name}
                                </a>
                              </td>
                              <td className="px-4 py-3 text-sm text-gray-700">
                                <div className={isExpanded ? '' : 'line-clamp-2'}>
                                  {result.summary}
                                </div>
                              </td>
                              <td className="px-4 py-3 text-center">
                                <button
                                  onClick={() => toggleSummary(result.bill_name, tableTitle)}
                                  className="text-blue-600 hover:text-blue-800 transition-colors"
                                >
                                  {isExpanded ? (
                                    <ChevronUp className="w-3 h-3" />
                                  ) : (
                                    <ChevronDown className="w-3 h-3" />
                                  )}
                                </button>
                              </td>
                            </tr>
                          );
                        });
                    })()}
                  </tbody>
                </table>
              </div>
            </div>
            
            {/* Bill Visualization */}
            <div className="relative">
              <BillVisualization />
              
              {/* Floating Legend Box */}
              {billClassification && (
                <div className="absolute top-32 left-4 bg-white rounded-lg shadow-lg border border-gray-200 p-4 z-10 max-w-xs">
                  <h4 className="text-sm font-semibold text-gray-900 mb-3">Legend</h4>
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <div className="w-3 h-3 rounded-full bg-gray-800"></div>
                      <span className="text-xs text-gray-600">Original Bill</span>
                    </div>
                    {Array.from(new Map(billClassification.map((b: any) => [b.cluster_name, b.cluster])).entries()).map(([clusterName, cluster]) => {
                      return (
                        <div key={cluster as number} className="flex items-center gap-2">
                          <div 
                            className="w-3 h-3 rounded-full" 
                            style={{ backgroundColor: getClusterColor(cluster as number) }}
                          ></div>
                          <span className="text-xs text-gray-600">{String(clusterName)}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
            
            {/* LLM Analysis Section */}
            {llmAnalysis && (
              <div className="bg-white rounded-lg shadow p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                  <Brain className="w-5 h-5 mr-2 text-purple-600" />
                  AI Analysis
                </h3>
                <div className="prose prose-sm max-w-none text-gray-700 leading-relaxed">
                  <ReactMarkdown 
                    components={{
                      h1: ({children}) => <h1 className="text-2xl font-bold text-gray-900 mt-6 mb-4">{children}</h1>,
                      h2: ({children}) => <h2 className="text-xl font-semibold text-gray-900 mt-6 mb-3">{children}</h2>,
                      h3: ({children}) => <h3 className="text-lg font-semibold text-gray-900 mt-4 mb-2">{children}</h3>,
                      p: ({children}) => <p className="mb-3 text-gray-700">{children}</p>,
                      ul: ({children}) => <ul className="list-disc list-outside mb-3 space-y-1 ml-6">{children}</ul>,
                      ol: ({children}) => <ol className="list-decimal list-outside mb-3 space-y-1 ml-6">{children}</ol>,
                      li: ({children}) => <li className="text-gray-700">{children}</li>,
                      strong: ({children}) => <strong className="font-semibold text-gray-900">{children}</strong>,
                      em: ({children}) => <em className="italic">{children}</em>,
                    }}
                  >
                    {llmAnalysis}
                  </ReactMarkdown>
                </div>
              </div>
            )}

            {/* Bill Classification Section */}
            
          </div>
        ) : (
          <div className="flex items-center justify-center h-64">
            <div className="text-center">
              <Search className="w-12 h-12 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-semibold text-gray-900 mb-2">Search for Similar Bills</h3>
              <p className="text-gray-600">
                Enter a bill type and number above to find similar bills using advanced search algorithms.
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Simple Tooltip */}
      {selectedBill && tooltipPosition && (
        <div 
          className="fixed z-50 pointer-events-none"
          style={{ 
            left: tooltipPosition.x,
            top: tooltipPosition.y,
            transform: 'translateX(-50%)'
          }}
        >
          <div className="bg-white rounded-lg shadow-xl border border-gray-200 w-80 pointer-events-auto">
            {/* Arrow pointing up */}
            <div className="absolute -top-2 left-1/2 transform -translate-x-1/2">
              <div className="w-0 h-0 border-l-6 border-r-6 border-b-6 border-l-transparent border-r-transparent border-b-white"></div>
            </div>
            
            <div className="p-3">
              {(() => {
                const classification = getBillClassification(selectedBill.bill_name);
                const cluster = classification?.cluster || 0;
                const color = getClusterColor(cluster);
                
                return (
                  <div>
                    {/* Header */}
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="text-sm font-semibold text-gray-900">
                        {selectedBill.bill_name}
                      </h3>
                      <button
                        onClick={() => {
                          setSelectedBill(null);
                          setTooltipPosition(null);
                        }}
                        className="text-gray-400 hover:text-gray-600 transition-colors"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    </div>

                    {/* Classification badges */}
                    <div className="flex flex-wrap gap-1 mb-2">
                      {classification && (
                        <>
                          <span className={`inline-flex px-2 py-1 text-xs font-medium rounded-full ${
                            classification.relationship === 'supporting' 
                              ? 'bg-green-100 text-green-800' 
                              : classification.relationship === 'contracting'
                              ? 'bg-red-100 text-red-800'
                              : 'bg-gray-100 text-gray-800'
                          }`}>
                            {classification.relationship === 'supporting' ? 'Supporting' : 
                             classification.relationship === 'contracting' ? 'Contracting' : 'Unrelated'}
                          </span>
                          <span 
                            className="inline-flex px-2 py-1 text-xs font-medium rounded-full text-white"
                            style={{ backgroundColor: color }}
                          >
                            {classification.cluster_name || `Cluster ${cluster}`}
                          </span>
                        </>
                      )}
                      <span className="inline-flex px-2 py-1 text-xs font-medium rounded-full bg-blue-100 text-blue-800">
                        Score: {selectedBill.score.toFixed(3)}
                      </span>
                    </div>

                    {/* Bill summary */}
                    <div 
                      className="p-2 rounded border-l-3 text-gray-700 leading-tight mb-2"
                      style={{ 
                        borderLeftColor: color,
                        backgroundColor: `${color}10`
                      }}
                    >
                      <h4 className="font-medium text-gray-900 mb-1 text-xs">Bill Summary:</h4>
                      <p className="text-xs leading-tight">{selectedBill.summary}</p>
                    </div>

                    {/* Link to full bill */}
                    <div>
                      <a
                        href={`https://www.capitol.hawaii.gov/session/measure_indiv.aspx?billtype=${selectedBill.bill_name.match(/^(HB|SB)/)?.[0] || 'HB'}&billnumber=${selectedBill.bill_name.match(/\d+/)?.[0] || ''}&year=2025`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center px-2 py-1 border border-transparent text-xs font-medium rounded shadow-sm text-white hover:opacity-90 transition-colors w-full justify-center"
                        style={{ backgroundColor: color }}
                      >
                        View Full Bill
                      </a>
                    </div>
                  </div>
                );
              })()}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default SimilarBillSearch;
