# Fiscal Notes Directory Consolidation

## Changes Made

### ✅ Consolidated All Fiscal Note Data

All fiscal note related files are now in **one location**: `/src/fiscal_notes/generation/`

### Before (Scattered)
```
/src/HB_727_2025/fiscal_notes/
  ├── HB727_chunk_mapping.json
  ├── HB727_HD1_HSCR624__chunk_mapping.json
  └── ...

/src/fiscal_notes/generation/HB_727_2025/fiscal_notes/
  ├── HB727.json
  ├── HB727_HD1_HSCR624_.json
  ├── HB727_HD1_HSCR624__metadata.json
  └── ...
```

### After (Consolidated)
```
/src/fiscal_notes/generation/HB_727_2025/fiscal_notes/
  ├── HB727.json                              # Fiscal note
  ├── HB727_chunk_mapping.json                # Chunk mapping
  ├── HB727_HD1_HSCR624_.json                 # Fiscal note
  ├── HB727_HD1_HSCR624__chunk_mapping.json   # Chunk mapping
  ├── HB727_HD1_HSCR624__metadata.json        # Metadata
  └── ...
```

## Code Changes

### 1. Updated Chunk Mapping Generation
**File:** `src/fiscal_notes/generation/step5_fiscal_note_gen.py`

**Change:** Modified `save_chunk_mapping()` to save files to the generation directory:
```python
# OLD: Saved to /src/HB_*_2025/fiscal_notes/
bill_dir = f"{bill_type}_{bill_number}_{year}"
output_dir = os.path.join(bill_dir, "fiscal_notes")

# NEW: Saves to /src/fiscal_notes/generation/HB_*_2025/fiscal_notes/
script_dir = os.path.dirname(os.path.abspath(__file__))
bill_dir = f"{bill_type}_{bill_number}_{year}"
output_dir = os.path.join(script_dir, bill_dir, "fiscal_notes")
```

### 2. API Already Reads from Correct Location
**File:** `src/api.py` (Line 1135)

The API already uses the generation directory:
```python
fiscal_notes_dir = Path(__file__).parent / "fiscal_notes" / "generation"
```

**No changes needed** - API already reads chunk mappings from the correct location (line 2186).

### 3. Updated .gitignore
**File:** `.gitignore`

Simplified to only ignore the generation directory:
```gitignore
# Fiscal notes generation directory (user-generated data)
# Includes fiscal notes, chunk mappings, and metadata
/src/fiscal_notes/generation/HB_*_2025/
/src/fiscal_notes/generation/SB_*_2025/
/src/fiscal_notes/generation/HR_*_2025/
/src/fiscal_notes/generation/SR_*_2025/
```

## Migration Completed

### Files Moved
- ✅ All `*_chunk_mapping.json` files moved from `/src/HB_*_2025/` to `/src/fiscal_notes/generation/HB_*_2025/`
- ✅ Empty directories cleaned up
- ✅ 20+ bill directories consolidated

### Verified
- ✅ Chunk mappings exist in generation directory
- ✅ Old root-level directories removed
- ✅ API reads from correct location
- ✅ Generation script saves to correct location

## Benefits

### 1. **Single Source of Truth**
All fiscal note data (notes, chunks, metadata) in one place

### 2. **Simpler Deployment**
Only one directory pattern to ignore in Git

### 3. **Easier Backup**
Backup `/src/fiscal_notes/generation/` to preserve all user data

### 4. **Cleaner Repository**
No scattered bill directories in `/src/` root

### 5. **Consistent Structure**
```
/src/fiscal_notes/generation/
  ├── HB_*_2025/
  │   ├── documents/              # Source documents
  │   ├── fiscal_notes/           # Generated notes + chunks + metadata
  │   ├── *_chronological.json    # Timeline data
  │   └── *_timeline.json         # Timeline data
  ├── SB_*_2025/
  └── september_archive/          # Archived bills
```

## Testing

### Verify Chunk Mappings Work
```bash
# Check files exist
ls -la src/fiscal_notes/generation/HB_70_2025/fiscal_notes/*_chunk_mapping.json

# Test API endpoint
curl http://localhost:8200/api/fiscal-notes/HB/70/2025
```

### Verify Generation Works
```bash
cd src/fiscal_notes/generation
python step5_fiscal_note_gen.py
# Should save chunk mappings to current directory structure
```

## Rollback (If Needed)

If you need to rollback:
```bash
# The old files are gone, but you can regenerate chunk mappings
cd src/fiscal_notes/generation
python step5_fiscal_note_gen.py --regenerate-chunks
```

## Next Steps

1. ✅ Test fiscal note generation with new structure
2. ✅ Test API endpoints return chunk mappings correctly
3. ✅ Test frontend displays citations properly
4. ✅ Commit changes to Git
5. ✅ Deploy to production (data will be preserved via .gitignore)
