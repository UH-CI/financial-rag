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
  type: 'document_reference' | 'chunk_reference';
  number: number;
  displayNumber?: string; // Optional display number like "5.3" for chunk sub-citations
  url?: string;
  document_type: string;
  document_name: string;
  description: string;
  document_category?: string; // Bill Introduction, Bill Amendment, Committee Report, Testimony
  document_icon?: string; // Icon for the document type
  chunk_text?: string;
  similarity_score?: number;
  sentence?: string; // The sentence context for word highlighting
  financial_amount?: number; // The financial amount for financial citations
  chunk_id?: number; // For chunk references
}

export interface TimelineItem {
  date: string;
  text: string;
  documents: string[];
}

// Atom: stable unit for text rendering and selection mapping
export type Atom =
  | { type: 'text'; text: string }
  | { type: 'ref'; refId: string; display: string };

// Annotation types for Ramseyer format
export type AnnotationType = 'strikethrough' | 'underline';

// New unified annotation interface
export interface AnnotationItem {
  id: string;
  type: AnnotationType; // 'strikethrough' for deleted material, 'underline' for new material
  sectionKey: string;
  textContent: string; // Keep for reference/display
  timestamp: string;
  // Atom-based positioning (stable, deterministic)
  startAtom: number;   // Index in atom array
  startOffset: number; // Character offset within startAtom (0 for refs)
  endAtom: number;     // Index in atom array
  endOffset: number;   // Character offset within endAtom
}

// Legacy type for backward compatibility
export interface StrikethroughItem {
  id: string;
  sectionKey: string;
  textContent: string; // Keep for reference/display
  timestamp: string;
  // Atom-based positioning (stable, deterministic)
  startAtom: number;   // Index in atom array
  startOffset: number; // Character offset within startAtom (0 for refs)
  endAtom: number;     // Index in atom array
  endOffset: number;   // Character offset within endAtom
  type?: AnnotationType; // Optional for backward compatibility
}

export interface EnhancedNumber {
  number: number;
  filename: string;
  document_type: string;
  summary: string;
  amount_type?: string;
  unit?: string;
  sentiment?: string;
  category?: string;
  service_description?: string;
  expending_agency?: string;
  means_of_financing?: string;
}

export interface EnhancedNumbers {
  count: number;
  numbers: EnhancedNumber[];
}

export interface FiscalNoteItem {
  filename: string;
  data: Record<string, any>;
  new_documents_processed?: string[]; // Documents used to create this specific fiscal note
  strikethroughs?: StrikethroughItem[]; // Legacy: User-applied strikethroughs (backward compatibility)
  annotations?: AnnotationItem[]; // New: User-applied annotations (strikethrough + underline)
  enhanced_numbers?: EnhancedNumbers; // Enhanced financial numbers extracted from the bill
}

export interface NumbersDataItem {
  text: string;
  number: number;
  filename: string;
  document_type: string;
}

export interface NumberCitationMapItem {
  amount: number;
  filename: string;
  document_name: string;
  data?: NumbersDataItem;
}

export interface ChunkTextMapItem {
  chunk_text: string;
  attribution_score: number;
  attribution_method: string;
  sentence?: string; // The sentence context that contains the citation
  chunk_id?: number; // Chunk identifier for creating sub-citations
  document_name?: string; // Document name for the chunk
}

export interface ChunkReference {
  chunk_id: number;
  document_name: string;
  chunk_text: string;
  start_word?: number;
  end_word?: number;
  word_count?: number;
}

export interface ChunkMetadata {
  total_chunks: number;
  chunk_details: ChunkReference[];
}

export interface DocumentInfo {
  name: string;
  type: string;
  description: string;
  icon: string;
}

// Chronological Number Tracking Types
export interface HistoryEntry {
  segment_id: number;
  number: number;
  summary?: string;
  similarity_score: number;
  amount_type?: string;
  category?: string;
  fiscal_year?: string[];
  expending_agency?: string;
  source_documents?: string[];
  filename?: string;
  document_type?: string;
}

export interface TrackedNumber {
  number: number;
  text: string;
  filename: string;
  document_type: string;
  summary?: string;
  
  // Enhanced properties (from step 6)
  entity_name?: string;
  type?: string;
  fund_type?: string;
  fiscal_year?: string[];
  expending_agency?: string;
  category?: string;
  amount_type?: string;
  
  // Tracking metadata (from step 7)
  change_type: 'new' | 'continued' | 'modified' | 'no_change';
  first_appeared_in_segment: number;
  source_documents?: string[];
  history: HistoryEntry[];
  history_length?: number;
  carried_forward?: boolean;
  previous_number?: number;
  
  // Advanced tracking
  all_merged_numbers?: any[];
  exact_match_low_similarity?: {
    previous_segment: number;
    similarity: number;
    previous_summary: string;
  };
}

export interface NumberTrackingSegment {
  segment_id: number;
  segment_name: string;
  documents: string[];
  ends_with_committee_report: boolean;
  counts: {
    total: number;
    new: number;
    continued: number;
    modified: number;
    carried_forward: number;
  };
  numbers: TrackedNumber[];
  is_carried_forward?: boolean; // NEW: Flag indicating if this data was carried forward
  carried_forward_from?: number; // NEW: Original segment_id if carried forward
}

export interface ChronologicalTracking {
  bill_name: string;
  generated_at: string;
  numbers_source: 'enhanced' | 'regular';
  statistics: {
    total_segments: number;
    total_number_entries: number;
    new_numbers: number;
    continued_numbers: number;
    modified_numbers: number;
    no_change_numbers: number;
  };
  segments: NumberTrackingSegment[];
  timeline: Array<{
    segment_id: number;
    segment_name: string;
    new_numbers: number;
    modified_numbers: number;
    total_numbers: number;
  }>;
  metadata?: {
    total_segments: number;
    has_committee_reports: boolean;
  };
}

export interface FiscalNoteItem {
  filename: string;
  data: Record<string, any>;
  new_documents_processed?: string[]; // Documents used to create this specific fiscal note
  strikethroughs?: StrikethroughItem[]; // Legacy: User-applied strikethroughs (backward compatibility)
  annotations?: AnnotationItem[]; // New: User-applied annotations (strikethrough + underline)
  enhanced_numbers?: EnhancedNumbers; // Enhanced financial numbers extracted from the bill
  number_tracking?: NumberTrackingSegment; // NEW: Chronological number tracking for this fiscal note version
}

export interface FiscalNoteData {
  status: 'ready' | 'generating' | 'error';
  message?: string;
  fiscal_notes: FiscalNoteItem[];
  timeline: TimelineItem[];
  document_mapping: Record<string, number>;
  enhanced_document_mapping: Record<number, DocumentInfo>;
  numbers_data: NumbersDataItem[];
  number_citation_map: Record<number, NumberCitationMapItem>; // Each citation number maps to a single item
  chunk_text_map: Record<number, ChunkTextMapItem[]>; // Document citations to chunk text
  chunk_metadata?: ChunkMetadata; // Chunk information for CHUNK citations
  chronological_tracking?: ChronologicalTracking; // NEW: Full chronological tracking data
  has_tracking?: boolean; // NEW: Flag indicating if tracking data is available
}
