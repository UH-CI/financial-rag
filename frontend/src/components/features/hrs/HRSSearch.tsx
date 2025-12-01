import { useState } from "react";

const HRSSearch = () => {

  const [isIndexExpanded, setIsIndexExpanded] = useState<boolean>(false);

  return (
    <div>
      <div className="bg-white border-b border-gray-200 p-6">
        <div className="max-w-4xl mx-auto">
          
          <div className="flex items-center space-x-4">
          <h2 className="text-2xl font-bold text-gray-900 pt-5">HRS Search</h2>

            {/* Search Type Dropdown */}
            <div className="flex-shrink-0">
              <label htmlFor="searchType" className="block text-sm font-medium text-gray-700 mb-1">
                Search Type
              </label>
              <select
                id="searchType"
                // value={billType}
                // onChange={(e) => setBillType(e.target.value as 'HB' | 'SB')}
                className="block w-50 px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
              >
                <option value="keyword">Find in Document</option>
                <option value="keyword">Keyword Search</option>
                <option value="semantic">Semantic Search</option>
              </select>
            </div>

            {/* Search Input */}
            <div className="flex-1 max-w-xs">
              <label htmlFor="searchTerm" className="block text-sm font-medium text-gray-700 mb-1">
                Search Term
              </label>
              <input
                type="string"
                id="searchBox"
                // value={billNumber}
                // onChange={(e) => setBillNumber(e.target.value)}
                placeholder="Enter search term"
                className="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
              />
            </div>

            {/* Search Button */}
            <div className="flex-shrink-0 pt-6">
              <button
                className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Search
              </button>
            </div>

            <div className="flex-shrink-0 pt-6">
              {/* <Link to="/page2"> */}
              <button
                className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                View Raw Text
              </button>
            </div>
          </div>
        </div>
      </div>



























      <div className="flex h-screen w-screen bg-gray-50 overflow-x-hidden">
      {/* Left Sidebar - Hidden on mobile, visible on desktop */}
      <div className="hidden lg:block w-80 min-w-0 bg-white shadow-lg border-r border-gray-200 flex flex-col flex-shrink-0 sticky top-0 h-screen overflow-y-auto scroll-smooth mobile-scroll">
        <div className="p-6 border-b border-gray-200">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-bold text-gray-900">Statutes Index</h1>
            <div className="flex items-center space-x-2">
            </div>
          </div>
        </div>

        <div className="flex-1 p-6 space-y-4 overflow-y-auto scroll-smooth mobile-scroll pb-32">

          {/* Matching Statutes Table */}
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Matching Statutes
          </label>


           {/* Index Filter Section */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="block text-sm font-medium text-gray-700">
                HRS Index View
              </label>
              <button
                onClick={() => setIsIndexExpanded(!isIndexExpanded)}
                className="text-sm text-blue-600 hover:text-blue-800 flex items-center space-x-1"
              >
                <span>{isIndexExpanded ? 'Collapse' : 'Expand'}</span>
                <svg 
                  className={`w-4 h-4 transform transition-transform ${isIndexExpanded ? 'rotate-180' : ''}`} 
                  fill="none" 
                  stroke="currentColor" 
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
            </div>
            
            {isIndexExpanded && (
              <div>
                Index
              </div>
            )}
          </div>
        </div>


       


      </div>


      




      {/* Main Content Area - Desktop */}
      <div className="flex-1 flex flex-col min-w-0">
      <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
        </div>
      </div>
    </div>




















    </div>
   
  );
};

export default HRSSearch;