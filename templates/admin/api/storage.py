"""
API endpoint: GET /admin/api/storage
Returns storage statistics for TSV files
"""

import json
from pathlib import Path


def GET(request):
    """Get storage statistics"""
    data_dir = Path("data")

    if not data_dir.exists():
        return json_response({
            'total_mb': 0,
            'used_mb': 0,
            'tables': []
        })

    tables = []
    total_bytes = 0

    for tsv_file in data_dir.glob("*.tsv"):
        try:
            stat = tsv_file.stat()
            size_kb = stat.st_size / 1024

            # Format size
            if size_kb < 1:
                size_str = f"{stat.st_size} B"
            elif size_kb < 1024:
                size_str = f"{size_kb:.1f} KB"
            else:
                size_str = f"{size_kb/1024:.1f} MB"

            tables.append({
                'name': tsv_file.stem,
                'size': size_str,
                'size_bytes': stat.st_size
            })

            total_bytes += stat.st_size
        except Exception as e:
            print(f"Error reading {tsv_file}: {e}")
            continue

    # Sort by size (largest first)
    tables.sort(key=lambda t: t['size_bytes'], reverse=True)

    used_mb = total_bytes / (1024 * 1024)

    # Estimate total available (could be from disk stats in real impl)
    # For now, just show a reasonable default
    total_mb = max(1000, used_mb * 2)

    return json_response({
        'total_mb': round(total_mb, 1),
        'used_mb': round(used_mb, 2),
        'tables': tables
    })


def json_response(data, status=200):
    """Helper to return JSON response"""
    return {
        'status': status,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps(data)
    }
