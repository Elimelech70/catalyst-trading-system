#!/usr/bin/env python3
"""
Catalyst Trading System - Database Validation Script
Name of file: validate_database.py
Version: 1.0.0
Last Updated: 2025-11-18
Purpose: Validate database creation and provide next steps

REVISION HISTORY:
v1.0.0 (2025-11-18) - Initial validation script
  - Verify all tables created
  - Check normalization
  - Test helper functions
  - Provide next steps for Phase 5
"""

import os
import sys
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

# Load environment variables
load_dotenv()

# ANSI color codes
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'

def print_header(title):
    """Print formatted header"""
    print(f"\n{BLUE}{'=' * 60}{RESET}")
    print(f"{BOLD}{title}{RESET}")
    print(f"{BLUE}{'=' * 60}{RESET}")

def print_success(message):
    """Print success message"""
    print(f"{GREEN}✅ {message}{RESET}")

def print_error(message):
    """Print error message"""
    print(f"{RED}❌ {message}{RESET}")

def print_warning(message):
    """Print warning message"""
    print(f"{YELLOW}⚠️  {message}{RESET}")

def print_info(message):
    """Print info message"""
    print(f"   {message}")

def validate_database():
    """Validate database creation and structure"""
    
    try:
        # Get connection string
        DATABASE_URL = os.getenv('DATABASE_URL')
        if not DATABASE_URL:
            print_error("DATABASE_URL not found in .env file")
            return False
        
        print_header("DATABASE VALIDATION REPORT")
        print_info(f"Connecting to: {DATABASE_URL.split('@')[1]}")
        
        # Connect to database
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        print_success("Connected to database successfully!")
        
        # ======================================================================
        # 1. CHECK TABLES EXIST
        # ======================================================================
        print_header("1. CHECKING TABLES")
        
        expected_tables = [
            # Dimension tables
            ('sectors', 'Dimension', 'GICS sector classification'),
            ('securities', 'Dimension', 'Master security data - SINGLE SOURCE OF TRUTH'),
            ('time_dimension', 'Dimension', 'Time as entity'),
            
            # Fact tables
            ('trading_history', 'Fact', 'OHLCV price bars'),
            ('news_sentiment', 'Fact', 'News events & catalysts'),
            ('technical_indicators', 'Fact', 'Technical analysis metrics'),
            
            # Operations tables
            ('trading_cycles', 'Operations', 'Daily workflow orchestration'),
            ('positions', 'Operations', 'Trading positions'),
            ('orders', 'Operations', 'Order execution records'),
            ('scan_results', 'Operations', 'Market scanning candidates'),
            ('risk_events', 'Operations', 'Risk management log')
        ]
        
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """)
        
        existing_tables = [row['table_name'] for row in cursor.fetchall()]
        
        tables_ok = True
        for table_name, table_type, description in expected_tables:
            if table_name in existing_tables:
                print_success(f"{table_name:25} [{table_type:10}] - {description}")
            else:
                print_error(f"{table_name:25} MISSING!")
                tables_ok = False
        
        if tables_ok:
            print_info(f"\nTotal: {len(existing_tables)} tables created")
        
        # ======================================================================
        # 2. CHECK NORMALIZATION (CRITICAL!)
        # ======================================================================
        print_header("2. NORMALIZATION CHECK (3NF)")
        
        # Check for foreign keys
        cursor.execute("""
            SELECT 
                tc.table_name,
                kcu.column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
            ORDER BY tc.table_name
        """)
        
        foreign_keys = cursor.fetchall()
        
        if foreign_keys:
            print_success(f"Found {len(foreign_keys)} foreign key relationships")
            
            # Group by table
            fk_by_table = {}
            for fk in foreign_keys:
                table = fk['table_name']
                if table not in fk_by_table:
                    fk_by_table[table] = []
                fk_by_table[table].append(f"{fk['column_name']} → {fk['foreign_table_name']}.{fk['foreign_column_name']}")
            
            for table, fks in fk_by_table.items():
                print_info(f"{table}:")
                for fk in fks:
                    print_info(f"  └─ {fk}")
        else:
            print_error("No foreign keys found - Database is NOT normalized!")
            return False
        
        # Check for symbol duplication (should ONLY be in securities table)
        cursor.execute("""
            SELECT table_name, column_name 
            FROM information_schema.columns 
            WHERE column_name = 'symbol' 
            AND table_schema = 'public'
            ORDER BY table_name
        """)
        
        symbol_tables = cursor.fetchall()
        
        print(f"\n{BOLD}Symbol Column Check:{RESET}")
        if len(symbol_tables) == 1 and symbol_tables[0]['table_name'] == 'securities':
            print_success("Symbol column exists ONLY in securities table (properly normalized)")
        else:
            print_error("Symbol column found in multiple tables (denormalized!)")
            for row in symbol_tables:
                print_info(f"  - {row['table_name']}.{row['column_name']}")
        
        # ======================================================================
        # 3. CHECK HELPER FUNCTIONS
        # ======================================================================
        print_header("3. HELPER FUNCTIONS")
        
        cursor.execute("""
            SELECT routine_name 
            FROM information_schema.routines 
            WHERE routine_schema = 'public' 
            AND routine_type = 'FUNCTION'
            ORDER BY routine_name
        """)
        
        functions = [row['routine_name'] for row in cursor.fetchall()]
        
        expected_functions = [
            'get_or_create_security',
            'get_or_create_time',
            'insert_trading_data'
        ]
        
        for func_name in expected_functions:
            if func_name in functions:
                print_success(f"{func_name}() created")
            else:
                print_error(f"{func_name}() MISSING")
        
        # Test helper functions
        print(f"\n{BOLD}Testing Helper Functions:{RESET}")
        
        try:
            # Test get_or_create_security
            cursor.execute("SELECT get_or_create_security('AAPL', 'Apple Inc.', 'NASDAQ')")
            security_id = cursor.fetchone()['get_or_create_security']
            print_success(f"get_or_create_security('AAPL') returned security_id: {security_id}")
            
            # Test get_or_create_time
            cursor.execute("SELECT get_or_create_time(NOW())")
            time_id = cursor.fetchone()['get_or_create_time']
            print_success(f"get_or_create_time(NOW()) returned time_id: {time_id}")
            
            # Commit the test inserts
            conn.commit()
            
        except Exception as e:
            print_error(f"Helper function test failed: {e}")
        
        # ======================================================================
        # 4. CHECK VIEWS
        # ======================================================================
        print_header("4. VIEWS & MATERIALIZED VIEWS")
        
        cursor.execute("""
            SELECT viewname, definition LIKE '%MATERIALIZED%' as is_materialized
            FROM pg_views 
            WHERE schemaname = 'public'
            ORDER BY viewname
        """)
        
        views = cursor.fetchall()
        
        cursor.execute("""
            SELECT matviewname 
            FROM pg_matviews 
            WHERE schemaname = 'public'
            ORDER BY matviewname
        """)
        
        matviews = [row['matviewname'] for row in cursor.fetchall()]
        
        expected_views = ['v_securities_latest', 'v_daily_performance']
        expected_matviews = ['mv_security_metrics', 'mv_daily_summary']
        
        for view_name in expected_views:
            if any(v['viewname'] == view_name for v in views):
                print_success(f"View: {view_name}")
            else:
                print_warning(f"View: {view_name} MISSING")
        
        for matview_name in expected_matviews:
            if matview_name in matviews:
                print_success(f"Materialized View: {matview_name}")
            else:
                print_warning(f"Materialized View: {matview_name} MISSING")
        
        # ======================================================================
        # 5. CHECK DATA
        # ======================================================================
        print_header("5. DATA CHECK")
        
        # Check sectors
        cursor.execute("SELECT COUNT(*) as count FROM sectors")
        sector_count = cursor.fetchone()['count']
        if sector_count > 0:
            print_success(f"Sectors table has {sector_count} records (GICS sectors loaded)")
        else:
            print_warning("Sectors table is empty")
        
        # Check securities
        cursor.execute("SELECT COUNT(*) as count FROM securities")
        security_count = cursor.fetchone()['count']
        if security_count > 0:
            print_success(f"Securities table has {security_count} records")
            
            # Show sample securities
            cursor.execute("""
                SELECT s.symbol, s.company_name, sec.sector_name 
                FROM securities s
                LEFT JOIN sectors sec ON sec.sector_id = s.sector_id
                LIMIT 3
            """)
            print_info("Sample securities:")
            for row in cursor.fetchall():
                print_info(f"  - {row['symbol']}: {row['company_name']} ({row['sector_name'] or 'No sector'})")
        else:
            print_info("Securities table is empty (normal for fresh install)")
        
        # ======================================================================
        # 6. PHASE 5 READINESS CHECK
        # ======================================================================
        print_header("6. PHASE 5 READINESS CHECK")
        
        print(f"{BOLD}Schema Logic Fixes Required:{RESET}")
        
        services_to_fix = [
            ('Scanner Service', 'scan_results table with security_id FK'),
            ('Workflow Service', 'trading_cycles orchestration'),
            ('News Service', 'news_sentiment with security_id FK'),
            ('Risk Manager', 'positions & risk_events tables'),
            ('Technical Service', 'technical_indicators with security_id FK'),
            ('Trading Service', 'orders & positions with security_id FK')
        ]
        
        print_info("Services that need updating to use normalized schema:")
        for service, description in services_to_fix:
            print_info(f"  □ {service:20} - {description}")
        
        print(f"\n{BOLD}Key Changes for Each Service:{RESET}")
        print_info("1. Replace symbol VARCHAR with security_id INTEGER")
        print_info("2. Use JOINs to get symbol from securities table")
        print_info("3. Use get_or_create_security() helper function")
        print_info("4. Update all queries to use proper foreign keys")
        
        # ======================================================================
        # SUMMARY
        # ======================================================================
        print_header("VALIDATION SUMMARY")
        
        if tables_ok and len(foreign_keys) > 0:
            print_success("Database is properly created and normalized!")
            print_success("Ready for Phase 5: Schema Logic Fixes")
            
            print(f"\n{BOLD}Next Steps:{RESET}")
            print_info("1. Begin updating services to use normalized schema")
            print_info("2. Start with Scanner Service (first in pipeline)")
            print_info("3. Test each service after updates")
            print_info("4. Use helper functions for all inserts")
            
            print(f"\n{BOLD}Example Query Pattern:{RESET}")
            print(f"{BLUE}-- OLD (Denormalized):{RESET}")
            print_info("SELECT symbol, close FROM trading_history")
            print(f"{GREEN}-- NEW (Normalized):{RESET}")
            print_info("SELECT s.symbol, th.close")
            print_info("FROM trading_history th")
            print_info("JOIN securities s ON s.security_id = th.security_id")
            
            return True
        else:
            print_error("Database validation FAILED")
            print_info("Please check errors above and re-run schema creation")
            return False
        
    except psycopg2.OperationalError as e:
        print_error(f"Connection failed: {e}")
        print_info("\nTroubleshooting:")
        print_info("1. Check PostgreSQL is running: sudo systemctl status postgresql")
        print_info("2. Verify .env file has correct DATABASE_URL")
        print_info("3. Ensure database exists: createdb catalyst_trading_dev")
        return False
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    print(f"{BOLD}Catalyst Trading System - Database Validation{RESET}")
    print(f"Version: 1.0.0")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    success = validate_database()
    
    if success:
        print(f"\n{GREEN}{BOLD}✅ VALIDATION PASSED{RESET}")
    else:
        print(f"\n{RED}{BOLD}❌ VALIDATION FAILED{RESET}")
    
    sys.exit(0 if success else 1)