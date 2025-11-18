#!/usr/bin/env python3
"""
Script to generate a new requirements.txt file with specific versions from a snapshot.

This script reads the current requirements.txt and matches packages with their
exact versions from requirements_snapshot.txt to create a fully pinned requirements file.
"""

import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional


def parse_package_name(line: str) -> Optional[str]:
    """
    Extract package name from a requirement line.
    Handles various formats like:
    - package==1.0.0
    - package>=1.0.0
    - package[extra]==1.0.0
    - package @ file://...
    """
    line = line.strip()
    if not line or line.startswith('#'):
        return None
    
    # Remove comments
    line = line.split('#')[0].strip()
    if not line:
        return None
    
    # Handle @ file:// format
    if ' @ ' in line:
        package_name = line.split(' @ ')[0].strip()
    else:
        # Handle regular format with version specifiers
        # Split on common version operators
        for op in ['==', '>=', '<=', '>', '<', '~=', '!=']:
            if op in line:
                package_name = line.split(op)[0].strip()
                break
        else:
            # No version specifier found
            package_name = line.strip()
    
    # Remove extras (e.g., package[extra] -> package)
    if '[' in package_name:
        package_name = package_name.split('[')[0].strip()
    
    return package_name.lower() if package_name else None


def parse_snapshot_line(line: str) -> Optional[Tuple[str, str]]:
    """
    Parse a line from the snapshot file and return (package_name, full_line).
    """
    package_name = parse_package_name(line)
    if package_name:
        return (package_name, line.strip())
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
    """Create a mapping of package names to their pinned versions from snapshot."""
    snapshot_map = {}
    
    for line in snapshot_lines:
        result = parse_snapshot_line(line)
        if result:
            package_name, full_line = result
            snapshot_map[package_name] = full_line
    
    return snapshot_map


def process_requirements(
    requirements_lines: List[str], 
    snapshot_map: Dict[str, str]
) -> List[str]:
    """
    Process requirements lines and replace with pinned versions from snapshot.
    """
    output_lines = []
    
    for line in requirements_lines:
        original_line = line.rstrip()
        
        # Keep comments and empty lines as-is
        if not line.strip() or line.strip().startswith('#'):
            output_lines.append(original_line)
            continue
        
        package_name = parse_package_name(line)
        
        if package_name and package_name in snapshot_map:
            # Replace with pinned version from snapshot
            pinned_line = snapshot_map[package_name]
            output_lines.append(pinned_line)
            print(f"✓ Pinned: {package_name} -> {pinned_line}")
        elif package_name:
            # Package not found in snapshot, keep original
            output_lines.append(original_line)
            print(f"⚠ Not found in snapshot: {package_name} (keeping original)")
        else:
            # Couldn't parse package name, keep original
            output_lines.append(original_line)
    
    return output_lines


def main():
    """Main function to process requirements files."""
    # Define file paths
    base_dir = Path(__file__).parent
    src_requirements = base_dir / "src" / "requirements.txt"
    snapshot_file = base_dir / "requirements_snapshot.txt"
    output_file = base_dir / "requirements_pinned.txt"
    
    print("🔍 Reading requirements files...")
    print(f"   Source: {src_requirements}")
    print(f"   Snapshot: {snapshot_file}")
    print(f"   Output: {output_file}")
    print()
    
    # Read files
    requirements_lines = read_requirements_file(src_requirements)
    snapshot_lines = read_requirements_file(snapshot_file)
    
    # Create snapshot mapping
    print("📦 Creating package version mapping from snapshot...")
    snapshot_map = create_snapshot_mapping(snapshot_lines)
    print(f"   Found {len(snapshot_map)} packages in snapshot")
    print()
    
    # Process requirements
    print("🔄 Processing requirements...")
    output_lines = process_requirements(requirements_lines, snapshot_map)
    print()
    
    # Write output file
    print(f"💾 Writing pinned requirements to {output_file}...")
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
    print(f"   Packages pinned from snapshot: {pinned_packages}")
    print(f"   Pinning success rate: {pinned_packages/total_packages*100:.1f}%")


if __name__ == "__main__":
    main()
