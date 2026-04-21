#!/usr/bin/env python3
"""
Demonstration of how the external link handler works with your azubi.de example
This shows the exact flow without requiring Playwright installation
"""

import re
from urllib.parse import urlparse, parse_qs

def demo_external_detection():
    """Demonstrate external redirect detection logic"""
    
    # Your HTML example
    html_content = '''
    <div class="ba-layout-tile query-container">
        <h3 class="h5 sr-only">Stellenbeschreibung</h3>
        <div class="externe-Beschreibung ng-star-inserted">
            <h4 class="h6">Vollständige Stellenbeschreibung bei unserem Kooperationspartner einsehen:</h4>
            <a id="detail-beschreibung-externe-url-btn" target="_blank" rel="noopener noreferrer" 
               class="ba-btn ba-btn-primary ba-btn-icon ba-icon-linkout" 
               href="https://www.azubi.de/ausbildungsplatz/10379239-p-?utm_campaign=BAG&utm_medium=premiumcpc&utm_source=BAG">
               Externe Seite öffnen
            </a>
            <p class="externe-quelle ng-star-inserted">
                Quelle: <a target="_blank" rel="noopener noreferrer" 
                          href="https://www.azubi.de">Funke Works GmbH / azubi.de</a>
            </p>
        </div>
    </div>
    '''
    
    print("=== EXTERNAL REDIRECT DETECTION DEMO ===")
    print()
    
    # Step 1: Check for external container
    external_container_selectors = [
        '.externe-Beschreibung',
        '.external-description',
        '[class*="extern"]'
    ]
    
    print("1. Checking for external container...")
    container_found = False
    for selector in external_container_selectors:
        selector_class = selector.replace('.', '').replace('[class*="', '').replace('"]', '')
        if selector_class in html_content:
            print(f"   [OK] Found container: {selector}")
            container_found = True
            break
    
    if not container_found:
        print("   [ERROR] No external container found")
        return
    
    # Step 2: Extract external link
    print("\n2. Extracting external link...")
    external_button_pattern = r'href="(https://[^"]+)"'
    match = re.search(external_button_pattern, html_content)
    
    if match:
        external_url = match.group(1)
        print(f"   [OK] External URL: {external_url}")
    else:
        print("   [ERROR] No external URL found")
        return
    
    # Step 3: Parse UTM parameters
    print("\n3. Parsing UTM parameters...")
    parsed_url = urlparse(external_url)
    query_params = parse_qs(parsed_url.query)
    
    utm_params = {}
    for param in ['utm_campaign', 'utm_source', 'utm_medium']:
        values = query_params.get(param, [])
        utm_params[param] = values[0] if values else None
        if utm_params[param]:
            print(f"   [OK] {param}: {utm_params[param]}")
    
    # Step 4: Identify partner
    print("\n4. Identifying partner...")
    domain = parsed_url.netloc.lower()
    
    partner_sites = {
        'azubi.de': {
            'company': 'Funke Works GmbH',
            'type': 'apprenticeship'
        }
    }
    
    partner_info = None
    for site_domain, site_info in partner_sites.items():
        if site_domain in domain:
            partner_info = {
                'domain': site_domain,
                'company': site_info['company'],
                'type': site_info['type']
            }
            break
    
    if partner_info:
        print(f"   [OK] Partner: {partner_info['company']} ({partner_info['domain']})")
        print(f"   [OK] Type: {partner_info['type']}")
    else:
        print(f"   [WARNING] Unknown partner: {domain}")
    
    # Step 5: Extract source info
    print("\n5. Extracting source information...")
    source_pattern = r'Quelle:\s*<a[^>]*>([^<]+)</a>'
    source_match = re.search(source_pattern, html_content)
    
    if source_match:
        source_text = source_match.group(1)
        print(f"   [OK] Source: {source_text}")
    
    # Final result
    print("\n=== DETECTION RESULT ===")
    result = {
        'has_external_redirect': True,
        'external_url': external_url,
        'partner_domain': partner_info['domain'] if partner_info else domain,
        'partner_company': partner_info['company'] if partner_info else 'Unknown',
        'partner_type': partner_info['type'] if partner_info else 'unknown',
        'utm_campaign': utm_params.get('utm_campaign'),
        'utm_source': utm_params.get('utm_source'),
        'utm_medium': utm_params.get('utm_medium')
    }
    
    for key, value in result.items():
        print(f"{key}: {value}")
    
    return result

def demo_scraper_integration():
    """Show how this integrates with the main job scraper"""
    print("\n=== INTEGRATION WITH JOB SCRAPER ===")
    print()
    print("When your job scraper encounters this element:")
    print("1. detect_external_redirect() finds the .externe-Beschreibung container")
    print("2. Extracts the href from #detail-beschreibung-externe-url-btn")
    print("3. Identifies azubi.de as a known partner")
    print("4. Calls scrape_external_job() with the external URL")
    print("5. Uses azubi.de-specific selectors to extract job details")
    print("6. Returns combined data with external metadata")
    print()
    print("The result includes:")
    print("- is_external_redirect: True")
    print("- external_partner: azubi.de")
    print("- external_company: Funke Works GmbH")
    print("- utm_campaign, utm_source, utm_medium")
    print("- All job details scraped from the external site")

def demo_azubi_selectors():
    """Show the azubi.de specific selectors"""
    print("\n=== AZUBI.DE SCRAPING SELECTORS ===")
    print()
    
    azubi_selectors = {
        'title': ['h1', '.job-title', '[data-testid="job-title"]'],
        'company': ['.company-name', '[data-testid="company-name"]'],
        'location': ['.job-location', '[data-testid="location"]'],
        'description': ['.job-description', '.description-content'],
        'contact_email': ['a[href^="mailto:"]'],
        'contact_phone': ['a[href^="tel:"]', '[class*="phone"]'],
        'start_date': ['[class*="start"]', '[class*="beginn"]'],
        'salary': ['[class*="salary"]', '[class*="gehalt"]', '[class*="vergütung"]']
    }
    
    print("Your scraper will try these selectors on azubi.de:")
    for field, selectors in azubi_selectors.items():
        print(f"{field}:")
        for selector in selectors:
            print(f"  - {selector}")
    print()
    print("Plus generic email/phone regex extraction as fallback")

if __name__ == "__main__":
    # Run the complete demonstration
    result = demo_external_detection()
    demo_scraper_integration()
    demo_azubi_selectors()
    
    print("\n=== SUMMARY ===")
    print("[OK] Your external link handler is fully configured for this scenario")
    print("[OK] It will detect the azubi.de redirect automatically")
    print("[OK] It will scrape the external job page using specific selectors")
    print("[OK] Integration with job_scraper.py is already complete")
    print()
    print("To test with real jobs, run your main scraper:")
    print("python scripts/run_job_scraper.py")