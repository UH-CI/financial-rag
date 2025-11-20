#!/usr/bin/env python3
"""
Final script to generate a fully clean requirements.txt with PyPI-compatible versions.
"""

import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional


# Manual mapping for packages that need special handling
PACKAGE_MAPPING = {
    'google_auth': 'google-auth',
    'pypdf2': 'PyPDF2',
    'pymupdf': 'PyMuPDF',
}

# Fallback versions for packages not found in snapshot
FALLBACK_VERSIONS = {
    'typing-extensions': '4.12.2',
    'google-auth': '2.41.1',
}


def normalize_package_name(name: str) -> str:
    """Normalize package name for comparison."""
    return name.lower().replace('_', '-').replace('.', '-')


def parse_package_name(line: str) -> Optional[str]:
    """Extract package name from a requirement line."""
    line = line.strip()
    if not line or line.startswith('#'):
        return None
    
    line = line.split('#')[0].strip()
    if not line:
        return None
    
    if ' @ ' in line:
        package_name = line.split(' @ ')[0].strip()
    else:
        for op in ['==', '>=', '<=', '>', '<', '~=', '!=']:
            if op in line:
                package_name = line.split(op)[0].strip()
                break
        else:
            package_name = line.strip()
    
    if '[' in package_name:
        package_name = package_name.split('[')[0].strip()
    
    return normalize_package_name(package_name) if package_name else None


def extract_version_from_conda_path(line: str) -> Optional[str]:
    """Extract version from conda file path."""
    version_patterns = [
        r'_(\d+\.\d+\.\d+(?:\.\d+)?)-',
        r'-(\d+\.\d+\.\d+(?:\.\d+)?)-',
        r'/(\d+\.\d+\.\d+(?:\.\d+)?)/',
        r'(\d+\.\d+\.\d+(?:\.\d+)?)-cp\d+',
    ]
    
    for pattern in version_patterns:
        match = re.search(pattern, line)
        if match:
            return match.group(1)
    
    return None


def parse_snapshot_line(line: str) -> Optional[Tuple[str, str]]:
    """Parse snapshot line and return (normalized_name, clean_requirement)."""
    original_line = line.strip()
    package_name = parse_package_name(original_line)
    
    if not package_name:
        return None
    
    # Handle conda file paths
    if ' @ file://' in original_line:
        version = extract_version_from_conda_path(original_line)
        if version:
            # Get the original package name before normalization for output
            orig_name = original_line.split(' @ ')[0].strip()
            return (package_name, f"{orig_name}=={version}")
        else:
            return None
    
    # Handle standard version format
    if '==' in original_line:
        return (package_name, original_line)
    
    return None


def read_requirements_file(file_path: Path) -> List[str]:
    """Read and return all lines from a requirements file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.readlines()
    except FileNotFoundError:
        print(f"Error: File {file_path} not found")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        sys.exit(1)


def create_snapshot_mapping(snapshot_lines: List[str]) -> Dict[str, str]:
    """Create a mapping of normalized package names to their pinned versions."""
    snapshot_map = {}
    
    for line in snapshot_lines:
        result = parse_snapshot_line(line)
        if result:
            normalized_name, clean_requirement = result
            snapshot_map[normalized_name] = clean_requirement
    
    return snapshot_map


def get_original_package_name(line: str) -> str:
    """Get the original package name from requirements line."""
    line = line.strip().split('#')[0].strip()
    
    if ' @ ' in line:
        return line.split(' @ ')[0].strip()
    
    for op in ['==', '>=', '<=', '>', '<', '~=', '!=']:
        if op in line:
            return line.split(op)[0].strip()
    
    return line.strip()


def process_requirements(
    requirements_lines: List[str], 
    snapshot_map: Dict[str, str]
) -> List[str]:
    """Process requirements lines and replace with pinned versions."""
    output_lines = []
    
    for line in requirements_lines:
        original_line = line.rstrip()
        
        # Keep comments and empty lines as-is
        if not line.strip() or line.strip().startswith('#'):
            output_lines.append(original_line)
            continue
        
        normalized_name = parse_package_name(line)
        original_name = get_original_package_name(line)
        
        if normalized_name:
            # Check if we have it in snapshot
            if normalized_name in snapshot_map:
                pinned_line = snapshot_map[normalized_name]
                output_lines.append(pinned_line)
                print(f"✓ Pinned: {original_name} -> {pinned_line}")
            
            # Check manual mapping
            elif normalized_name in PACKAGE_MAPPING:
                mapped_name = normalize_package_name(PACKAGE_MAPPING[normalized_name])
                if mapped_name in snapshot_map:
                    pinned_line = snapshot_map[mapped_name]
                    output_lines.append(pinned_line)
                    print(f"✓ Mapped & Pinned: {original_name} -> {pinned_line}")
                else:
                    output_lines.append(original_line)
                    print(f"⚠ Mapped but not found: {original_name}")
            
            # Check fallback versions
            elif normalized_name in FALLBACK_VERSIONS:
                fallback_line = f"{original_name}=={FALLBACK_VERSIONS[normalized_name]}"
                output_lines.append(fallback_line)
                print(f"✓ Fallback: {original_name} -> {fallback_line}")
            
            else:
                # Package not found, keep original
                output_lines.append(original_line)
                print(f"⚠ Not found: {original_name} (keeping original)")
        else:
            # Couldn't parse, keep original
            output_lines.append(original_line)
    
    return output_lines


def main():
    """Main function to process requirements files."""
    base_dir = Path(__file__).parent
    src_requirements = base_dir / "src" / "requirements.txt"
    snapshot_file = base_dir / "requirements_snapshot.txt"
    output_file = base_dir / "requirements_final_pinned.txt"
    
    print("🔍 Reading requirements files...")
    print(f"   Source: {src_requirements}")
    print(f"   Snapshot: {snapshot_file}")
    print(f"   Output: {output_file}")
    print()
    
    # Read files
    requirements_lines = read_requirements_file(src_requirements)
    snapshot_lines = read_requirements_file(snapshot_file)
    
    # Create snapshot mapping
    print("📦 Creating package version mapping...")
    snapshot_map = create_snapshot_mapping(snapshot_lines)
    print(f"   Found {len(snapshot_map)} packages in snapshot")
    print()
    
    # Process requirements
    print("🔄 Processing requirements...")
    output_lines = process_requirements(requirements_lines, snapshot_map)
    print()
    
    # Write output file
    print(f"💾 Writing final pinned requirements to {output_file}...")
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            for line in output_lines:
                f.write(line + '\n')
        print(f"✅ Successfully created {output_file}")
    except Exception as e:
        print(f"❌ Error writing output file: {e}")
        sys.exit(1)
    
    # Summary
    total_packages = sum(1 for line in requirements_lines if parse_package_name(line))
    pinned_packages = sum(1 for line in output_lines 
                         if parse_package_name(line) and '==' in line)
    
    print()
    print("📊 Summary:")
    print(f"   Total packages in requirements: {total_packages}")
    print(f"   Packages pinned: {pinned_packages}")
    print(f"   Pinning success rate: {pinned_packages/total_packages*100:.1f}%")


if __name__ == "__main__":
    main()
