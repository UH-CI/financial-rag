import { useEffect, useState, useRef } from "react";
import { getFiscalNoteFiles, createFiscalNote, getFiscalNote, deleteFiscalNote, getFiscalNoteFilesSeptember, getFiscalNoteSeptember } from "../services/api";
import { Loader2 } from "lucide-react";
import FiscalNoteViewer from "./FiscalNoteViewer";

interface CreateFiscalNoteForm {
  billType: 'HB' | 'SB';
  billNumber: string;
  year: '2025';
}

const FiscalNoteGeneration = () => {
  const [fiscalNoteFiles, setFiscalNoteFiles] = useState<{ name: string; status: string }[]>([]);
  const [fiscalNoteFilesSeptember, setFiscalNoteFilesSeptember] = useState<{ name: string; status: string }[]>([]);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [fiscalNoteHtml, setFiscalNoteHtml] = useState<string>('');
  const [selectedFiscalNote, setSelectedFiscalNote] = useState<string>('');
  const [useNewViewer, setUseNewViewer] = useState<boolean>(true);
  const [formData, setFormData] = useState<CreateFiscalNoteForm>({
    billType: 'HB',
    billNumber: '',
    year: '2025'
  });
  const [jobProgress, setJobProgress] = useState<{ [jobId: string]: string }>({});
  const [jobErrors, setJobErrors] = useState<{ [jobId: string]: boolean }>({});
  const [loadingFiscalNote, setLoadingFiscalNote] = useState<boolean>(false);
  const [isSeptemberExpanded, setIsSeptemberExpanded] = useState<boolean>(false);
  const [wsConnected, setWsConnected] = useState<boolean>(false);
  const wsRef = useRef<WebSocket | null>(null);
  const pendingRequestsRef = useRef<Set<string>>(new Set());

  // Move fetch functions outside useEffect so WebSocket can access them
  const fetchFiscalNoteFiles = async () => {
    try {
      const response = await getFiscalNoteFiles();
      console.log(response);
      setFiscalNoteFiles(response as { name: string; status: string }[]);
    } catch (error) {
      console.error('Error fetching fiscal note files:', error);
    }
  }

  const fetchFiscalNoteFilesSeptember = async () => {
    try {
      const response = await getFiscalNoteFilesSeptember();
      console.log('September files:', response);
      setFiscalNoteFilesSeptember(response as { name: string; status: string }[]);
    } catch (error) {
      console.error('Error fetching September fiscal note files:', error);
    }
  }

  useEffect(() => {
    fetchFiscalNoteFiles();
    fetchFiscalNoteFilesSeptember();

    // WebSocket connection
    const connectWebSocket = () => {
      let wsUrl;
      if (window.location.hostname === 'localhost'){
         wsUrl = 'ws://localhost:8200/ws';
        console.log('Attempting to connect to WebSocket:', wsUrl);
      }
      else {
        wsUrl = import.meta.env.VITE_WS_URL || 'wss://finbot.its.hawaii.edu/ws';
      }
      console.log('Attempting to connect to WebSocket:', wsUrl);

      try {
        wsRef.current = new WebSocket(wsUrl);

        wsRef.current.onopen = () => {
          console.log('✅ WebSocket connected successfully');
          setWsConnected(true);
        };

        wsRef.current.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            console.log('📨 WebSocket message received:', data);

            if (data.type === 'job_progress') {
              setJobProgress(prev => ({
                ...prev,
                [data.job_id]: data.message
              }));
            } else if (data.type === 'job_completed') {
              setJobProgress(prev => {
                const newProgress = { ...prev };
                delete newProgress[data.job_id];
                return newProgress;
              });
              setJobErrors(prev => {
                const newErrors = { ...prev };
                delete newErrors[data.job_id];
                return newErrors;
              });

              // Refresh the fiscal note files list
              console.log('🔄 Job completed, refreshing fiscal note files...');
              fetchFiscalNoteFiles();

              // Show success notification
              alert(data.message);
            } else if (data.type === 'job_error') {
              setJobProgress(prev => {
                const newProgress = { ...prev };
                delete newProgress[data.job_id];
                return newProgress;
              });
              setJobErrors(prev => ({
                ...prev,
                [data.job_id]: true
              }));

              // Show error notification
              alert(data.message);
            }
          } catch (error) {
            console.error('Error parsing WebSocket message:', error);
          }
        };

        wsRef.current.onclose = (event) => {
          console.log('🔌 WebSocket disconnected. Code:', event.code, 'Reason:', event.reason);
          setWsConnected(false);
          if (event.code !== 1000 && event.code !== 1001) { // Don't reconnect if it was a normal closure or going away
            console.log('🔄 Attempting to reconnect in 5 seconds...');
            setTimeout(() => {
              // Only reconnect if the component is still mounted
              if (wsRef.current === null || wsRef.current.readyState === WebSocket.CLOSED) {
                connectWebSocket();
              }
            }, 5000);
          }
        };

        wsRef.current.onerror = (error) => {
          console.error('❌ WebSocket error:', error);
          console.log('💡 Make sure the FastAPI server is running with WebSocket support');
          setWsConnected(false);
        };
      } catch (error) {
        console.error('❌ Failed to create WebSocket connection:', error);
        console.log('🔄 Retrying in 5 seconds...');
        setTimeout(connectWebSocket, 5000);
      }
    };

    connectWebSocket();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  const handleCreateFiscalNote = async () => {
    if (!formData.billNumber.trim()) {
      alert('Please enter a bill number');
      return;
    }

    // Prevent multiple submissions
    if (isCreating) {
      console.log('⚠️ Already creating a fiscal note, please wait...');
      return;
    }

    // Check if this fiscal note already exists
    const jobId = `${formData.billType}_${formData.billNumber}_${formData.year}`;
    const existingJob = fiscalNoteFiles.find(file => file.name === jobId);
    if (existingJob) {
      alert(`A fiscal note for ${formData.billType} ${formData.billNumber} (${formData.year}) already exists or is being generated.`);
      return;
    }

    setIsCreating(true);
    
    // Store current form data to avoid race conditions
    const currentFormData = { ...formData };
    const requestId = `${currentFormData.billType}_${currentFormData.billNumber}_${Date.now()}`;
    
    try {
      console.log(`🚀 [${requestId}] Starting fiscal note creation...`, currentFormData);
      console.log(`📡 WebSocket connected: ${wsConnected}, WebSocket state: ${wsRef.current?.readyState}`);
      console.log(`📊 Pending requests: ${Array.from(pendingRequestsRef.current).join(', ')}`);
      
      // Track this request
      pendingRequestsRef.current.add(requestId);
      
      const result = await createFiscalNote(
        currentFormData.billType, 
        currentFormData.billNumber, 
        currentFormData.year
      );
      
      // Remove from pending requests
      pendingRequestsRef.current.delete(requestId);
      
      console.log(`✅ [${requestId}] Create fiscal note response:`, result);

      if (result.success) {
        // Add to the list with the job_id first
        if (result.job_id) {
          setFiscalNoteFiles(prev => [...prev, { name: result.job_id!, status: 'generating' }]);
        }
        
        // Close modal and reset form immediately
        setIsCreateModalOpen(false);
        setFormData({ billType: 'HB', billNumber: '', year: '2025' });
        
        // Show success message after UI updates
        alert('Fiscal note generation started! This will take 5-10 minutes to create, depending on how complex the bill is.');
      } else {
        alert(result.message || 'Failed to start fiscal note generation');
      }
      

    } catch (error: any) {
      console.error('❌ Error creating fiscal note:', error);
      
      // More specific error handling
      if (error.name === 'AbortError') {
        alert('Request timed out: The server may be busy. Please try again in a moment.');
      } else if (error.message?.includes('Failed to fetch')) {
        alert('Connection error: Please check if the server is running and try again.');
      } else {
        alert(`Error creating fiscal note: ${error.message || 'Unknown error'}. Please try again.`);
      }
    } finally {
      // Always reset the creating state and clean up pending requests
      pendingRequestsRef.current.delete(requestId);
      setIsCreating(false);
    }
  };

  const handleSelectFile = async (fileName: string) => {
    try {
      setLoadingFiscalNote(true);
      // Extract bill type and number from filename (assuming format like "HB_400_2025")
      const parts = fileName.split('_');
      if (parts.length >= 2) {
        const billType = parts[0] as 'HB' | 'SB';
        const billNumber = parts[1];
        const year = parts[2] || '2025';
        setSelectedFiscalNote(fileName);
        const response = await getFiscalNote(billType, billNumber, year);

        // Check if response is a message object (job in progress) or HTML content
        if (typeof response === 'object' && 'message' in response) {
          setFiscalNoteHtml(`
            <div class="text-center p-8">
              <div class="inline-flex items-center px-4 py-2 font-semibold leading-6 text-sm shadow rounded-md text-blue-500 bg-blue-100">
                <svg class="animate-spin -ml-1 mr-3 h-5 w-5 text-blue-500" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                ${response.message}
              </div>
            </div>
          `);
        } else {
          setFiscalNoteHtml(response as string);
        }
      }
    } catch (error) {
      console.error('Error loading fiscal note:', error);
      alert('Error loading fiscal note. Please try again.');
    } finally {
      setLoadingFiscalNote(false);
    }
  };

  const handleSelectSeptemberFile = async (fileName: string) => {
    try {
      setLoadingFiscalNote(true);
      // Extract bill type and number from filename (assuming format like "HB_400_2025")
      const parts = fileName.split('_');
      if (parts.length >= 2) {
        const billType = parts[0] as 'HB' | 'SB';
        const billNumber = parts[1];
        const year = parts[2] || '2025';
        setSelectedFiscalNote(fileName);
        const response = await getFiscalNoteSeptember(billType, billNumber, year);

        // Check if response is a message object (job in progress) or HTML content
        if (typeof response === 'object' && 'message' in response) {
          setFiscalNoteHtml(`
            <div class="text-center p-8">
              <div class="inline-flex items-center px-4 py-2 font-semibold leading-6 text-sm shadow rounded-md text-blue-500 bg-blue-100">
                <svg class="animate-spin -ml-1 mr-3 h-5 w-5 text-blue-500" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                ${response.message}
              </div>
            </div>
          `);
        } else {
          setFiscalNoteHtml(response as string);
        }
      }
    } catch (error) {
      console.error('Error loading September fiscal note:', error);
      alert('Error loading September fiscal note. Please try again.');
    } finally {
      setLoadingFiscalNote(false);
    }
  };

  const handleDeleteFile = async (fileName: string) => {
    if (!confirm(`Are you sure you want to delete ${fileName}? This action cannot be undone.`)) {
      return;
    }

    try {
      // Extract bill type and number from filename
      const parts = fileName.split('_');
      if (parts.length >= 2) {
        const billType = parts[0] as 'HB' | 'SB';
        const billNumber = parts[1];
        const year = parts[2] || '2025';

        await deleteFiscalNote(billType, billNumber, year);

        // Clear the HTML if this was the selected file
        setFiscalNoteHtml('');

        // Refresh the fiscal note files list
        const updatedFiles = await getFiscalNoteFiles();
        setFiscalNoteFiles(updatedFiles as { name: string; status: string }[]);

      }
    } catch (error) {
      console.error('Error deleting fiscal note:', error);
      alert('Error deleting fiscal note. Please try again.');
    }
  };

  return (
    <div className="flex h-screen w-screen bg-gray-50 overflow-x-hidden">
      {/* Left Sidebar */}
      <div className="w-80 min-w-0 bg-white shadow-lg border-r border-gray-200 flex flex-col flex-shrink-0 sticky top-0 h-screen overflow-y-auto">
        <div className="p-6 border-b border-gray-200">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-bold text-gray-900">Fiscal Note Generation</h1>
            <div className="flex items-center space-x-2">
              <div className={`w-3 h-3 rounded-full ${wsConnected ? 'bg-green-500' : 'bg-red-500'}`}></div>
              <span className="text-sm text-gray-600">
                {wsConnected ? 'Connected' : 'Disconnected'}
              </span>
            </div>
          </div>
        </div>

        <div className="flex-1 p-6 space-y-4 overflow-y-auto pb-32">
          {/* Create New Button */}
          <button
            onClick={() => setIsCreateModalOpen(true)}
            className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-3 px-4 rounded-lg transition-colors duration-200 flex items-center justify-center space-x-2"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            <span>Create New Fiscal Note</span>
          </button>

          {/* Fiscal Note Files Table */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Available Fiscal Notes
            </label>
            <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Status
                    </th>

                    <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Bill
                    </th>
                    <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {fiscalNoteFiles.map((file) => (
                    <tr key={file.name} className={`hover:bg-gray-50 ${file.name == selectedFiscalNote ? 'bg-blue-100' : ''}`}>

                      <td className="px-3 py-2 whitespace-nowrap relative z-[10000]">
                        <div className="flex flex-col">
                          {/* Status Button with Tooltip */}
                          <div className="relative group">
                            <button
                              className={`w-6 h-6 rounded-full flex items-center justify-center text-white text-sm font-bold ${jobErrors[file.name]
                                  ? 'bg-red-500 hover:bg-red-600'
                                  : file.status === 'error'
                                    ? 'bg-red-500 hover:bg-red-600'
                                  : file.status === 'ready'
                                    ? 'bg-green-500 hover:bg-green-600'
                                    : 'bg-yellow-500 hover:bg-yellow-600'
                                }`}
                            >
                              {jobErrors[file.name] ? '!' : file.status === 'ready' ? '✓' : (file.status === 'error' ? '✗' : '⧗')}
                            </button>

                            {/* Tooltip */}
                            <div className="absolute bottom-full left-1/2 transform -translate-x-2 mb-2 px-2 py-1 text-xs text-white bg-gray-800 rounded opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none whitespace-nowrap z-[99999] shadow-lg border border-gray-700">
                              {jobErrors[file.name]
                                ? 'Error - Generation failed'
                                : file.status === 'error'
                                  ? 'Error - Generation failed'
                                : file.status === 'ready'
                                  ? 'Ready - Click to view'
                                  : 'In Progress - ' + (jobProgress[file.name] ? jobProgress[file.name] : '')}
                            </div>
                          </div>

                          {/* Progress message */}
                          {/* {jobProgress[file.name] && (
                            <span className="text-xs text-gray-500 mt-1 max-w-32 truncate">
                              {jobProgress[file.name]}
                            </span>
                          )} */}
                        </div>
                      </td>
                      <td className="px-3 py-2 whitespace-nowrap text-sm text-gray-500 cursor-pointer max-w-26 truncate" onClick={() => handleSelectFile(file.name)}>
                        {file.name}
                      </td>
                      <td className="px-3 py-2 whitespace-nowrap text-sm text-gray-500">
                        <div className="flex items-center space-x-2">

                          {/* Delete Button */}
                          <button
                            onClick={() => handleDeleteFile(file.name)}
                            className="text-red-600 hover:text-red-900 p-1 rounded hover:bg-red-50 transition-colors duration-200"
                            title="Delete fiscal note"
                          >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                            </svg>
                          </button>
                          {/* View Button */}
                          {/* <button
                            onClick={() => handleSelectFile(file.name)}
                            disabled={file.status === 'generating' || jobErrors[file.name]}
                            className={`text-blue-600 hover:text-blue-900 font-medium ${
                              (file.status === 'generating' || jobErrors[file.name]) ? 'opacity-50 cursor-not-allowed' : ''
                            }`}
                            title={file.status === 'ready' ? 'View fiscal note' : 'Cannot view while generating or in error state'}
                          >
                            {file.status === 'ready' ? 'View' : 'Generating...'}
                          </button> */}

                        </div>
                      </td>

                    </tr>
                  ))}
                </tbody>
              </table>
              {fiscalNoteFiles.length === 0 && (
                <div className="text-center py-4 text-gray-500 text-sm">
                  No fiscal notes available
                </div>
              )}
            </div>
          </div>

          {/* September Archive Section */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="block text-sm font-medium text-gray-700">
                September Archive
              </label>
              <button
                onClick={() => setIsSeptemberExpanded(!isSeptemberExpanded)}
                className="text-sm text-blue-600 hover:text-blue-800 flex items-center space-x-1"
              >
                <span>{isSeptemberExpanded ? 'Collapse' : 'Expand'}</span>
                <svg 
                  className={`w-4 h-4 transform transition-transform ${isSeptemberExpanded ? 'rotate-180' : ''}`} 
                  fill="none" 
                  stroke="currentColor" 
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
            </div>
            
            {isSeptemberExpanded && (
              <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Status
                      </th>
                      <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Bill
                      </th>
                      <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Actions
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {fiscalNoteFilesSeptember.map((file) => (
                      <tr key={file.name} className={`hover:bg-gray-50 ${file.name == selectedFiscalNote ? 'bg-blue-100' : ''}`}>
                        <td className="px-3 py-2 whitespace-nowrap">
                          <div className="flex flex-col">
                            <div className="relative group">
                              <button
                                className={`w-6 h-6 rounded-full flex items-center justify-center text-white text-sm font-bold bg-green-500 hover:bg-green-600
                                `}
                              >
                                {file.status === 'ready' ? '✓' : (file.status === 'error' ? '✗' : '⧗')}
                              </button>
                              <div className="absolute bottom-full left-1/2 transform -translate-x-2 mb-2 px-2 py-1 text-xs text-white bg-gray-800 rounded opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none whitespace-nowrap z-[99999] shadow-lg border border-gray-700">
                                Ready - Click to view
                              </div>
                            </div>
                          </div>
                        </td>
                        <td className="px-3 py-2 whitespace-nowrap text-sm text-gray-500 cursor-pointer max-w-26 truncate" onClick={() => handleSelectSeptemberFile(file.name)}>
                          {file.name}
                        </td>
                        <td className="px-3 py-2 whitespace-nowrap text-sm text-gray-500">
                          <div className="flex items-center space-x-2">
                            <button
                              onClick={() => handleSelectSeptemberFile(file.name)}
                              disabled={file.status !== 'ready'}
                              className={`text-blue-600 hover:text-blue-900 p-1 rounded hover:bg-blue-50 transition-colors duration-200 ${
                                file.status !== 'ready' ? 'opacity-50 cursor-not-allowed' : ''
                              }`}
                              title={file.status === 'ready' ? 'View fiscal note' : 'Cannot view - not ready'}
                            >
                              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                              </svg>
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {fiscalNoteFilesSeptember.length === 0 && (
                  <div className="text-center py-4 text-gray-500 text-sm">
                    No September fiscal notes available
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0">
        {selectedFiscalNote && useNewViewer ? (
          <div className="flex-1 h-full overflow-hidden">
            {(() => {
              const parts = selectedFiscalNote.split('_');
              if (parts.length >= 2) {
                const billType = parts[0] as 'HB' | 'SB';
                const billNumber = parts[1];
                const year = parts[2] || '2025';
                return (
                  <FiscalNoteViewer
                    billType={billType}
                    billNumber={billNumber}
                    year={year}
                  />
                );
              }
              return (
                <div className="flex items-center justify-center h-64">
                  <div className="text-center">
                    <div className="text-red-600 mb-2">⚠️ Error</div>
                    <div className="text-gray-600">Invalid fiscal note format</div>
                  </div>
                </div>
              );
            })()}
          </div>
        ) : fiscalNoteHtml ? (
          <div className="flex-1 overflow-auto p-6">
            {loadingFiscalNote && (
              <div className="flex items-center justify-center">
                <Loader2 className="w-8 h-8 text-blue-600 animate-spin" />
                <p className="ml-2">Generating fiscal note...</p>
              </div>
            )}
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900">Legacy Viewer</h2>
              <button
                onClick={() => setUseNewViewer(true)}
                className="px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
              >
                Switch to New Viewer
              </button>
            </div>
            <div
              className="prose max-w-none"
              dangerouslySetInnerHTML={{ __html: fiscalNoteHtml }}
            />
          </div>
        ) : (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <h3 className="mt-2 text-sm font-medium text-gray-900">No fiscal note selected</h3>
              <p className="mt-1 text-sm text-gray-500">
                Select an existing fiscal note from the sidebar or create a new one.
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Create Modal */}
      {isCreateModalOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4">
            <div className="p-6">
              <h2 className="text-xl font-bold text-gray-900 mb-4">Create New Fiscal Note</h2>

              <div className="space-y-4">
                {/* Bill Type */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Bill Type
                  </label>
                  <select
                    value={formData.billType}
                    onChange={(e) => setFormData({ ...formData, billType: e.target.value as 'HB' | 'SB' })}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  >
                    <option value="HB">HB (House Bill)</option>
                    <option value="SB">SB (Senate Bill)</option>
                  </select>
                </div>

                {/* Bill Number */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Bill Number
                  </label>
                  <input
                    type="text"
                    value={formData.billNumber}
                    onChange={(e) => setFormData({ ...formData, billNumber: e.target.value })}
                    placeholder="e.g., 400"
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                </div>

                {/* Year */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Year
                  </label>
                  <select
                    value={formData.year}
                    onChange={(e) => setFormData({ ...formData, year: e.target.value as '2025' })}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  >
                    <option value="2025">2025</option>
                  </select>
                </div>
              </div>

              <div className="mt-6 flex space-x-3">
                <button
                  onClick={() => {
                    setIsCreateModalOpen(false);
                    setFormData({ billType: 'HB', billNumber: '', year: '2025' });
                  }}
                  className="flex-1 bg-gray-300 hover:bg-gray-400 text-gray-700 font-medium py-2 px-4 rounded-lg transition-colors duration-200"
                >
                  Cancel
                </button>
                <button
                  onClick={handleCreateFiscalNote}
                  disabled={isCreating || !formData.billNumber.trim()}
                  className="flex-1 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white font-medium py-2 px-4 rounded-lg transition-colors duration-200 flex items-center justify-center space-x-2"
                >
                  {isCreating ? (
                    <>
                      <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      <span>Creating...</span>
                    </>
                  ) : (
                    <span>Create</span>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default FiscalNoteGeneration;