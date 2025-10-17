"""
API endpoint: GET /admin/api/tables
Returns list of all TSV tables with metadata
"""

import json
import os
from pathlib import Path


def GET(request):
    """List all TSV tables in data/ directory"""
    data_dir = Path("data")

    if not data_dir.exists():
        return json_response([])

    tables = []

    for tsv_file in data_dir.glob("*.tsv"):
        try:
            # Get file stats
            stat = tsv_file.stat()
            size_kb = stat.st_size / 1024

            # Read first line to get columns
            with open(tsv_file, 'r') as f:
                first_line = f.readline().strip()
                columns = first_line.split('\t') if first_line else []

                # Count rows (excluding header)
                row_count = sum(1 for line in f)

            # Format size
            if size_kb < 1:
                size_str = f"{stat.st_size} B"
            elif size_kb < 1024:
                size_str = f"{size_kb:.1f} KB"
            else:
                size_str = f"{size_kb/1024:.1f} MB"

            tables.append({
                'name': tsv_file.stem,
                'columns': columns,
                'rows': row_count,
                'size': size_str,
                'size_bytes': stat.st_size
            })
        except Exception as e:
            print(f"Error reading {tsv_file}: {e}")
            continue

    # Sort by name
    tables.sort(key=lambda t: t['name'])

    return json_response(tables)


def json_response(data, status=200):
    """Helper to return JSON response"""
    return {
        'status': status,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps(data)
    }
