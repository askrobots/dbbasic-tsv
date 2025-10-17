"""
API endpoint: GET /admin/api/query
Query TSV table with filters and limits
"""

import json
from pathlib import Path
from dbbasic.tsv import TSV


def GET(request):
    """Query a TSV table"""
    params = request.get('params', {})

    table_name = params.get('table')
    where_clause = params.get('where', '')
    limit = int(params.get('limit', 100))

    if not table_name:
        return json_response({'error': 'table parameter required'}, 400)

    try:
        # Open table
        tsv = TSV(table_name, data_dir="data")

        # Parse where clause (simple key=value format)
        filters = {}
        if where_clause:
            if '=' in where_clause:
                key, val = where_clause.split('=', 1)
                filters[key.strip()] = val.strip()

        # Query with filters
        if filters:
            results = list(tsv.query(**filters))
        else:
            results = list(tsv.all())

        # Apply limit
        results = results[:limit]

        # Get columns from first result or table schema
        columns = []
        if results:
            columns = list(results[0].keys())
        else:
            # Try to get columns from file header
            tsv_path = Path("data") / f"{table_name}.tsv"
            if tsv_path.exists():
                with open(tsv_path, 'r') as f:
                    first_line = f.readline().strip()
                    columns = first_line.split('\t')

        return json_response({
            'columns': columns,
            'rows': results,
            'count': len(results)
        })

    except FileNotFoundError:
        return json_response({'error': f'Table {table_name} not found'}, 404)
    except Exception as e:
        return json_response({'error': str(e)}, 500)


def json_response(data, status=200):
    """Helper to return JSON response"""
    return {
        'status': status,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps(data)
    }
