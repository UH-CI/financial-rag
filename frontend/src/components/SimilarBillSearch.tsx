import { useState } from 'react';
import { Search, Loader2, AlertCircle, ChevronDown, ChevronUp, Brain } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { getBillSimilaritySearch, askLLM } from '../services/api';
import type { BillSimilaritySearch, BillVectors } from '../types';

const SimilarBillSearch = () => {
  const [billType, setBillType] = useState<'HB' | 'SB'>('HB');
  const [billNumber, setBillNumber] = useState('');
  const [searchResults, setSearchResults] = useState<BillSimilaritySearch>({tfidf_results: [], vector_results: []});
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedSummaries, setExpandedSummaries] = useState<Set<string>>(new Set());
  const [llmAnalysis, setLlmAnalysis] = useState<string | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);

  const handleSearch = async () => {
    if (!billNumber.trim()) {
      setError('Please enter a bill number');
      return;
    }

    setIsLoading(true);
    setError(null);
    
    try {
      const results = await getBillSimilaritySearch(billType, billNumber.trim());
      console.log(results);
      setSearchResults(results);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to search for similar bills');
      setSearchResults({tfidf_results: [], vector_results: []});
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

  const handleLLMAnalysis = async () => {
    if (!searchResults || (searchResults.tfidf_results.length === 0 && searchResults.vector_results.length === 0)) {
      return;
    }

    setIsAnalyzing(true);
    setAnalysisError(null);
    
    try {
      // Construct the prompt with all the search results
      const prompt = `
Analyze the following similar bills found for ${billType}${billNumber}:

**TF-IDF Search Results:**
${searchResults.tfidf_results.map((bill, index) => 
  `${index + 1}. ${bill.bill_name}: ${bill.summary}`
).join('\n')}

**Semantic/Vector Search Results:**
${searchResults.vector_results.map((bill, index) => 
  `${index + 1}. ${bill.bill_name}: ${bill.summary}`
).join('\n')}

Please analyze these bills and answer the following questions:

1. Are these bills similar? Can they be combined into a single bill? Be specific about how they are similar and what aspects could be consolidated.

2. Do they have competing agendas? Are they in contradiction with each other? If they don't compete, explain that they are fine and affect unrelated matters.

Be very specific in your analysis about how the bills are either competing, similar, or unrelated. Focus on the actual policy content and legislative intent.`;

      console.log('Sending prompt to LLM:', prompt.substring(0, 200) + '...');
      const analysis = await askLLM(prompt);
      console.log('Received analysis:', analysis);
      setLlmAnalysis(analysis);
    } catch (err) {
      console.error('LLM Analysis error:', err);
      setAnalysisError(err instanceof Error ? err.message : 'Failed to analyze bills with LLM');
    } finally {
      setIsAnalyzing(false);
    }
  };

  const ResultsTable = ({ title, results }: { title: string; results: BillVectors[] }) => (
    <div className="flex-1 min-w-0">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">{title}</h3>
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full divide-y divide-gray-200 table-fixed">
            <thead className="bg-gray-50">
              <tr>
              <th className="w-12 px-2 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  #
                </th>
                <th className="w-20 px-2 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Bill
                </th>
                <th className="px-2 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Summary
                </th>
                <th className="w-16 px-2 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Action
                </th>

              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {results.length > 0 ? (
                results.map((result, index) => (
                  <tr key={index} className="hover:bg-gray-50">
                    <td className="px-2 py-3 whitespace-nowrap text-xs font-medium text-gray-900">
                      {index + 1}
                    </td>
                    <td className="px-2 py-3 text-xs font-medium text-gray-900">
                      <a
                        href={`https://www.capitol.hawaii.gov/session/measure_indiv.aspx?billtype=${result.bill_name.match(/^(HB|SB)/)?.[0] || 'HB'}&billnumber=${result.bill_name.match(/\d+/)?.[0] || ''}&year=2025`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-600 hover:text-blue-800 hover:underline transition-colors"
                        title={`View ${result.bill_name} on Hawaii State Legislature website`}
                      >
                        {result.bill_name}
                      </a>
                    </td>
                    <td className="px-2 py-3 text-xs text-gray-700">
                      <div className={expandedSummaries.has(`${title}-${result.bill_name}`) ? 'break-words text-xs leading-tight' : 'truncate'} title={result.summary}>
                        {result.summary}
                      </div>
                    </td>
                    <td className="px-2 py-3 whitespace-nowrap text-xs text-gray-500">
                      <button
                        onClick={() => toggleSummary(result.bill_name, title)}
                        className="inline-flex items-center px-1 py-1 text-xs font-medium text-blue-600 hover:text-blue-800 hover:bg-blue-50 rounded transition-colors"
                        title={expandedSummaries.has(`${title}-${result.bill_name}`) ? 'Collapse summary' : 'Expand summary'}
                      >
                        {expandedSummaries.has(`${title}-${result.bill_name}`) ? (
                          <ChevronUp className="w-3 h-3" />
                        ) : (
                          <ChevronDown className="w-3 h-3" />
                        )}
                      </button>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={4} className="px-2 py-4 text-center text-xs text-gray-500">
                    No results found
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );

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
      <div className="flex-1 overflow-auto p-6">
        {isLoading ? (
          <div className="flex items-center justify-center h-64">
            <div className="text-center">
              <Loader2 className="w-8 h-8 text-blue-600 animate-spin mx-auto mb-4" />
              <p className="text-gray-600">Searching for similar bills...</p>
            </div>
          </div>
        ) : searchResults ? (
          <div className="w-full max-w-none mx-auto space-y-6">
            <div className="flex flex-col space-y-4 lg:flex-row lg:space-y-0 lg:space-x-4">
              <ResultsTable title="Search Results 1" results={searchResults.tfidf_results} />
              <ResultsTable title="Search Results 2" results={searchResults.vector_results} />
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
                      ul: ({children}) => <ul className="list-disc list-inside mb-3 space-y-1">{children}</ul>,
                      ol: ({children}) => <ol className="list-decimal list-inside mb-3 space-y-1">{children}</ol>,
                      li: ({children}) => <li className="text-gray-700 ml-4">{children}</li>,
                      strong: ({children}) => <strong className="font-semibold text-gray-900">{children}</strong>,
                      em: ({children}) => <em className="italic">{children}</em>,
                    }}
                  >
                    {llmAnalysis}
                  </ReactMarkdown>
                </div>
              </div>
            )}
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
    </div>
  );
};

export default SimilarBillSearch;
