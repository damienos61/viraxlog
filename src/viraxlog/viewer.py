#!/usr/bin/env python3
"""
ViraxLog - CLI Viewer v2.0
Visualisation colorée et filtrage avancé des logs en terminal.
"""

import sqlite3
import argparse
import json
import os
import sys
from typing import Optional, List, Dict
from datetime import datetime, timedelta

# ========== ANSI COLORS ==========

class Colors:
    """Codes ANSI pour couleurs terminal."""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    UNDERLINE = '\033[4m'


LEVEL_COLORS = {
    "TRACE": Colors.DIM + Colors.CYAN,
    "DEBUG": Colors.BLUE,
    "INFO": Colors.GREEN,
    "WARNING": Colors.YELLOW,
    "ERROR": Colors.RED,
    "CRITICAL": Colors.RED + Colors.BOLD,
    "FATAL": Colors.RED + Colors.BOLD,
}

CATEGORY_COLORS = {
    "AUTH": Colors.BLUE,
    "DATABASE": Colors.CYAN,
    "SECURITY": Colors.RED,
    "PERFORMANCE": Colors.YELLOW,
    "SYSTEM": Colors.GREEN,
}


# ========== FORMATTING ==========

def format_level(level: str) -> str:
    """Applique couleur au niveau."""
    lvl_upper = level.upper()
    color = LEVEL_COLORS.get(lvl_upper, Colors.ENDC)
    return f"{color}{lvl_upper:<9}{Colors.ENDC}"


def format_timestamp(ts: str) -> str:
    """Formate timestamp."""
    return f"{Colors.DIM}{ts[:19]}{Colors.ENDC}"


def format_category(category: str) -> str:
    """Applique couleur catégorie."""
    for key, color in CATEGORY_COLORS.items():
        if key.lower() in category.lower():
            return f"{color}{category:<15}{Colors.ENDC}"
    return f"{category:<15}"


def format_data(data_str: str, max_len: int = 80) -> str:
    """Formate et tronque données."""
    try:
        # Parse JSON si possible
        data_obj = json.loads(data_str)
        data_str = json.dumps(data_obj, ensure_ascii=False, separators=(',', ':'))
    except Exception:
        pass
    
    # Tronque si trop long
    if len(data_str) > max_len:
        return data_str[:max_len-3] + "..."
    return data_str


# ========== DATABASE QUERIES ==========

def build_query(
    category: Optional[str] = None,
    level: Optional[str] = None,
    session_id: Optional[str] = None,
    since_hours: Optional[int] = None,
    search_text: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
) -> tuple:
    """Construit requête SQL avec filtres."""
    sql = "SELECT id, timestamp, level, category, source, data, session_id FROM registry WHERE 1=1"
    params = []
    
    if category:
        sql += " AND category LIKE ?"
        params.append(f"%{category}%")
    
    if level:
        sql += " AND level = ?"
        params.append(level.upper())
    
    if session_id:
        sql += " AND session_id = ?"
        params.append(session_id)
    
    if since_hours:
        since_dt = datetime.now() - timedelta(hours=since_hours)
        sql += " AND timestamp >= ?"
        params.append(since_dt.isoformat())
    
    if search_text:
        sql += " AND (data LIKE ? OR category LIKE ? OR source LIKE ?)"
        like_text = f"%{search_text}%"
        params.extend([like_text, like_text, like_text])
    
    sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    return sql, params


def view_logs(
    db_path: str,
    category: Optional[str] = None,
    level: Optional[str] = None,
    session_id: Optional[str] = None,
    since_hours: Optional[int] = None,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    json_output: bool = False
):
    """Affiche logs avec filtrage."""
    
    if not os.path.exists(db_path):
        print(f"{Colors.RED}Error: Database '{db_path}' not found.{Colors.ENDC}")
        return

    try:
        # Connect read-only
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5)
        conn.row_factory = sqlite3.Row
        
        # Build & execute query
        sql, params = build_query(
            category=category,
            level=level,
            session_id=session_id,
            since_hours=since_hours,
            search_text=search,
            limit=limit,
            offset=offset
        )
        
        rows = conn.execute(sql, params).fetchall()
        
        if not rows:
            print(f"{Colors.DIM}No logs found matching criteria.{Colors.ENDC}")
            conn.close()
            return
        
        # Output
        if json_output:
            output = [dict(r) for r in rows]
            print(json.dumps(output, ensure_ascii=False, indent=2))
        else:
            # Terminal display
            print()
            header = (
                f"{Colors.BOLD}{'ID':<6} | "
                f"{'TIMESTAMP':<19} | {'LEVEL':<9} | "
                f"{'CATEGORY':<15} | "
                f"{'DATA'}{Colors.ENDC}"
            )
            print(header)
            print("-" * 150)
            
            for r in reversed(rows):
                row_str = (
                    f"{r['id']:<6} | "
                    f"{format_timestamp(r['timestamp'])} | "
                    f"{format_level(r['level'])} | "
                    f"{format_category(r['category'])} | "
                    f"{format_data(r['data'])}"
                )
                print(row_str)
        
        # Stats
        total_query = "SELECT COUNT(*) FROM registry"
        total = conn.execute(total_query).fetchone()[0]
        
        print()
        print(f"{Colors.DIM}Displayed: {len(rows)} | Total in DB: {total}{Colors.ENDC}\n")
        
        conn.close()
        
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Viewer interrupted.{Colors.ENDC}")
    except Exception as e:
        print(f"{Colors.RED}Error: {e}{Colors.ENDC}", file=sys.stderr)
        sys.exit(1)


def get_db_stats(db_path: str) -> Dict:
    """Récupère stats DB rapides."""
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        
        total = conn.execute("SELECT COUNT(*) FROM registry").fetchone()[0]
        
        levels = {}
        for level in ["TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "FATAL"]:
            count = conn.execute(
                "SELECT COUNT(*) FROM registry WHERE level = ?", (level,)
            ).fetchone()[0]
            if count > 0:
                levels[level] = count
        
        earliest = conn.execute(
            "SELECT timestamp FROM registry ORDER BY id ASC LIMIT 1"
        ).fetchone()
        latest = conn.execute(
            "SELECT timestamp FROM registry ORDER BY id DESC LIMIT 1"
        ).fetchone()
        
        conn.close()
        
        return {
            "total_entries": total,
            "levels": levels,
            "earliest": earliest[0] if earliest else None,
            "latest": latest[0] if latest else None,
        }
    except Exception as e:
        return {"error": str(e)}


def show_stats(db_path: str):
    """Affiche statistiques DB."""
    if not os.path.exists(db_path):
        print(f"{Colors.RED}Database not found: {db_path}{Colors.ENDC}")
        return
    
    stats = get_db_stats(db_path)
    
    if "error" in stats:
        print(f"{Colors.RED}Error: {stats['error']}{Colors.ENDC}")
        return
    
    print(f"\n{Colors.BOLD}Database Statistics{Colors.ENDC}")
    print("-" * 50)
    print(f"Total Entries: {stats['total_entries']}")
    print(f"Earliest: {stats['earliest']}")
    print(f"Latest: {stats['latest']}")
    print(f"\n{Colors.BOLD}By Level:{Colors.ENDC}")
    for level, count in sorted(stats['levels'].items()):
        color = LEVEL_COLORS.get(level, Colors.ENDC)
        print(f"  {color}{level:<10}{Colors.ENDC}: {count}")
    print()


# ========== CLI ==========

def main():
    parser = argparse.ArgumentParser(
        description=f"{Colors.BOLD}ViraxLog CLI Viewer v2.0{Colors.ENDC}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  viraxlog-viewer --db logs.db
  viraxlog-viewer --db logs.db -l ERROR -n 20
  viraxlog-viewer --db logs.db -c AUTH --since-hours 24
  viraxlog-viewer --db logs.db --stats
        """
    )
    
    parser.add_argument("--db", default="virax.db", help="Database path")
    parser.add_argument("-n", "--limit", type=int, default=50, help="Max logs to show")
    parser.add_argument("-c", "--category", help="Filter by category")
    parser.add_argument("-l", "--level", help="Filter by level (TRACE/DEBUG/INFO/etc)")
    parser.add_argument("-s", "--session", dest="session_id", help="Filter by session ID")
    parser.add_argument("--since-hours", type=int, help="Show last N hours")
    parser.add_argument("--search", help="Search in data/category/source")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--stats", action="store_true", help="Show database statistics")
    
    args = parser.parse_args()
    
    try:
        if args.stats:
            show_stats(args.db)
        else:
            view_logs(
                args.db,
                category=args.category,
                level=args.level,
                session_id=args.session_id,
                since_hours=args.since_hours,
                search=args.search,
                limit=args.limit,
                json_output=args.json
            )
    except Exception as e:
        print(f"{Colors.RED}Fatal error: {e}{Colors.ENDC}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
