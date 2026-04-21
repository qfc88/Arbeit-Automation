"""
Debug script to test contact extraction logic specifically
"""
import asyncio
import sys
from pathlib import Path

# Add paths
project_root = Path(__file__).parent
sys.path.append(str(project_root / "src"))
sys.path.append(str(project_root / "src" / "config"))

from playwright.async_api import async_playwright
from settings import SCRAPER_SETTINGS, BROWSER_SETTINGS

async def test_contact_extraction():
    """Test contact extraction on specific URLs that show different behaviors"""
    
    # Test URLs from your example
    test_urls = [
        "https://www.arbeitsagentur.de/jobsuche/jobdetail/10000-1203463975-S",  # Anlagenbau - missing contact
        "https://www.arbeitsagentur.de/jobsuche/jobdetail/10001-1001684902-S"   # METZ CONNECT - has contact
    ]
    
    selectors = {
        'contact_phone': '#detail-bewerbung-telefon-Telefon',
        'contact_email': '#detail-bewerbung-mail',
        'contact_address': '#detail-bewerbung-adresse',
        'captcha_container': '#jobdetails-kontaktdaten-block',
        'captcha_image': '#kontaktdaten-captcha-image',
        'captcha_input': '#kontaktdaten-captcha-input',
        'captcha_submit': '#kontaktdaten-captcha-absenden-button',
    }
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=SCRAPER_SETTINGS['headless'],
            args=BROWSER_SETTINGS['args']
        )
        
        context = await browser.new_context(
            user_agent=BROWSER_SETTINGS['user_agent'],
            viewport=BROWSER_SETTINGS['viewport']
        )
        
        for i, url in enumerate(test_urls):
            print(f"\n=== Testing URL {i+1}: {url} ===")
            
            page = await context.new_page()
            
            try:
                # Navigate to page
                await page.goto(url, wait_until="load", timeout=30000)
                await asyncio.sleep(2)
                
                # Check for CAPTCHA
                captcha_exists = await page.locator(selectors['captcha_container']).count() > 0
                print(f"CAPTCHA present: {captcha_exists}")
                
                if captcha_exists:
                    captcha_image = await page.locator(selectors['captcha_image']).count() > 0
                    captcha_input = await page.locator(selectors['captcha_input']).count() > 0
                    print(f"CAPTCHA image: {captcha_image}, CAPTCHA input: {captcha_input}")
                
                # Check contact elements BEFORE CAPTCHA
                phone_before = await page.locator(selectors['contact_phone']).count() > 0
                email_before = await page.locator(selectors['contact_email']).count() > 0
                print(f"Contact elements before CAPTCHA - Phone: {phone_before}, Email: {email_before}")
                
                # If CAPTCHA exists, try to solve it manually (just wait for user)
                if captcha_exists:
                    print("CAPTCHA detected. Manual solving required...")
                    print("Please solve the CAPTCHA manually and press Enter to continue...")
                    if not SCRAPER_SETTINGS['headless']:
                        input("Press Enter after solving CAPTCHA...")
                    else:
                        print("Skipping CAPTCHA in headless mode")
                        continue
                
                # Check contact elements AFTER CAPTCHA
                await asyncio.sleep(2)
                phone_after = await page.locator(selectors['contact_phone']).count() > 0
                email_after = await page.locator(selectors['contact_email']).count() > 0
                print(f"Contact elements after CAPTCHA - Phone: {phone_after}, Email: {email_after}")
                
                # Try to extract actual contact info
                if phone_after:
                    phone_element = await page.query_selector(selectors['contact_phone'])
                    if phone_element:
                        phone_href = await phone_element.get_attribute('href')
                        phone_text = await phone_element.text_content()
                        print(f"Phone href: {phone_href}")
                        print(f"Phone text: {phone_text}")
                        
                        if phone_href and phone_href.startswith('tel:'):
                            phone = phone_href.replace('tel:', '').replace('&nbsp;', ' ')
                            print(f"Extracted phone: '{phone}' (length: {len(phone)})")
                        else:
                            phone = phone_text.strip() if phone_text else None
                            print(f"Fallback phone: '{phone}'")
                
                if email_after:
                    email_element = await page.query_selector(selectors['contact_email'])
                    if email_element:
                        email_href = await email_element.get_attribute('href')
                        email_text = await email_element.text_content()
                        print(f"Email href: {email_href}")
                        print(f"Email text: {email_text}")
                        
                        if email_href and email_href.startswith('mailto:'):
                            email = email_href.replace('mailto:', '')
                            print(f"Extracted email: '{email}'")
                        else:
                            email = email_text.strip() if email_text and '@' in email_text else None
                            print(f"Fallback email: '{email}'")
                
                # Check page HTML around contact area
                try:
                    contact_html = await page.locator('#detail-bewerbung-adresse').innerHTML()
                    print(f"Contact area HTML: {contact_html[:200]}...")
                except:
                    print("Could not get contact area HTML")
                
            except Exception as e:
                print(f"Error testing {url}: {e}")
            finally:
                await page.close()
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_contact_extraction())