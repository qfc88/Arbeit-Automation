#!/usr/bin/env python3
"""
Test script for German date parsing from start_date field
"""

import re
from datetime import datetime
from typing import Optional

def parse_german_start_date(date_str: str) -> Optional[datetime]:
    """Parse German start date formats to datetime"""
    if not date_str:
        return None
    
    print(f"Parsing: '{date_str}'")
    
    # German date patterns commonly found in job postings
    patterns = [
        # "Beginn ab 01.08.2026"
        (r'Beginn ab (\d{1,2})\.(\d{1,2})\.(\d{4})', "Beginn ab DD.MM.YYYY"),
        # "Beginn 01.09.2026"
        (r'Beginn (\d{1,2})\.(\d{1,2})\.(\d{4})', "Beginn DD.MM.YYYY"),
        # "ab 01.08.2026"
        (r'ab (\d{1,2})\.(\d{1,2})\.(\d{4})', "ab DD.MM.YYYY"),
        # Direct date "01.08.2026"
        (r'^(\d{1,2})\.(\d{1,2})\.(\d{4})$', "DD.MM.YYYY"),
        # "zum 01.09.2026"
        (r'zum (\d{1,2})\.(\d{1,2})\.(\d{4})', "zum DD.MM.YYYY"),
        # "01.08.2026" anywhere in text
        (r'(\d{1,2})\.(\d{1,2})\.(\d{4})', "DD.MM.YYYY anywhere"),
    ]
    
    for pattern, description in patterns:
        match = re.search(pattern, date_str)
        if match:
            day, month, year = match.groups()
            try:
                parsed_date = datetime(int(year), int(month), int(day))
                print(f"  [OK] Matched pattern: {description}")
                print(f"  [OK] Extracted date: {parsed_date.strftime('%Y-%m-%d')}")
                return parsed_date
            except ValueError as e:
                print(f"  [X] Invalid date values: {e}")
                continue
    
    # Check for common text patterns that indicate no specific date
    no_date_patterns = [
        'sofort', 'ab sofort', 'nach vereinbarung', 'nach absprache', 
        'flexibel', 'jederzeit', 'individuell'
    ]
    
    date_lower = date_str.lower()
    for pattern in no_date_patterns:
        if pattern in date_lower:
            print(f"  -> No specific date ('{pattern}' found)")
            return None
    
    print(f"  [X] No date pattern matched")
    return None

# Test cases from real data
test_dates = [
    # Real examples from JSON files
    "Beginn ab 01.08.2026",
    "Beginn ab 01.09.2026", 
    "Beginn 01.09.2026 Standort 59821 Arnsberg",
    
    # Other common German formats
    "ab 15.08.2026",
    "zum 01.09.2026",
    "01.08.2026",
    "Ausbildungsbeginn: 01.09.2026",
    
    # No specific date cases
    "ab sofort",
    "nach Vereinbarung",
    "flexibler Beginn",
    
    # Invalid/edge cases
    "",
    None,
    "Beginn ab 32.13.2026",  # Invalid date
    "some text without date",
]

print("Testing German date parsing:\n")

for i, test_date in enumerate(test_dates, 1):
    print(f"Test {i}: {repr(test_date)}")
    result = parse_german_start_date(test_date) if test_date else None
    print(f"Result: {result}")
    print("-" * 50)

print("Date parsing test completed!")