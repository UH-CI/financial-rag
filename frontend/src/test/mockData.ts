import type { FiscalNoteItem, DocumentInfo, NumberCitationMapItem, ChunkTextMapItem } from '../types';
import fiscalNoteData from './HB_727_2025/fiscal_notes/HB727.json';
import documentMappingData from './HB_727_2025/document_mapping.json';
import metadataData from './HB_727_2025/fiscal_notes/HB727_metadata.json';

export const mockFiscalNote: FiscalNoteItem = {
  filename: 'HB727',
  data: fiscalNoteData,
  strikethroughs: []
};

export const mockDocumentMapping: Record<string, number> = documentMappingData;

export const mockEnhancedDocumentMapping: Record<number, DocumentInfo> = {
  1: {
    name: 'HB727',
    type: 'Bill Introduction',
    description: "House Bill 727 - Women's Court Pilot Program",
    icon: '📄'
  },
  2: {
    name: 'HB727_TESTIMONY_JHA_01-30-25_',
    type: 'Testimony',
    description: 'Judiciary and Hawaiian Affairs Committee Testimony',
    icon: '💬'
  },
  3: {
    name: 'HB727_HD1',
    type: 'Bill Draft',
    description: 'House Bill 727 HD1',
    icon: '📋'
  },
  4: {
    name: 'HB727_HD1_HSCR624_',
    type: 'Committee Report',
    description: 'House Standing Committee Report 624',
    icon: '📊'
  }
};

// Extract chunk text map from metadata
export const mockChunkTextMap: Record<number, ChunkTextMapItem[]> = {
  1: (metadataData.response_metadata.chunks_metadata.chunk_details as any[]).slice(0, 5).map((chunk: any) => ({
    chunk_text: chunk.chunk_text,
    attribution_score: 0.95,
    attribution_method: 'semantic' as const,
    sentence: chunk.chunk_text.substring(0, 100) + '...',
    chunk_id: chunk.chunk_id,
    document_name: chunk.document_name
  }))
};

// No financial citations in HB727
export const mockNumberCitationMap: Record<number, NumberCitationMapItem> = {};
