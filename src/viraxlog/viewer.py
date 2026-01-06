#!/usr/bin/env python3
"""
ViraxLog - CLI Visualization Tool
Allows reading and filtering logs directly from the terminal with color coding.
"""

import sqlite3
import argparse
import json
import os
import sys
from typing import Optional

# ANSI Color Configuration for Terminal
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'

LEVEL_COLORS = {
    "DEBUG": Colors.BLUE,
    "INFO": Colors.GREEN,
    "WARNING": Colors.YELLOW,
    "ERROR": Colors.RED,
    "CRITICAL": Colors.RED + Colors.BOLD,
    "FATAL": Colors.RED + Colors.BOLD,
    "TRACE": Colors.DIM + Colors.CYAN,
}

def format_level(level: str) -> str:
    """Applies color coding to the log level string."""
    lvl_upper = level.upper()
    color = LEVEL_COLORS.get(lvl_upper, Colors.ENDC)
    return f"{color}{lvl_upper:<8}{Colors.ENDC}"

def view_logs(db_path: str, limit: int, category: Optional[str] = None, level: Optional[str] = None):
    """Fetches and displays logs from the SQLite database."""
    if not os.path.exists(db_path):
        print(f"{Colors.RED}Error: Database '{db_path}' not found.{Colors.ENDC}")
        return

    try:
        # Connect with timeout to avoid locking issues with the active logger
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Build query with dynamic filtering
        query = "SELECT id, timestamp, level, category, source, data FROM registry"
        params = []
        conditions = []

        if category:
            conditions.append("category LIKE ?")
            params.append(f"%{category}%")
        if level:
            conditions.append("level = ?")
            params.append(level.upper())

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        rows = cursor.execute(query, params).fetchall()

        # Header
        header = f"{'ID':<5} | {'TIMESTAMP':<19} | {'LEVEL':<8} | {'CATEGORY':<12} | {'DATA'}"
        print(f"\n{Colors.BOLD}{header}{Colors.ENDC}")
        print("-" * 120)

        # Display rows (reversed to keep chronological order on screen)
        for r in reversed(rows):
            lvl = format_level(r['level'])
            ts = f"{Colors.CYAN}{r['timestamp'][:19]}{Colors.ENDC}"
            cat = f"{r['category'][:12]:<12}"
            
            # Smart Data Formatting
            raw_data = r['data']
            try:
                # If it's valid JSON, we parse and re-dump to ensure it's compact
                data_obj = json.loads(raw_data)
                data_str = json.dumps(data_obj, ensure_ascii=False)
            except:
                data_str = raw_data

            # Truncate extremely long data for terminal readability
            if len(data_str) > 80:
                data_str = data_str[:77] + "..."

            print(f"{r['id']:<5} | {ts} | {lvl} | {cat} | {data_str}")

        print(f"\n{Colors.DIM}Total logs displayed: {len(rows)} (Source: {db_path}){Colors.ENDC}\n")

    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Viewer closed.{Colors.ENDC}")
    except Exception as e:
        print(f"{Colors.RED}Read error: {e}{Colors.ENDC}")
    finally:
        if 'conn' in locals():
            conn.close()

def main():
    parser = argparse.ArgumentParser(
        description="ViraxLog CLI Viewer - Secure Log Inspection",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("--db", default="virax_universal.db", help="Path to SQLite database")
    parser.add_argument("-n", "--limit", type=int, default=30, help="Number of logs to show")
    parser.add_argument("-c", "--category", help="Filter by category (partial match)")
    parser.add_argument("-l", "--level", help="Filter by level (INFO, ERROR, etc.)")

    args = parser.parse_args()
    
    # Hide traceback on simple errors
    try:
        view_logs(args.db, args.limit, args.category, args.level)
    except Exception as e:
        print(f"Critical error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()