export interface SearchResult {
  id: string;
  content: string;
  metadata: Record<string, any>;
  score: number;
}

export interface CollectionStats {
  count: number;
  name: string;
  status: string;
}

export interface CollectionsResponse {
  collections: Collection[];
  total_collections: number;
}

export interface Collection {
  name: string;
  num_documents: number;
  last_updated?: string;
  total_size?: number;
  path?: string;
  status?: string;
}

export interface SearchResponse {
  results: SearchResult[];
  total_results: number;
  query: string;
  collection: string;
  search_type: string;
}

export interface QuestionResponse {
  answer: string;
  sources: SearchResult[];
  query: string;
  collection: string;
  conversation_id?: string;
  immediate_response?: boolean;
  processing_time?: number;
}

export interface ChatMessage {
  id: string;
  type: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  collection?: string;
  sources?: SearchResult[];
  isLoading?: boolean;
  conversation_id?: string;
}

export interface ConversationState {
  conversation_id: string;
  messages: ChatMessage[];
  source_references: any[];
  created_at: Date;
  last_updated: Date;
}

export interface ApiError {
  message: string;
  code?: string;
  details?: any;
}

export interface DocumentParsingType {
  id: string;
  label: string;
  description: string;
}

export interface UploadMethod {
  id: string;
  label: string;
  description: string;
  icon: React.ComponentType<any>;
}

export interface CreateGroupData {
  name: string;
  description?: string;
  documents: File[];
  parsingType: string;
  customParsingDescription?: string;
  
  // Upload method and related fields
  uploadMethod?: string;
  googleDriveUrl?: string;
  websiteUrl?: string;
  extractionPrompt?: string;
  recursive?: boolean;
  recursiveDownload?: boolean;
  
  // Text extraction settings
  containsTables?: boolean;
  containsImagesOfText?: boolean;
  containsImagesOfNontext?: boolean;
  containsStructuredData?: boolean;
  extractionType?: 'basic' | 'advanced';
  
  // Text chunking settings
  chunkingMethods?: string[];
  chunkSize?: number;
  chunkOverlap?: number;
  useAI?: boolean;
  useAi?: boolean;
  splitBySentence?: boolean;
  useSemanticSplitter?: boolean;
  
  // Additional settings
  promptDescription?: string;
  previousPagesToInclude?: number;
  contextItemsToShow?: number;
  rewriteQuery?: boolean;
}

export interface CreateGroupStep {
  id: number;
  title: string;
  description: string;
}

export interface UploadProgress {
  fileName: string;
  progress: number;
  status: 'pending' | 'uploading' | 'completed' | 'error';
  error?: string;
}

export interface Bill {
  id: string;
  name: string;
}

export interface FiscalNote {
  overview: string;
  policy_impact: string;
  appropriations: string;
  assumptions_and_methodology: string;
  agency_impact: string;
  economic_impact: string;
  revenue_sources: string;
  six_year_fiscal_implications: string;
  fiscal_implications_after_6_years: string;
  operating_revenue_impact: string;
  capital_expenditure_impact: string;
} 

export interface BillVectors {
  bill_name: string;
  summary: string;
  score: number;
}

export interface BillSimilaritySearch {
  tfidf_results: BillVectors[];
  vector_results: BillVectors[];
  search_bill: BillVectors;
}

export interface DocumentReference {
  type: 'document_reference';
  number: number;
  url: string;
  document_type: string;
  document_name: string;
  description: string;
  chunk_text?: string;
  similarity_score?: number;
}

export interface TimelineItem {
  date: string;
  text: string;
  documents: string[];
}

export interface FiscalNoteItem {
  filename: string;
  data: Record<string, any>;
}

export interface FiscalNoteData {
  status: 'ready' | 'generating' | 'error';
  message?: string;
  fiscal_notes: FiscalNoteItem[];
  timeline: TimelineItem[];
  document_mapping: Record<string, number>;
}
