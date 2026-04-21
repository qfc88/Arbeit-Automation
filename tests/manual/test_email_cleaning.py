#!/usr/bin/env python3
"""
Test script for the improved email cleaning function
"""

import sys
from pathlib import Path
import re
from typing import Optional

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

def clean_email(email: str) -> Optional[str]:
    """Clean and validate email address - improved version"""
    if not email:
        return None
    
    email = email.strip()
    
    # Filter out URL parameters, links, and malformed entries
    if (email.startswith('?body=') or 
        email.startswith('http') or 
        email.startswith('mailto:') or
        'azubi.de' in email or
        len(email) > 100):  # Reasonable email length limit
        print(f"[X] Filtered out invalid email format: {email[:50]}...")
        return None
    
    email = email.lower()
    
    # Enhanced email validation
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if re.match(email_pattern, email):
        # Additional checks for common issues
        if email.count('@') != 1:
            print(f"[X] Invalid email format (multiple @): {email}")
            return None
        if email.startswith('.') or email.endswith('.'):
            print(f"[X] Invalid email format (starts/ends with dot): {email}")
            return None
        if '..' in email:
            print(f"[X] Invalid email format (double dots): {email}")
            return None
        print(f"[OK] Valid email: {email}")
        return email
    
    print(f"[X] Invalid email format: {email}")
    return None

# Test cases
test_emails = [
    # Valid emails
    "bewerbung@lidl.de",
    "info@company.com",
    "test.email@example.org",
    "contact123@test-domain.co.uk",
    
    # Invalid emails - URL parameters (real problematic cases)
    "?body=ausbildung%20tiefbaufacharbeiter%3ain%202026%0ahttps%3a%2f%2fwww.azubi.de%2fausbildungsplatz%2f10379212-p",
    "?body=ausbildung%20mechatroniker%3ain%202026%0ahttps%3a%2f%2fwww.azubi.de%2fausbildungsplatz%2f10357235-p",
    
    # Invalid emails - URLs
    "http://www.company.com/contact",
    "https://jobs.example.com",
    
    # Invalid emails - Other issues
    "mailto:info@company.com",
    "email.with..double.dots@company.com",
    ".startswithdot@company.com",
    "endswithddot.@company.com",
    "no-at-symbol.company.com",
    "multiple@@company.com",
    "a" * 101 + "@company.com",  # Too long
    
    # Edge cases
    "",
    None,
    "   contact@company.com   ",  # Should be trimmed
]

print("Testing improved email cleaning function:\n")

for i, test_email in enumerate(test_emails, 1):
    print(f"Test {i}: {repr(test_email)}")
    result = clean_email(test_email)
    print(f"Result: {repr(result)}\n")

print("Email cleaning function test completed!")