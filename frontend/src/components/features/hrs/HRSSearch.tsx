import { useState, useLayoutEffect, useEffect } from "react";
import { HRSTextView } from "./HRSTextView";
import { HRSIndexView, type HRSFilter, type HRSIndex } from './HRSIndexView';
import { MatchingStatutes } from './MatchingStatutes';
import { getHRSIndex, getHRSRaw, searchHRS } from '../../../services/api';
import { hrsCache } from '../../../services/hrsCache';

const HRSSearch = () => {

  const [isMatchesExpanded, setIsMatchesExpanded] = useState<boolean>(true);
  const [isIndexExpanded, setIsIndexExpanded] = useState<boolean>(true);
  const [contentHeight, setContentHeight] = useState('100vh');
  const [filter, setFilter] = useState<HRSFilter>({});
  const [link, setLink] = useState<HRSFilter>({});
  const [index, setIndex] = useState<HRSIndex | null>(null);
  const [searchText, setSearchText] = useState<string>("");
  const [matchingStatutes, setMatchingStatutes] = useState<[string, string, string][] | null>(null);
  const [selectedMatch, setSelectedMatch] = useState<{ statute: [string, string, string], text: string } | null>(null);
  const [lastSearchValue, setLastSearchValue] = useState<string | null>(null);


  async function openRawDataTab() {
    const { volume, chapter, section } = filter;
    const raw = await getHRSRaw(volume, chapter, section);
    const blob = new Blob([raw], { type: 'text/plain' });

    const url = URL.createObjectURL(blob);
    window.open(url, '_blank');
  }

  async function searchDocument(text: string) {
    setSelectedMatch(null);
    const { volume, chapter, section } = filter;
    const found = await searchHRS(text, volume, chapter, section);
    setMatchingStatutes(found);

    // Prefetch content for top results (async, non-blocking)
    if (found && found.length > 0) {
      // Prefetch top 10 results
      const toPrefetch = found.slice(0, 10).map(row => ({
        volume: row[0],
        chapter: row[1],
        section: row[2]
      }));
      hrsCache.prefetch(toPrefetch);
    }
    setLastSearchValue(text);
  }

  useEffect(() => {
    if(lastSearchValue) {
      searchDocument(lastSearchValue);
    }
  }, [filter]);

  const handleFilterChange = (newFilter: HRSFilter) => {
    setFilter(newFilter);
  };

  const handleLinkChange = (newFilter: HRSFilter) => {
    setLink(newFilter);
  };

  useEffect(() => {
    const getData = async () => {
      const hrsindex = await getHRSIndex();
      setIndex(hrsindex);
    }
    getData();
  }, []);


  useLayoutEffect(() => {
    const header = document.querySelector('header');
    if (header) {
      const calculateHeight = () => {
        const headerHeight = header.offsetHeight;
        setContentHeight(`calc(100vh - ${headerHeight}px)`);
      };

      calculateHeight();
      const resizeObserver = new ResizeObserver(() => {
        calculateHeight();
      });

      resizeObserver.observe(header);
      return () => resizeObserver.disconnect();
    }
  }, []);

  return (
    <div className="flex flex-col"
      style={{
        height: contentHeight
      }}>
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
                title="More options coming soon!"
                id="searchType"
                className="block w-50 px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                disabled
              >
                {/* <option value="keyword">Find in Document</option> */}
                <option value="keyword">More options coming soon!</option>
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
                value={searchText}
                onChange={(e) => setSearchText(e.target.value)}
                placeholder="Enter search term"
                className="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
              />
            </div>

            {/* Search Button */}
            <div className="flex-shrink-0 pt-6">
              <button
                className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
                onClick={() => {searchDocument(searchText)}}
                disabled={searchText ? false : true}
              >
                Search
              </button>
            </div>

            <div className="flex-shrink-0 pt-6">
              <button
                className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
                onClick={openRawDataTab}
              >
                View Raw Text
              </button>
            </div>
          </div>
        </div>
      </div>



      <div className="flex flex-1  bg-gray-50 overflow-x-hidden">
        {/* Left Sidebar - Hidden on mobile, visible on desktop */}
        <div className="hidden w-80 lg:block min-w-0 bg-white shadow-lg border-r border-gray-200 flex flex-col flex-shrink-0 sticky top-0 overflow-y-auto scroll-smooth mobile-scroll">
          <div className="p-6 border-b border-gray-200">
            <div className="flex items-center justify-between">
              <h1 className="text-2xl font-bold text-gray-900">Statutes Index</h1>
              <div className="flex items-center space-x-2">
              </div>
            </div>
          </div>

          <div className="flex-1 p-6 space-y-4 overflow-y-auto scroll-smooth mobile-scroll pb-32">

            {/* Matching Statutes Table */}




            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Matching Statutes
                </label>
                <button
                  onClick={() => setIsMatchesExpanded(!isMatchesExpanded)}
                  className="text-sm text-blue-600 hover:text-blue-800 flex items-center space-x-1"
                >
                  <span>{isMatchesExpanded ? 'Collapse' : 'Expand'}</span>
                  <svg
                    className={`w-4 h-4 transform transition-transform ${isMatchesExpanded ? 'rotate-180' : ''}`}
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </button>
              </div>

              {isMatchesExpanded && (
                <div>
                  <MatchingStatutes
                    data={matchingStatutes}
                    onRowClick={(statute) => setSelectedMatch({ statute, text: searchText })}
                  />
                </div>
              )}
            </div>

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
                  <HRSIndexView
                    index={index}
                    selectedFilter={filter}
                    onFilterChange={handleFilterChange}
                    onLinkChange={handleLinkChange}
                  />
                </div>
              )}
            </div>
          </div>
        </div>





        <HRSTextView
          selectedMatch={selectedMatch}
          filter={filter}
          link={link}>
        </HRSTextView>



      </div>







    </div>

  );
};

export default HRSSearch;