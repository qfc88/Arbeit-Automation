#!/usr/bin/env python3
"""
Configuration example for post-CAPTCHA page stabilization
Shows how to configure the new page stabilization features
"""

# Enhanced SCRAPER_SETTINGS with post-CAPTCHA stabilization options
SCRAPER_SETTINGS = {
    # Existing settings
    'headless': False,
    'timeout': 30000,
    'batch_size': 10,
    'delay_between_jobs': 1,
    'max_jobs_per_session': 1000,
    'enable_resume': True,
    
    # NEW: Post-CAPTCHA page stabilization settings
    'enable_page_stabilization': True,    # Enable/disable stabilization
    'stabilization_timeout': 30,          # Timeout in seconds for stabilization operations
    'prefer_new_tab': False,              # Whether to prefer new tab over page refresh
}

# Configuration profiles for different scenarios
PROFILES = {
    'default': {
        'enable_page_stabilization': True,
        'stabilization_timeout': 30,
        'prefer_new_tab': False,  # Try refresh first, then new tab
    },
    
    'aggressive_refresh': {
        'enable_page_stabilization': True,
        'stabilization_timeout': 45,
        'prefer_new_tab': True,   # Always try new tab first
    },
    
    'conservative': {
        'enable_page_stabilization': True,
        'stabilization_timeout': 20,
        'prefer_new_tab': False,  # Only use refresh, no new tabs
    },
    
    'disabled': {
        'enable_page_stabilization': False,  # Disable stabilization completely
    }
}

def get_settings_for_profile(profile_name: str = 'default') -> dict:
    """Get scraper settings for a specific profile"""
    base_settings = SCRAPER_SETTINGS.copy()
    
    if profile_name in PROFILES:
        base_settings.update(PROFILES[profile_name])
    
    return base_settings

def demo_stabilization_usage():
    """Show how to use the stabilization settings"""
    print("=== POST-CAPTCHA PAGE STABILIZATION CONFIGURATION ===")
    print()
    
    print("Available profiles:")
    for profile, settings in PROFILES.items():
        print(f"  {profile}:")
        for key, value in settings.items():
            print(f"    {key}: {value}")
        print()
    
    print("Usage examples:")
    print()
    
    print("1. Default behavior (refresh first, then new tab):")
    print("   scraper = JobScraper()")
    print("   # Uses SCRAPER_SETTINGS with enable_page_stabilization=True")
    print()
    
    print("2. Aggressive new tab approach:")
    print("   SCRAPER_SETTINGS.update(PROFILES['aggressive_refresh'])")
    print("   scraper = JobScraper()")
    print()
    
    print("3. Conservative refresh only:")
    print("   SCRAPER_SETTINGS.update(PROFILES['conservative'])")
    print("   scraper = JobScraper()")
    print()
    
    print("4. Disable stabilization completely:")
    print("   SCRAPER_SETTINGS.update(PROFILES['disabled'])")
    print("   scraper = JobScraper()")
    print()
    
    print("=== HOW IT WORKS ===")
    print()
    print("After CAPTCHA is solved:")
    print("1. Page may have rendering issues or become unresponsive")
    print("2. Stabilization detects this and tries to fix it")
    print("3. Two strategies available:")
    print("   a) Page refresh: Reload current page")
    print("   b) New tab: Create fresh page and close old one")
    print("4. Verification ensures page is working before continuing")
    print("5. If stabilization fails, continues with basic data")
    print()
    
    print("Benefits:")
    print("- Fixes rendering issues after CAPTCHA")
    print("- Handles unresponsive pages") 
    print("- Reduces 1-2 minute delays")
    print("- Improves scraping reliability")
    print("- Configurable timeout and strategy")

if __name__ == "__main__":
    demo_stabilization_usage()
    
    print("\n" + "="*60)
    print("CONFIGURATION RECOMMENDATION")
    print("="*60)
    print()
    print("For your use case (rendering issues after CAPTCHA):")
    print("1. Start with 'default' profile")
    print("2. If you still see issues, try 'aggressive_refresh'")
    print("3. Monitor logs to see which strategy works best")
    print("4. Adjust stabilization_timeout if needed (20-45 seconds)")
    print()
    print("The new stabilization will automatically:")
    print("- Detect when page has issues after CAPTCHA")
    print("- Try refresh or new tab approach")
    print("- Continue scraping once page is stable")
    print("- Handle any errors gracefully")