import { useState, useEffect, useCallback } from 'react';
import { MessageSquare, AlertCircle, Loader2, FileText, Search } from 'lucide-react';
// import CollectionsSidebar from './components/CollectionsSidebar';
import { ConversationChat } from './components/ConversationChat';
import CreateGroupModal from './components/CreateGroupModal';
import FiscalNoteGeneration from './components/FiscalNoteGeneration';
import SimilarBillSearch from './components/SimilarBillSearch';
import MobileBottomNav from './components/MobileBottomNav';
  import type { Collection } from './types';
import { getCollections } from './services/api';

type AppView = 'chat' | 'fiscal-note-generation' | 'similar-bill-search';

function App() {
  const [currentView, setCurrentView] = useState<AppView>('fiscal-note-generation');
  const [collections, setCollections] = useState<Collection[]>([]);
  const [collectionsLoading, setCollectionsLoading] = useState(true);
  const [collectionsError, setCollectionsError] = useState<string | null>(null);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);

  // Load collections on app start
  const loadCollections = useCallback(async () => {
    setCollectionsLoading(true);
    setCollectionsError(null);
    
    try {
      const response = await getCollections();
      
      // Transform the backend response to our Collection type
      const collectionsArray: Collection[] = Object.entries(response.collections).map(
        ([collectionName, totalCollections]) => ({
          name: collectionName,
          total_collections: totalCollections,
          status: "active",
          num_documents: 0,
        })
      );
      
      setCollections(collectionsArray);
      
      // Auto-select functionality is no longer needed since chat works across all collections
    } catch (err) {
      setCollectionsError(err instanceof Error ? err.message : 'Failed to load collections');
    } finally {
      setCollectionsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadCollections();
  }, [loadCollections]);

  // Handle collection selection
  // const handleCollectionSelect = useCallback((collectionId: string) => {
  //   setSelectedCollection(collectionId);
  //   // Don't clear messages when switching collections since chat works across all collections
  // }, []); // This function is no longer needed

  // Handle create group modal
  // const handleCreateGroup = useCallback(() => {
  //   setIsCreateModalOpen(true);
  // }, []);

  const handleCreateModalClose = useCallback(() => {
    setIsCreateModalOpen(false);
  }, []);

  const handleCreateSuccess = useCallback(() => {
    // Refresh collections to include the new group
    loadCollections();
  }, []);

  return (
    <div className="h-screen bg-gray-100 flex overflow-hidden">
      {/* Sidebar */}
      {/* <CollectionsSidebar
        collections={collections}
        loading={collectionsLoading}
        error={collectionsError}
        onRefresh={loadCollections}
        onCreateGroup={handleCreateGroup}
      /> */}

      {/* Main Content */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <header className="bg-white border-b border-gray-200 px-3 lg:px-6 py-3 lg:py-4">
          <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3 lg:gap-0">
            <div className="flex items-center space-x-2 lg:space-x-3">
              <div className={`rounded-lg p-1.5 lg:p-2 flex-shrink-0 ${
                currentView === 'chat' ? 'bg-blue-600' : 
                currentView === 'fiscal-note-generation' ? 'bg-green-600' : 'bg-purple-600'
              }`}>
                {currentView === 'chat' ? (
                  <MessageSquare className="w-5 h-5 lg:w-6 lg:h-6 text-white" />
                ) : currentView === 'fiscal-note-generation' ? (
                  <FileText className="w-5 h-5 lg:w-6 lg:h-6 text-white" />
                ) : (
                  <Search className="w-5 h-5 lg:w-6 lg:h-6 text-white" />
                )}
              </div>
              <div className="min-w-0">
                <h1 className="text-base lg:text-xl font-bold text-gray-900 truncate">
                  {currentView === 'chat' && 'FinBot'}
                  {currentView === 'fiscal-note-generation' && 'Fiscal Note Generation'}
                  {currentView === 'similar-bill-search' && 'Similar Bill Search'}
                </h1>
                <p className="text-xs lg:text-sm text-gray-500 line-clamp-2 lg:line-clamp-1">
                  {currentView === 'chat'
                    ? `Ask questions about the state budget and the state of Hawaii. This interface has access to the <sappropriation bill 300, statutes, budget worksheets, and bills.`
                    : currentView === 'fiscal-note-generation'
                    ? 'Upload documents and analyze using selected collections'
                    : currentView === 'similar-bill-search'
                    ? 'Search for bills similar to a specific bill using advanced algorithms'
                    : 'Generate a fiscal note for a specific bill'
                  }
                </p>
              </div>
            </div>
            
            {/* Navigation - Hidden on mobile, shown on desktop */}
            <div className="hidden lg:flex items-center space-x-4 overflow-x-auto">
              <nav className="flex space-x-1 flex-shrink-0">
                <button
                  onClick={() => setCurrentView('fiscal-note-generation')}
                  className={`px-2 lg:px-3 py-1.5 lg:py-2 rounded-lg text-xs lg:text-sm font-medium transition-colors whitespace-nowrap ${
                    currentView === 'fiscal-note-generation'
                      ? 'bg-yellow-100 text-yellow-700'
                      : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
                  }`}
                >
                  <FileText className="w-3 h-3 lg:w-4 lg:h-4 inline mr-1 lg:mr-2" />
                  <span className="hidden sm:inline">Fiscal Note Generation</span>
                  <span className="sm:hidden">Fiscal Note</span>
                </button>
                <button
                  onClick={() => setCurrentView('similar-bill-search')}
                  className={`px-2 lg:px-3 py-1.5 lg:py-2 rounded-lg text-xs lg:text-sm font-medium transition-colors whitespace-nowrap ${
                    currentView === 'similar-bill-search'
                      ? 'bg-purple-100 text-purple-700'
                      : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
                  }`}
                >
                  <Search className="w-3 h-3 lg:w-4 lg:h-4 inline mr-1 lg:mr-2" />
                  <span className="hidden sm:inline">Similar Bill Search</span>
                  <span className="sm:hidden">Search</span>
                </button>
              </nav>
              
              {/* Status Indicator */}
              <div className="flex items-center space-x-2">
              {collectionsLoading && (
                <div className="flex items-center space-x-2 text-gray-500">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span className="text-sm">Loading...</span>
                </div>
              )}
              
              {!collectionsLoading && collections.length > 0 && (
                <div className="flex items-center space-x-2 text-green-600">
                  <div className="w-2 h-2 bg-green-400 rounded-full"></div>
                  <span className="text-sm">Connected</span>
                </div>
              )}
              
              {collectionsError && (
                <div className="flex items-center space-x-2 text-red-600">
                  <AlertCircle className="w-4 h-4" />
                  <span className="text-sm">Connection Error</span>
                </div>
              )}
              </div>
            </div>
          </div>
        </header>

        {/* Main Content - Add bottom padding on mobile for navbar */}
        <div className="flex-1 overflow-hidden pb-16 lg:pb-0">
          {currentView === 'fiscal-note-generation' ? (
            <FiscalNoteGeneration />
          ) : currentView === 'similar-bill-search' ? (
            <SimilarBillSearch />
          ) : (
            collectionsLoading ? (
            <div className="flex items-center justify-center h-full">
              <div className="text-center">
                <Loader2 className="w-8 h-8 text-blue-600 animate-spin mx-auto mb-4" />
                <p className="text-gray-600">Loading collections...</p>
              </div>
            </div>
          ) : collectionsError ? (
            <div className="flex items-center justify-center h-full">
              <div className="text-center max-w-md">
                <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
                <h3 className="text-lg font-semibold text-gray-900 mb-2">Connection Error</h3>
                <p className="text-gray-600 mb-4">{collectionsError}</p>
                <button
                  onClick={loadCollections}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                >
                  Try Again
                </button>
              </div>
            </div>
          ) : collections.length === 0 ? (
            <div className="flex items-center justify-center h-full">
              <div className="text-center max-w-md">
                <MessageSquare className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                <h3 className="text-lg font-semibold text-gray-900 mb-2">No Collections Found</h3>
                <p className="text-gray-600 mb-4">
                  No document collections are available. Make sure the backend has collections with documents.
                </p>
                <button
                  onClick={loadCollections}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                >
                  Refresh
                </button>
              </div>
            </div>
          ) : (
              <ConversationChat className="h-full" />
            )
          )}
        </div>
      </div>

      {/* Create Group Modal */}
      <CreateGroupModal
        isOpen={isCreateModalOpen}
        onClose={handleCreateModalClose}
        onSuccess={handleCreateSuccess}
      />

      {/* Mobile Bottom Navigation */}
      <MobileBottomNav
        currentView={currentView === 'chat' ? 'fiscal-note-generation' : currentView}
        onViewChange={(view) => setCurrentView(view)}
      />
    </div>
  );
}

export default App;
