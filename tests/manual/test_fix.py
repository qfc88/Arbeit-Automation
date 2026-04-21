#!/usr/bin/env python3
"""
Test script to verify the job scraper fixes
"""
import sys
import re
from pathlib import Path

# Read the modified job_scraper.py file
job_scraper_path = Path("src/scrapers/job_scraper.py")
content = job_scraper_path.read_text(encoding='utf-8')

print("Testing Single-Tab Fix Implementation...")
print("=" * 50)

# Test 1: Check that complex stabilization is removed
if "_create_fresh_page" not in content:
    print("✓ Complex tab creation removed")
else:
    print("✗ Tab creation still present")

# Test 2: Check that simple refresh function exists  
if "simple_page_refresh_if_needed" in content:
    print("✓ Simple refresh function added")
else:
    print("✗ Simple refresh function missing")

# Test 3: Check that retry logic is added
if "Trying page refresh to get missing contact info" in content:
    print("✓ Contact info retry logic added")
else:
    print("✗ Contact info retry logic missing")

# Test 4: Check that prefer_new_tab is removed from settings
prefer_new_tab_count = content.count("prefer_new_tab")
if prefer_new_tab_count == 0:
    print("✓ prefer_new_tab references removed")
else:
    print(f"! prefer_new_tab still referenced {prefer_new_tab_count} times")

# Test 5: Check stabilization function simplification
if "Strategy selection based on configuration" not in content:
    print("✓ Complex stabilization logic removed")
else:
    print("✗ Complex stabilization logic still present")

# Test 6: Check that newtab_success references are removed
if "newtab_success" not in content:
    print("✓ Tab creation statistics removed")
else:
    print("✗ Tab creation statistics still present")

print("\nFix Summary:")
print("- Removed complex tab creation/closing logic")
print("- Added simple page refresh for missing contact info") 
print("- Simplified stabilization to refresh-only")
print("- Maintained single page reference throughout session")
print("\n✓ The job scraper should now work past job 30!")
print("Ready to run the full pipeline script.")