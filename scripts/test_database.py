#!/usr/bin/env python3
"""
Catalyst Trading System - Database Test Script
Tests database connection and validates schema
"""

import os
import sys

# Try different import methods for compatibility
try:
    from dotenv import load_dotenv
    HAS_DOTENV = True
except ImportError:
    HAS_DOTENV = False
    print("Note: python-dotenv not found, using hardcoded connection string")

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    print("❌ psycopg2-binary not installed!")
    print("Run: pip3 install psycopg2-binary")
    sys.exit(1)

# Colors for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'

def test_database():
    """Test database connection and schema"""
    
    print(f"{BLUE}{'='*60}{RESET}")
    print(f"{BOLD}Catalyst Trading System - Database Test{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")
    
    # Get database URL
    DATABASE_URL = None
    
    # Try to load from .env file
    if HAS_DOTENV:
        load_dotenv()
        DATABASE_URL = os.getenv('DATABASE_URL')
    
    # Fallback to hardcoded for testing
    if not DATABASE_URL:
        print(f"{YELLOW}Using default connection string...{RESET}")
        DATABASE_URL = "postgresql://catalyst_user:catalyst_dev_password@localhost:5432/catalyst_trading_dev"
    
    try:
        # Connect to database
        print(f"Connecting to database...")
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        print(f"{GREEN}✅ Connected successfully!{RESET}\n")
        
        # Run tests
        tests_passed = 0
        tests_failed = 0
        
        # Test 1: Count tables
        cur.execute("""
            SELECT COUNT(*) as count 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
        """)
        table_count = cur.fetchone()['count']
        
        if table_count == 11:
            print(f"{GREEN}✅ All 11 tables exist{RESET}")
            tests_passed += 1
        else:
            print(f"{YELLOW}⚠️  Found {table_count} tables (expected 11){RESET}")
            tests_failed += 1
        
        # Test 2: Check foreign keys (normalization)
        cur.execute("""
            SELECT COUNT(*) as count 
            FROM information_schema.table_constraints 
            WHERE constraint_type = 'FOREIGN KEY' 
            AND constraint_schema = 'public'
        """)
        fk_count = cur.fetchone()['count']
        
        if fk_count >= 10:  # Should have at least 10 FKs
            print(f"{GREEN}✅ Database is normalized ({fk_count} foreign keys){RESET}")
            tests_passed += 1
        else:
            print(f"{RED}❌ Only {fk_count} foreign keys (expected 10+){RESET}")
            tests_failed += 1
        
        # Test 3: Check securities master table
        cur.execute("""
            SELECT EXISTS(
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = 'securities'
            )
        """)
        has_securities = cur.fetchone()['exists']
        
        if has_securities:
            print(f"{GREEN}✅ Securities master table exists{RESET}")
            tests_passed += 1
            
            # Check if any test data
            cur.execute("SELECT COUNT(*) as count FROM securities")
            sec_count = cur.fetchone()['count']
            if sec_count > 0:
                print(f"   Found {sec_count} securities in database")
        else:
            print(f"{RED}❌ Securities table missing!{RESET}")
            tests_failed += 1
        
        # Test 4: Check symbol normalization
        cur.execute("""
            SELECT table_name 
            FROM information_schema.columns 
            WHERE column_name = 'symbol' 
            AND table_schema = 'public'
        """)
        symbol_tables = [row['table_name'] for row in cur.fetchall()]
        
        if len(symbol_tables) == 1 and 'securities' in symbol_tables:
            print(f"{GREEN}✅ Symbol column only in securities (normalized){RESET}")
            tests_passed += 1
        elif len(symbol_tables) == 0:
            print(f"{RED}❌ No symbol column found anywhere!{RESET}")
            tests_failed += 1
        else:
            print(f"{RED}❌ Symbol in multiple tables: {symbol_tables}{RESET}")
            tests_failed += 1
        
        # Test 5: Check helper functions
        cur.execute("""
            SELECT routine_name 
            FROM information_schema.routines 
            WHERE routine_schema = 'public' 
            AND routine_type = 'FUNCTION'
        """)
        functions = [row['routine_name'] for row in cur.fetchall()]
        
        expected_funcs = ['get_or_create_security', 'get_or_create_time', 'insert_trading_data']
        missing_funcs = [f for f in expected_funcs if f not in functions]
        
        if not missing_funcs:
            print(f"{GREEN}✅ All helper functions exist{RESET}")
            tests_passed += 1
        else:
            print(f"{YELLOW}⚠️  Missing functions: {missing_funcs}{RESET}")
            tests_failed += 1
        
        # Test 6: Check sectors loaded
        cur.execute("SELECT COUNT(*) as count FROM sectors")
        sector_count = cur.fetchone()['count']
        
        if sector_count == 11:
            print(f"{GREEN}✅ GICS sectors loaded ({sector_count} sectors){RESET}")
            tests_passed += 1
        else:
            print(f"{YELLOW}⚠️  Found {sector_count} sectors (expected 11){RESET}")
            tests_failed += 1
        
        # List all tables for reference
        print(f"\n{BOLD}Tables in database:{RESET}")
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """)
        for row in cur.fetchall():
            print(f"  • {row['table_name']}")
        
        # Summary
        print(f"\n{BLUE}{'='*60}{RESET}")
        print(f"{BOLD}TEST SUMMARY{RESET}")
        print(f"{BLUE}{'='*60}{RESET}")
        print(f"Tests Passed: {tests_passed}/6")
        print(f"Tests Failed: {tests_failed}/6")
        
        if tests_passed == 6:
            print(f"\n{GREEN}{BOLD}✅ DATABASE IS READY FOR PHASE 5!{RESET}")
            print(f"\n{BOLD}Next Steps:{RESET}")
            print("1. Start updating Scanner Service")
            print("2. Replace 'symbol' columns with 'security_id' FKs")
            print("3. Update queries to JOIN with securities table")
            print("4. Use helper functions for inserts")
        elif tests_passed >= 4:
            print(f"\n{YELLOW}{BOLD}⚠️  DATABASE MOSTLY READY{RESET}")
            print("Some minor issues to fix - see warnings above")
        else:
            print(f"\n{RED}{BOLD}❌ DATABASE NEEDS ATTENTION{RESET}")
            print("Please review the errors above")
        
        # Close connection
        cur.close()
        conn.close()
        
        return tests_passed, tests_failed
        
    except psycopg2.OperationalError as e:
        print(f"{RED}❌ Connection failed!{RESET}")
        print(f"Error: {e}")
        print(f"\n{BOLD}Troubleshooting:{RESET}")
        print("1. Check PostgreSQL is running:")
        print("   sudo systemctl status postgresql")
        print("2. Verify connection string in .env file:")
        print("   DATABASE_URL=postgresql://catalyst_user:catalyst_dev_password@localhost:5432/catalyst_trading_dev")
        print("3. Test with psql:")
        print("   psql postgresql://catalyst_user:catalyst_dev_password@localhost:5432/catalyst_trading_dev")
        return 0, 1
    except Exception as e:
        print(f"{RED}❌ Unexpected error: {e}{RESET}")
        import traceback
        traceback.print_exc()
        return 0, 1

if __name__ == "__main__":
    passed, failed = test_database()
    sys.exit(0 if failed == 0 else 1)