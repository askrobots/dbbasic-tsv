"""
dbbasic-tsv: A pure-Python, filesystem-based database using TSV files
No setup, no dependencies, just import and go
"""

__version__ = "1.0.0"

from .tsv import TSV
from .audit_log import AuditLog, QueryLog, get_audit_log, get_query_log

__all__ = [
    "TSV",
    "AuditLog",
    "QueryLog",
    "get_audit_log",
    "get_query_log"
]