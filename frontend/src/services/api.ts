import axios from 'axios';
import type {
  SearchResponse,
  QuestionResponse,
  ApiError,
  CollectionsResponse,
  Bill,
  FiscalNote,
  BillSimilaritySearch,
  FiscalNoteData
} from '../types';
import type { HRSIndex } from '../components/features/hrs/HRSIndexView';

// API configuration
// For production deployment, use the same domain with /api path
let API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'https://finbot.its.hawaii.edu/api';
if (window.location.hostname === 'localhost') {
  API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8200';
}
console.log(window.location.hostname, API_BASE_URL)
const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
  maxRedirects: 5,
});

// Add request interceptor for debugging (excluding fiscal note creation which uses fetch)
api.interceptors.request.use(
  (config) => {
    if (!config.url?.includes('generate-fiscal-note')) {
      console.log(`📡 Outgoing axios request: ${config.method?.toUpperCase()} ${config.url}`, config.params);
    }
    return config;
  },
  (error) => {
    console.error('❌ Request interceptor error:', error);
    return Promise.reject(error);
  }
);

// Add response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      // Server responded with error status
      const apiError: ApiError = {
        message: error.response.data?.detail || error.response.data?.message || 'Server error',
        code: error.response.status.toString(),
        details: error.response.data,
      };
      throw apiError;
    } else if (error.request) {
      // Request was made but no response received
      const apiError: ApiError = {
        message: 'Unable to connect to the server. Please check if the API is running.',
        code: 'CONNECTION_ERROR',
      };
      throw apiError;
    } else {
      // Something else happened
      const apiError: ApiError = {
        message: error.message || 'An unexpected error occurred',
        code: 'UNKNOWN_ERROR',
      };
      throw apiError;
    }
  }
);

export const askLLM = async (question: string): Promise<string> => {
  try {
    console.log('Making request to /ask_llm with question:', question.substring(0, 100) + '...');
    const response = await api.post('/ask_llm', {
      question: question,
    }, {
      timeout: 120000, // 2 minutes timeout for LLM generation
    });
    console.log('Response received:', response.data);
    return response.data.response; // Extract the 'response' field from the returned object
  } catch (error) {
    console.error('askLLM API call failed:', error);
    throw error;
  }
};

export const getBillSimilaritySearch = async (billType: 'HB' | 'SB', billNumber: string): Promise<BillSimilaritySearch> => {
  const response = await api.post('/get_similar_bills', null, {
    timeout: 120000,
    params: {
      bill_type: billType,
      bill_number: billNumber,
    }
  });
  return response.data;
};

/**
 * Get available fiscal note files
 */
export const getFiscalNoteFiles = async (): Promise<{ name: string; status: string }[]> => {
  const response = await api.get('/get_fiscal_note_files');
  return response.data;
};

/**
 * Get available September fiscal note files (archived)
 */
export const getFiscalNoteFilesSeptember = async (): Promise<{ name: string; status: string }[]> => {
  const response = await api.get('/get_fiscal_note_files_september');
  return response.data;
};

/**
 * Create a new fiscal note
 */
export const createFiscalNote = async (
  billType: 'HB' | 'SB',
  billNumber: string,
  year: string = '2025'
): Promise<{ message: string; job_id?: string, success: boolean }> => {
  const response = await api.post('/generate-fiscal-note', null, {
    params: {
      bill_type: billType,
      bill_number: billNumber,
      year: year
    }
  });
  return response.data;
};

/**
 * Get fiscal note HTML content (legacy)
 */
export const getFiscalNote = async (
  billType: 'HB' | 'SB',
  billNumber: string,
  year: string = '2025'
): Promise<string | { message: string }> => {
  const response = await api.post('/get_fiscal_note', null, {
    params: {
      bill_type: billType,
      bill_number: billNumber,
      year: year
    },
    responseType: 'text' // Important: expect HTML response
  });
  return response.data;
};

/**
 * Get fiscal note structured data for React frontend
 */
export const getFiscalNoteData = async (
  billType: 'HB' | 'SB',
  billNumber: string,
  year: string = '2025'
): Promise<FiscalNoteData> => {
  const response = await api.post('/get_fiscal_note_data', null, {
    params: {
      bill_type: billType,
      bill_number: billNumber,
      year: year
    }
  });
  return response.data;
};

/**
 * Get September fiscal note HTML content (archived)
 */
export const getFiscalNoteSeptember = async (
  billType: 'HB' | 'SB',
  billNumber: string,
  year: string = '2025'
): Promise<string | { message: string }> => {
  const response = await api.post('/get_fiscal_note_september', null, {
    params: {
      bill_type: billType,
      bill_number: billNumber,
      year: year
    },
    responseType: 'text' // Important: expect HTML response
  });
  return response.data;
};

/**
 * Delete a fiscal note
 */
export const deleteFiscalNote = async (
  billType: 'HB' | 'SB',
  billNumber: string,
  year: string = '2025'
): Promise<{ message: string }> => {
  const response = await api.post('/delete_fiscal_note', null, {
    params: {
      bill_type: billType,
      bill_number: billNumber,
      year: year
    }
  });
  return response.data;
};

/**
 * Property Prompts Management
 */

export interface PropertyPrompt {
  prompt: string;
  description: string;
}

export interface PropertyPrompts {
  [key: string]: PropertyPrompt;
}

export interface PropertyPromptTemplate {
  id: string;
  name: string;
  is_default: boolean;
  created_at: string;
  prompts: PropertyPrompts;
}

/**
* Get all property prompt templates and active template ID
*/
export const getPropertyPrompts = async (): Promise<{ templates: PropertyPromptTemplate[]; active_template_id: string }> => {
  const response = await api.get('/property-prompts');
  return response.data;
};

/**
* Create a new template by copying an existing one
*/
export const createPropertyPromptTemplate = async (sourceTemplateId: string, name: string): Promise<{ success: boolean; template: PropertyPromptTemplate; message: string }> => {
  const response = await api.post('/property-prompts/template', {
    source_template_id: sourceTemplateId,
    name
  });
  return response.data;
};

/**
* Update an existing template
*/
export const updatePropertyPromptTemplate = async (templateId: string, data: { name?: string; prompts?: PropertyPrompts }): Promise<{ success: boolean; template: PropertyPromptTemplate; message: string }> => {
  const response = await api.put(`/property-prompts/template/${templateId}`, data);
  return response.data;
};

/**
* Delete a template
*/
export const deletePropertyPromptTemplate = async (templateId: string): Promise<{ success: boolean; message: string }> => {
  const response = await api.delete(`/property-prompts/template/${templateId}`);
  return response.data;
};

/**
* Set the active template for fiscal note generation
*/
export const setActivePropertyPromptTemplate = async (templateId: string): Promise<{ success: boolean; active_template_id: string; message: string }> => {
  const response = await api.put('/property-prompts/active', { template_id: templateId });
  return response.data;
};

/**
 * Get property prompts used for a specific fiscal note
 */
export const getFiscalNotePropertyPrompts = async (
  billType: 'HB' | 'SB',
  billNumber: string,
  fiscalNoteName: string,
  year: string = '2025'
): Promise<{ prompts: PropertyPrompts; is_stored: boolean; custom_prompts_used: boolean; message?: string }> => {
  const response = await api.get('/fiscal-note-property-prompts', {
    params: {
      bill_type: billType,
      bill_number: billNumber,
      fiscal_note_name: fiscalNoteName,
      year: year
    }
  });
  return response.data;
};

/**
 * Save annotations (strikethroughs and underlines) for a fiscal note
 * Supports both legacy strikethroughs and new annotations format
 */
export const saveStrikethroughs = async (
  filename: string,
  annotations: any[], // Can be strikethroughs (legacy) or annotations (new)
  billType: string,
  billNumber: string,
  year: string = '2025'
): Promise<{ success: boolean; message: string; filename: string; metadata_file: string; annotation_count?: number }> => {
  // Check if annotations have 'type' field to determine format
  const hasTypeField = annotations.length > 0 && annotations[0].type !== undefined;

  const response = await api.post('/fiscal-notes/save-strikethroughs', {
    filename,
    // Send as annotations if they have type field, otherwise as strikethroughs (legacy)
    ...(hasTypeField ? { annotations } : { strikethroughs: annotations }),
    bill_type: billType,
    bill_number: billNumber,
    year
  });
  return response.data;
};

/**
 * Get available collections and their stats
 */
export const getCollections = async (): Promise<CollectionsResponse> => {
  const response = await api.get('/collections');
  return response.data;
};

/**
 * Search documents in a specific collection
 */
export const searchDocuments = async (
  query: string,
  collection: string = 'courses',
  searchType: string = 'semantic',
  maxResults: number = 10
): Promise<SearchResponse> => {
  const response = await api.post('/search', {
    query,
    collections: [collection],
    search_type: searchType,
    num_results: maxResults,
  });

  // Transform the backend response to match our frontend types
  const backendResults = response.data;

  return {
    results: backendResults.map((item: any) => ({
      id: item.metadata?.id || `result_${Math.random()}`,
      content: item.content,
      metadata: item.metadata || {},
      score: item.score || 0,
    })),
    total_results: backendResults.length,
    query,
    collection,
    search_type: searchType,
  };
};

/**
 * Ask a question and get an AI-generated answer across all collections
 */
export const askQuestion = async (
  question: string,
  conversationId?: string,
  sourceReferences?: any[]
): Promise<QuestionResponse> => {
  const requestBody: any = {
    query: question,
    threshold: 0,  // Default threshold for similarity filtering
  };

  // Add conversation context if provided
  if (conversationId) {
    requestBody.conversation_id = conversationId;
  }
  if (sourceReferences && sourceReferences.length > 0) {
    requestBody.source_references = sourceReferences;
  }

  const response = await api.post('/query', requestBody, {
    timeout: 300000, // 5 minutes for complex queries
  });

  // Transform the backend response to match our frontend types
  const backendData = response.data;

  return {
    answer: backendData.answer || 'No answer available',
    sources: (backendData.sources || []).map((source: any) => ({
      id: source.metadata?.id || `source_${Math.random()}`,
      content: source.content,
      metadata: source.metadata || {},
      score: source.score || 0,
    })),
    query: question,
    collection: 'all', // Indicate it searched across all collections
    conversation_id: backendData.conversation_id,
    immediate_response: backendData.immediate_response,
    processing_time: backendData.processing_time,
  };
};

/**
 * Health check endpoint
 */
export const healthCheck = async (): Promise<{ status: string }> => {
  const response = await api.get('/');
  return response.data;
};

/**
 * Upload documents to a group/collection
 */
export const uploadDocuments = async (
  collectionId: string,
  files: File[],
  parsingType: string,
  customParsingDescription?: string,
  onProgress?: (fileName: string, progress: number) => void
): Promise<{ message: string; processed_files: number }> => {
  const formData = new FormData();

  files.forEach((file) => {
    formData.append('files', file);
  });

  formData.append('parsing_type', parsingType);
  if (customParsingDescription) {
    formData.append('custom_description', customParsingDescription);
  }

  const response = await api.post(`/collections/${collectionId}/upload`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    onUploadProgress: (progressEvent) => {
      if (progressEvent.total && onProgress) {
        const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total);
        // For simplicity, we'll use the first file name for progress
        onProgress(files[0]?.name || 'files', progress);
      }
    },
  });

  return response.data;
};

/**
 * Create a new collection
 */
export const createCollection = async (
  collection_name: string,
): Promise<{ message: string; collection_name: string; collection_path: string; directories_created: any }> => {
  const response = await api.post('/create-collection', {
    collection_name: collection_name,
  });
  return response.data;
};

/**
 * Upload PDF files for fiscal note generation to a specific collection
 */
export const uploadPDFFiles = async (
  collectionName: string,
  files: File[],
  onProgress?: (fileName: string, progress: number) => void
): Promise<{ message: string; collection_name: string; uploaded_files: any[]; total_files: number }> => {
  const formData = new FormData();
  formData.append('collection_name', collectionName);

  files.forEach((file) => {
    formData.append('files', file);
  });

  const response = await api.post('/upload-pdf', formData, {
    headers: {
      'Content-Type': undefined, // Let browser set multipart/form-data with boundary
    },
    onUploadProgress: (progressEvent) => {
      if (progressEvent.total && onProgress) {
        const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total);
        // For simplicity, we'll use the first file name for progress
        onProgress(files[0]?.name || 'files', progress);
      }
    },
  });

  return response.data;
};

/**
 * Upload PDF files to a collection path
 */
export const uploadPDFToCollection = async (
  files: File[],
  collection_path: string
): Promise<any> => {
  const formData = new FormData();
  files.forEach(file => formData.append('files', file));
  formData.append('collection_path', collection_path);

  const response = await api.post('/upload-pdf', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  });
  return response.data;
};

/**
 * Upload documents from Google Drive
 */
export const uploadFromGoogleDrive = async (
  folder_link: string,
  collection_path: string,
  recursive: boolean
): Promise<any> => {
  const response = await api.post('/upload-through-google-drive', {
    folder_link,
    collection_path,
    recursive
  });
  return response.data;
};

/**
 * Upload documents via web crawler
 */
export const uploadFromWebUrl = async (
  url: string,
  collection_path: string
): Promise<any> => {
  const response = await api.post('/web-crawler', {
    url,
    collection_path
  });
  return response.data;
};

/**
 * Extract text from documents
 */
export const extractText = async (
  collection_path: string,
  extract_tables: boolean,
  extract_images_with_text: boolean,
  extract_images_without_text: boolean
): Promise<any> => {
  const response = await api.post('/step1-text-extraction', {
    collection_path,
    extract_tables,
    extract_images_with_text,
    extract_images_without_text
  });
  return response.data;
};

/**
 * Chunk extracted text
 */
export const chunkText = async (
  collection_path: string,
  chunking_method: string,
  chunk_size: number,
  chunk_overlap: number,
  use_ai: boolean,
  context_prompt: string
): Promise<any> => {
  const response = await api.post('/step2-chunking', {
    collection_name: collection_path, // Backend expects collection_name
    chosen_methods: [chunking_method], // Backend expects chosen_methods array
    chunk_size,
    chunk_overlap,
    use_ai,
    prompt_description: context_prompt, // Backend expects prompt_description
    identifier: 'fiscal_note', // Add required field
    previous_pages_to_include: 1, // Add default
    context_items_to_show: 2, // Add default
    rewrite_query: false // Add default
  });
  return response.data;
};

/**
 * Extract text from all PDF files in a collection
 */
export const extractTextFromPDFs = async (
  collectionName: string,
  options: {
    contains_tables?: boolean;
    contains_images_of_text?: boolean;
    contains_images_of_nontext?: boolean;
  } = {}
): Promise<{ message: string; collection_name: string; processed_files: any[]; total_processed: number; errors: string[] }> => {
  const response = await api.post('/step1-text-extraction', null, {
    params: {
      collection_name: collectionName,
      contains_tables: options.contains_tables || false,
      contains_images_of_text: options.contains_images_of_text || false,
      contains_images_of_nontext: options.contains_images_of_nontext || false,
    },
  });

  return response.data;
};

/**
 * Chunk extracted text from all files in a collection
 */
export const chunkExtractedText = async (
  collectionName: string,
  options: {
    chosen_methods?: string[];
    identifier?: string;
    chunk_size?: number;
    chunk_overlap?: number;
    use_ai?: boolean;
    prompt_description?: string;
    previous_pages_to_include?: number;
    context_items_to_show?: number;
    rewrite_query?: boolean;
  } = {}
): Promise<{ message: string; collection_name: string; processed_files: any[]; total_processed: number; errors: string[] }> => {
  const response = await api.post('/step2-chunking', {
    collection_name: collectionName,
    chosen_methods: options.chosen_methods || ['pymupdf_extraction_text'],
    identifier: options.identifier || 'fiscal_note',
    chunk_size: options.chunk_size || 1000,
    chunk_overlap: options.chunk_overlap || 200,
    use_ai: options.use_ai || false,
    prompt_description: options.prompt_description,
    previous_pages_to_include: options.previous_pages_to_include || 1,
    context_items_to_show: options.context_items_to_show || 2,
    rewrite_query: options.rewrite_query || false,
  });

  return response.data;
};

/**
 * Ask a question with specific collections selected
 */
export const askQuestionWithCollections = async (
  question: string,
  selectedCollections: string[] = []
): Promise<QuestionResponse> => {
  const response = await api.post('/query', {
    query: question,
    collections: selectedCollections.length > 0 ? selectedCollections : undefined,
    threshold: 0,
  }, {
    timeout: 300000, // 5 minutes for complex fiscal analysis
  });

  const backendData = response.data;

  return {
    answer: backendData.response || 'No answer available',
    sources: (backendData.sources || []).map((source: any) => ({
      id: source.metadata?.id || `source_${Math.random()}`,
      content: source.content,
      metadata: source.metadata || {},
      score: source.score || 0,
    })),
    query: question,
    collection: selectedCollections.length > 0 ? selectedCollections.join(', ') : 'all',
  };
};

/**
 * Chat with a specific PDF document using additional collections as context
 */
export const chatWithPDF = async (
  query: string,
  sessionCollection: string,
  contextCollections: string[] = [],
  threshold: number = 0
): Promise<{
  response: string;
  sources: any[];
  session_collection: string;
  context_collections: string[];
  valid_collections_used: string[];
  query: string;
}> => {
  const response = await api.post('/chat-with-pdf', {
    query,
    session_collection: sessionCollection,
    context_collections: contextCollections,
    threshold,
  }, {
    timeout: 300000, // 5 minutes for complex analysis
  });
  console.log(response.data);
  return response.data;
};

/**
 * Stream chat with PDF - provides real-time updates during subquestion processing
 */
export const streamChatWithPDF = async (
  query: string,
  sessionCollection: string,
  contextCollections: string[] = [],
  threshold: number = 0,
  onUpdate: (update: any) => void,
  onError: (error: string) => void,
  onComplete: (response: any) => void
): Promise<void> => {
  try {
    console.log('🚀 FRONTEND: Starting streaming connection...');
    console.log('📝 Request data:', { query: query.substring(0, 50) + '...', sessionCollection, contextCollections, threshold });

    const response = await fetch(`${API_BASE_URL}/chat-with-pdf-stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        query,
        session_collection: sessionCollection,
        context_collections: contextCollections,
        threshold,
      }),
    });

    console.log('📡 Response status:', response.status, response.statusText);
    console.log('📡 Response headers:', Object.fromEntries(response.headers.entries()));

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error('Failed to get response reader');
    }

    console.log('✅ FRONTEND: Stream reader obtained successfully');
    const decoder = new TextDecoder();
    let buffer = '';
    let messageCount = 0;

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          console.log('📡 FRONTEND: Stream ended (done=true)');
          break;
        }

        const chunk = decoder.decode(value, { stream: true });
        buffer += chunk;
        messageCount++;

        console.log(`📨 FRONTEND: Received chunk ${messageCount}:`, chunk.substring(0, 100) + (chunk.length > 100 ? '...' : ''));

        const lines = buffer.split('\n');
        buffer = lines.pop() || ''; // Keep incomplete line in buffer

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const jsonData = line.slice(6);
              console.log('🔍 FRONTEND: Parsing JSON:', jsonData.substring(0, 200) + (jsonData.length > 200 ? '...' : ''));
              const data = JSON.parse(jsonData);

              console.log('✅ FRONTEND: Parsed data:', data.type, data.message?.substring(0, 50));

              if (data.type === 'error') {
                console.log('❌ FRONTEND: Error received:', data.message);
                onError(data.message);
                return;
              } else if (data.type === 'completed') {
                console.log('🏁 FRONTEND: Completion received');
                onComplete(data.response);
                return;
              } else {
                console.log('📤 FRONTEND: Calling onUpdate with:', data.type);
                onUpdate(data);
              }
            } catch (parseError) {
              console.error('❌ FRONTEND: Failed to parse streaming data:', parseError, 'Line:', line);
            }
          } else if (line.trim()) {
            console.log('⚠️ FRONTEND: Non-data line received:', line);
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  } catch (error) {
    console.error('Streaming error:', error);
    onError(error instanceof Error ? error.message : 'Unknown streaming error');
  }
};

/**
 * RefBot API Methods
 */

export const getRefBotResults = async (token: string): Promise<{ completed: any[], jobs: any[] }> => {
  const response = await api.get('/refbot/results', {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });
  return response.data;
};

export const uploadRefBotCollection = async (token: string, name: string, file: File): Promise<any> => {
  const formData = new FormData();
  formData.append('name', name);
  formData.append('file', file);

  const response = await api.post('/refbot/upload', formData, {
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'multipart/form-data'
    }
  });
  return response.data;
};

export const deleteRefBotResult = async (token: string, filename: string): Promise<any> => {
  const response = await api.delete(`/refbot/results/${filename}`, {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });
  return response.data;
};

export default api;


// MOCKUP fiscal note data for hb400
const MOCK_FISCAL_NOTE_HB400: FiscalNote = {
  "overview": "HB400 appropriates funds for the Judiciary for fiscal biennium 2025-2027,  with varying proposed operating budget figures across different committee versions ranging from approximately $198 million to $216 million per fiscal year.  The bill also includes capital improvement appropriations, with proposed General Obligation Bond allocations fluctuating between $9.9 million and $12.9 million for FY 2025-2026, and no allocation for FY 2026-2027 across different versions.  Several amendments adjusted appropriation amounts, effective dates (ranging from July 1, 2025 to April 23, 2057), and included  additional funding for civil legal services and immigration-related legal aid within the Judiciary budget.",
  "policy_impact": "HB400 modifies existing Judiciary appropriations by significantly increasing funding for the fiscal biennium 2025-2027, with varying versions proposing operating budgets between $198 million and $216 million annually.  Crucially,  amendments, such as those in SD1 (SSCR1253),  introduce  new policy directives by allocating additional funds specifically for civil legal services ($1 million) and immigration-related legal aid ($750,000), reflecting a legislative strategy to enhance access to justice for vulnerable populations.  This aligns with broader legislative efforts to address societal needs and potentially impacts state governance by influencing the Judiciary's capacity to handle increased caseloads and expand its service offerings.",
  "appropriations": "HB400 allocates varying amounts for the Judiciary's operating budget across different legislative versions, ranging from $198,782,736 to $216,237,353 in FY 2026-2027.  Capital improvement appropriations, primarily funded through General Obligation Bonds, are proposed at $9.9 million for FY 2025-2026, with no allocation for the subsequent fiscal year in some versions.  Intended uses include staffing increases (e.g.,  additional District Court Judge and support staff in Kona,  permanent and temporary FTE increases),  technology upgrades (cybersecurity), and funding for programs like the Criminal Justice Research Institute and civil legal services.",
  "assumptions_and_methodology": "The operating budget projections for the Judiciary in HB400 rely on existing expenditure data and anticipated inflationary pressures, adjusted for proposed staffing increases and program expansions detailed in the bill's various versions.  Capital improvement cost estimates, particularly the $12.9 million figure in some versions for FY 2025-2026, are based on project-specific cost analyses provided by the Judiciary,  potentially incorporating comparable past projects and  consultant estimates (specific details on these sources are not explicitly provided in the available documents).  The discrepancy between proposed General Obligation Bond allocations across different versions reflects ongoing legislative negotiations and adjustments to project scope.",
  "agency_impact": "The Judiciary's operational impact will include managing increased workloads stemming from  new staffing (e.g., a Kona District Court Judge and support staff,  additional FTEs) and expanded programs like enhanced civil legal services and immigration legal aid,  as mandated by HB400.  Administrative adjustments will be necessary to accommodate these changes, including  revised budgeting,  staff training, and  resource allocation across existing departments.  Budgetary impacts are directly tied to the varying appropriation levels in HB400, ranging from approximately $198 million to $216 million annually for operating expenses, plus capital improvement allocations ranging from $9.9 million to $12.9 million in FY 2025-2026.",
  "economic_impact": "HB400's funding for the Judiciary, ranging from approximately $198 million to $216 million annually in operating funds and up to $12.9 million in capital improvements for FY 2025-2026, is projected to improve access to justice, particularly through increased funding for civil legal services ($1 million annually) and immigration-related legal aid ($750,000 annually).  These investments should reduce backlogs and improve efficiency within the court system, indirectly benefiting the Hawaii community through more timely dispute resolution and enhanced access to legal representation for vulnerable populations.  However, a precise quantification of community benefits and cost savings requires further analysis beyond the provided documents.",
  "revenue_sources": "The primary funding source for the Judiciary's operating budget in HB400 is General Funds, with varying proposed allocations across different legislative versions ranging from approximately $198 million to $216 million annually for fiscal years 2025-2027.  Capital improvement projects are proposed to be funded through General Obligation Bonds, with amounts fluctuating between $9.9 million and $12.9 million for FY 2025-2026, and no allocation for FY 2026-2027 in some versions.  No other significant revenue streams are explicitly identified in the provided documents.",
  "six_year_fiscal_implications": "The provided documents offer insufficient data for a complete six-year fiscal outlook.  The available information focuses primarily on the 2025-2027 biennium.  While HB400 includes appropriations for this period, ranging from approximately $198 million to $216 million annually in operating funds and up to $12.9 million in capital improvements for FY 2025-2026 (with varying amounts across different versions),  no projections extend beyond FY 2026-2027.  The Judiciary's request for additional FTEs (17.0 permanent and 1.0 temporary in FY 2026) suggests potential ongoing staffing costs, but the long-term implications of these additions are not specified.  Similarly, the  $1 million annual allocation for civil legal services and $750,000 for immigration-related legal aid are presented as recurring expenses for the biennium, but their continuation beyond 2027 is uncertain.  Assumptions regarding program expansion or permanence are absent from the provided documents, hindering the creation of a reliable six-year projection.  To generate a comprehensive six-year fiscal outlook, additional data on projected workload increases, inflation rates, potential program modifications, and long-term staffing plans are needed.  Without this information, any six-year projection would be highly speculative and unreliable.",
  "fiscal_implications_after_6_years": "The provided documents lack sufficient information to project ongoing fiscal obligations for the Judiciary beyond the 2025-2027 biennium.  While the recurring nature of operating expenses like civil legal services ($1 million annually) and immigration-related legal aid ($750,000 annually) suggests continued costs, their long-term funding is unaddressed.  Similarly, the number of program sites or units remains unspecified beyond the initial implementation period, preventing a reliable projection of future operational needs and associated costs.  Therefore, a detailed analysis of the fiscal implications after six years is impossible without additional data on program sustainability and future budgetary allocations.",
  "operating_revenue_impact": "The provided documents detail appropriations for the Judiciary's operating budget, but do not describe any anticipated impacts on *operating revenues*.  The fiscal note focuses solely on expenditures and appropriations from General Funds and General Obligation Bonds, with no mention of revenue generation or changes to existing revenue streams resulting from HB400.  Therefore, there is no discernible impact on operating revenues to report.",
  "capital_expenditure_impact": "HB400 proposes capital improvement appropriations for the Judiciary, primarily funded through General Obligation Bonds.  Different versions of the bill propose varying amounts, ranging from $9.9 million to $12.9 million for Fiscal Year 2025-2026, with no allocation proposed for FY 2026-2027 in some versions.  These funds are intended for projects such as chiller replacement at the Kauai Judiciary Complex and general alterations, upgrades, and improvements to Judiciary facilities statewide, as detailed in Part IV of the bill."
};

const MOCK_BILLS: Bill[] = [
  { id: 'hb400', name: 'HB400' },
  { id: 'sb500', name: 'SB500' },
];

/**
 * MOCKUP: Get available bills
 */
export const getBills = async (): Promise<Bill[]> => {
  console.log('Fetching mock bills...');
  return new Promise(resolve => {
    setTimeout(() => {
      resolve(MOCK_BILLS);
    }, 500);
  });
};

/**
 * MOCKUP: Get fiscal note for a specific bill
 */
export const getBillFiscalNote = async (billId: string): Promise<FiscalNote> => {
  console.log(`Fetching mock fiscal note for ${billId}...`);
  return new Promise((resolve, reject) => {
    setTimeout(() => {
      if (billId === 'hb400') {
        resolve(MOCK_FISCAL_NOTE_HB400);
      } else {
        reject(new Error(`No fiscal note found for bill ${billId}`));
      }
    }, 1000);
  });
};

/**
 * Get HRS HTML data
 */
export const getHRSHTML = async (
  volume?: string,
  chapter?: string,
  section?: string
): Promise<string> => {
  let pathOrder = [volume, chapter, section];
  let urlPathParts = ["hrs", "html"];
  for (let part of pathOrder) {
    if (part !== undefined) {
      urlPathParts.push(part);
    }
    else {
      break;
    }
  }
  const response = await api.get(`/${urlPathParts.join("/")}`);
  return response.data;
};


/**
 * Get HRS text data
 */
export const getHRSRaw = async (
  volume?: string,
  chapter?: string,
  section?: string
): Promise<string> => {
  let pathOrder = [volume, chapter, section];
  let urlPathParts = ["hrs", "raw"];
  for (let part of pathOrder) {
    if (part !== undefined) {
      urlPathParts.push(part);
    }
    else {
      break;
    }
  }
  const response = await api.get(`/${urlPathParts.join("/")}`);
  return response.data;
};


/**
 * Search HRS
 */
export const searchHRS = async (
  searchText: string,
  volume?: string,
  chapter?: string,
  section?: string
): Promise<[string, string, string][]> => {
  let pathOrder = [volume, chapter, section];
  const queryString = encodeURIComponent(searchText);
  let urlPathParts = ["hrs", "find"];
  for (let part of pathOrder) {
    if (part !== undefined) {
      urlPathParts.push(part);
    }
    else {
      break;
    }
  }
  const response = await api.get(`/${urlPathParts.join("/")}?q=${queryString}`);
  return response.data;
};


/**
 * Get HRS text data
 */
export const getHRSIndex = async (): Promise<HRSIndex> => {
  const response = await api.get("/hrs/index");
  return response.data;
};