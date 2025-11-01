# Fiscal Note Generation Feature Flags

## Overview
The fiscal note generation pipeline has feature flags to enable/disable optional steps for optimization and testing.

## Location
Feature flags are defined in: `/src/api.py` (lines ~52-58)

## Available Flags

### ENABLE_STEP6_ENHANCE_NUMBERS
- **Default**: `False` (disabled)
- **Purpose**: Enhances numbers with RAG agent for additional context
- **File**: `step6_enhance_numbers.py`
- **Impact**: Non-critical, adds enhanced number context to fiscal notes

### ENABLE_STEP7_TRACK_CHRONOLOGICAL
- **Default**: `False` (disabled)
- **Purpose**: Tracks chronological changes in numbers across bill versions
- **File**: `step7_track_chronological.py`
- **Impact**: Non-critical, generates tracking files for number changes over time

## How to Enable/Disable

### Quick Toggle
Edit `/src/api.py` and change the flag values:

```python
# ============================================================================
# FEATURE FLAGS - Fiscal Note Generation Pipeline
# ============================================================================
ENABLE_STEP6_ENHANCE_NUMBERS = True   # Change to True to enable
ENABLE_STEP7_TRACK_CHRONOLOGICAL = True  # Change to True to enable
# ============================================================================
```

### Restart Required
After changing flags, restart the API server:
```bash
# Stop the current server (Ctrl+C)
# Then restart it
python src/api.py
```

## When to Enable

### Step 6 (Enhance Numbers)
Enable when you want to:
- Add additional context to financial numbers
- Improve number attribution accuracy
- Test RAG agent enhancements

### Step 7 (Track Chronological)
Enable when you want to:
- Track how numbers change across bill versions
- Generate chronological comparison reports
- Analyze fiscal impact trends

## Performance Notes

- Both steps are **non-blocking** and won't fail the pipeline if they error
- Disabling these steps will speed up fiscal note generation
- These steps can be optimized independently without affecting core generation

## Testing

To test these steps individually:
1. Set the flag to `True`
2. Generate a fiscal note for a bill with multiple versions
3. Check the output directory for:
   - Step 6: `enhanced_numbers.json`
   - Step 7: `chronological_tracking.json` and `tracking_summary.json`

## Future Optimization

When ready to optimize:
1. Review the step implementation files
2. Profile performance bottlenecks
3. Test with various bill types and sizes
4. Re-enable once optimized
