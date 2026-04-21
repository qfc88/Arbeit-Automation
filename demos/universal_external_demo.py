#!/usr/bin/env python3
"""
Demonstration of Universal External Job Redirect Handling
Shows how the enhanced handler works with ANY job site, not just azubi.de
"""

import re
from urllib.parse import urlparse, parse_qs

def demo_universal_detection():
    """Show how the handler detects various external redirect patterns"""
    
    # Test cases for different external redirect patterns
    test_cases = [
        {
            'name': 'azubi.de (your example)',
            'html': '''<div class="externe-Beschreibung">
                <a id="detail-beschreibung-externe-url-btn" href="https://www.azubi.de/job/123">Externe Seite öffnen</a>
            </div>''',
            'expected_domain': 'azubi.de'
        },
        {
            'name': 'stepstone.de redirect',
            'html': '''<div class="job-redirect">
                <a class="redirect-btn" target="_blank" href="https://www.stepstone.de/stellenangebote/456">Jetzt bewerben</a>
            </div>''',
            'expected_domain': 'stepstone.de'
        },
        {
            'name': 'indeed.com redirect',
            'html': '''<div class="external-job">
                <a target="_blank" rel="noopener" href="https://de.indeed.com/viewjob?jk=789">Apply Now</a>
            </div>''',
            'expected_domain': 'indeed.com'
        },
        {
            'name': 'xing.com redirect',
            'html': '''<div class="partner-redirect">
                <a class="apply-now" target="_blank" href="https://www.xing.com/jobs/berlin-senior-developer-012">Zur Stellenanzeige</a>
            </div>''',
            'expected_domain': 'xing.com'
        },
        {
            'name': 'Unknown job site redirect',
            'html': '''<div class="external-link-container">
                <a target="_blank" href="https://www.unknown-jobsite.de/jobs/345">Job ansehen</a>
            </div>''',
            'expected_domain': 'unknown-jobsite.de'
        }
    ]
    
    print("=== UNIVERSAL EXTERNAL REDIRECT DETECTION ===")
    print()
    
    # Enhanced detection selectors from the updated handler
    external_containers = [
        '.externe-Beschreibung', '.external-description', '[class*="extern"]', 
        '.partner-redirect', '.job-redirect', '.external-link-container',
        '[class*="redirect"]', '.job-external', '.third-party'
    ]
    
    external_buttons = [
        '#detail-beschreibung-externe-url-btn', 'a[href*="externe"]',
        'a[target="_blank"][href*="job"]', '.redirect-btn', 
        'a[rel*="noopener"][target="_blank"]', 'a[class*="external"]',
        '.apply-now[target="_blank"]', 'a[href*="stepstone"]',
        'a[href*="indeed"]', 'a[href*="xing"]'
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"{i}. Testing: {test_case['name']}")
        html = test_case['html']
        
        # Check container detection
        container_found = False
        for selector in external_containers:
            selector_clean = selector.replace('.', '').replace('[class*="', '').replace('"]', '').replace('[id*="', '').replace('#', '')
            if selector_clean in html:
                print(f"   [OK] Container detected: {selector}")
                container_found = True
                break
        
        if not container_found:
            print("   [ERROR] No container detected")
            continue
        
        # Extract external URL
        url_pattern = r'href="(https://[^"]+)"'
        match = re.search(url_pattern, html)
        
        if match:
            external_url = match.group(1)
            domain = urlparse(external_url).netloc.lower()
            print(f"   [OK] External URL: {external_url}")
            print(f"   [OK] Domain: {domain}")
            
            if test_case['expected_domain'] in domain:
                print(f"   [OK] Correctly identified: {test_case['expected_domain']}")
            else:
                print(f"   [WARNING] Expected {test_case['expected_domain']}, got {domain}")
        else:
            print("   [ERROR] No external URL found")
        
        print()
    
    return True

def demo_universal_selectors():
    """Show the enhanced selectors that work across all job sites"""
    
    print("=== UNIVERSAL JOB SCRAPING SELECTORS ===")
    print()
    
    selectors = {
        'Job Title': [
            'h1', 'h2', '.job-title', '.position-title', '.title', '.jobtitle',
            '[class*="title"]', '.job-name', '.position-name', '.vacancy-title',
            '.stellenbezeichnung', '.jobangebot-title', '.position'
        ],
        'Company Name': [
            '.company', '.employer', '.company-name', '.firmname', '.arbeitgeber',
            '[class*="company"]', '.firma', '.unternehmen', '.betrieb',
            '.job-company', '.vacancy-company'
        ],
        'Location': [
            '.location', '.address', '.ort', '.standort', '.arbeitsort',
            '[class*="location"]', '.job-location', '.vacancy-location',
            '.place', '.city', '.region', '.area'
        ],
        'Job Description': [
            '.description', '.content', '.job-description', '.stellenbeschreibung',
            '[class*="description"]', '.job-content', '.vacancy-description',
            '.details', '.aufgaben', '.job-details', '.text-content'
        ],
        'Contact Email': [
            'a[href^="mailto:"]', '[class*="email"]', '[class*="mail"]',
            '.kontakt-email', '.contact-email'
        ],
        'Contact Phone': [
            'a[href^="tel:"]', '[class*="phone"]', '[class*="telefon"]',
            '.kontakt-phone', '.contact-phone'
        ],
        'Salary': [
            '[class*="salary"]', '[class*="gehalt"]', '[class*="vergütung"]',
            '.salary', '.wage', '.compensation', '.bezahlung'
        ],
        'Start Date': [
            '[class*="start"]', '[class*="beginn"]', '.start-date',
            '.employment-start', '.antritt'
        ]
    }
    
    for field, selector_list in selectors.items():
        print(f"{field}:")
        for selector in selector_list[:5]:  # Show first 5 for brevity
            print(f"  - {selector}")
        if len(selector_list) > 5:
            print(f"  ... and {len(selector_list) - 5} more selectors")
        print()
    
    print("These selectors work across:")
    print("- German job sites (stellenanzeigen.de, jobs.de, etc.)")
    print("- International sites (Indeed, StepStone, Monster)")
    print("- Specialized platforms (XING, azubi.de, academics.de)")
    print("- Unknown/new job sites (generic patterns)")

def demo_supported_sites():
    """Show all supported job partner sites"""
    
    print("=== SUPPORTED PARTNER SITES ===")
    print()
    
    known_sites = {
        'azubi.de': 'Funke Works GmbH - Apprenticeships',
        'stepstone.de': 'StepStone Deutschland GmbH - General jobs',
        'indeed.com': 'Indeed - General jobs',
        'xing.de': 'XING AG - Professional network',
        'monster.de': 'Monster Worldwide Deutschland GmbH - General jobs',
        'jobware.de': 'Jobware Online-Service GmbH - General',
        'stellenanzeigen.de': 'Stellenanzeigen.de GmbH - General',
        'jobs.de': 'Jobs.de GmbH - General',
        'karriere.at': 'Karriere.at - General',
        'jobscout24.de': 'JobScout24 - General',
        'meinestadt.de': 'meinestadt.de GmbH - Local jobs',
        'stellenwerk.de': 'Stellenwerk GmbH - Student jobs',
        'academics.de': 'academics.de - Academic positions',
        'get-in-it.de': 'get-in-it.de - IT jobs'
    }
    
    for domain, description in known_sites.items():
        print(f"[OK] {domain:<20} {description}")
    
    print()
    print("Plus GENERIC SUPPORT for any unknown job site!")
    print("- Uses universal CSS selectors")
    print("- Regex-based contact extraction")
    print("- Adaptive content parsing")

def demo_text_indicators():
    """Show text patterns that trigger external redirect detection"""
    
    print("=== TEXT INDICATORS FOR EXTERNAL REDIRECTS ===")
    print()
    
    indicators = [
        'vollständige stellenbeschreibung',
        'externe seite',
        'kooperationspartner',
        'partner site',
        'jetzt bewerben',
        'zur stellenanzeige',
        'originalanzeige',
        'weiter zur',
        'direkt bewerben',
        'apply now',
        'zur bewerbung',
        'job ansehen',
        'stelle ansehen',
        'original job',
        'complete job description',
        'full description',
        'more details',
        'weitere informationen',
        'detailseite',
        'auf partnerseite'
    ]
    
    print("If any of these phrases are found, the scraper will look for external links:")
    for indicator in indicators:
        print(f"  - '{indicator}'")
    
    print()
    print("This catches redirects even when specific CSS selectors aren't present!")

if __name__ == "__main__":
    demo_universal_detection()
    print()
    demo_universal_selectors()
    print()
    demo_supported_sites()
    print()
    demo_text_indicators()
    
    print("\n" + "="*60)
    print("SUMMARY: UNIVERSAL EXTERNAL JOB HANDLING")
    print("="*60)
    print()
    print("Your enhanced external link handler now supports:")
    print()
    print("1. DETECTION:")
    print("   - 15+ container patterns")
    print("   - 20+ button/link patterns") 
    print("   - 20+ text indicators")
    print("   - Works with ANY job site")
    print()
    print("2. PARTNER SITES:")
    print("   - 14+ known German job sites")
    print("   - Specialized selectors for each")
    print("   - Generic fallback for unknown sites")
    print()
    print("3. DATA EXTRACTION:")
    print("   - 50+ universal CSS selectors")
    print("   - Multi-language support (German/English)")
    print("   - Contact info extraction (email/phone/person)")
    print("   - Salary, start date, location parsing")
    print()
    print("4. ROBUST HANDLING:")
    print("   - Fallback mechanisms")
    print("   - Error tolerance")
    print("   - Regex-based extraction")
    print("   - UTF-8 character support")
    print()
    print("[OK] Ready to handle external redirects from ANY job aggregator!")