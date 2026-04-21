# 2Captcha Integration Setup Guide

## Installation

```bash
# Install 2captcha-python library
pip install 2captcha-python
```

## Configuration

API key is loaded from environment variable `TWOCAPTCHA_API_KEY` in `src/config/settings.py`:
```python
TWOCAPTCHA_API_KEY = os.getenv("TWOCAPTCHA_API_KEY")
```

## Strategy Flow

The CaptchaSolver uses a 2-tier approach:

### 1. 2Captcha API (First Choice)  
- **Human solvers**: High accuracy
- **Cost**: ~$1-3 per 1000 CAPTCHAs
- **Timeout**: 2 minutes max
- **Error reporting**: Wrong solutions reported back

### 2. Manual Fallback (Last Resort)
- **User intervention**: Browser pause for manual solving
- **Timeout**: 300s (5 min) — job is skipped if not solved in time
- **Smart detection**: Automatic detection when completed

## Usage Examples

### Basic Usage (Automatic)
```python
# The job_scraper.py automatically uses the new strategy
python scripts/run_job_scraper.py
```

### Configuration Options
```python
# In src/config/settings.py
CAPTCHA_SETTINGS = {
    'solving_strategies': ['2captcha', 'manual'],  # Priority order
    'twocaptcha_attempts': 15,
    'manual_skip_timeout': 300,  # Skip job after 5 min
}
```

### Strategy Customization
```python
# Only use 2Captcha
'solving_strategies': ['2captcha']

# Manual only (disable automation)
'solving_strategies': ['manual']
```

## Expected Behavior

### Success Flow:
```
=== Trying strategy: 2CAPTCHA ===
Solving CAPTCHA with 2Captcha API...
2Captcha solution received: 'XYZ789'
Submitting CAPTCHA solution: 'XYZ789'
SUCCESS: CAPTCHA solved with 2CAPTCHA!
```

### Manual Fallback:
```
=== Trying strategy: 2CAPTCHA ===
2Captcha timeout error: Timeout
FAILED: 2CAPTCHA strategy failed

=== Trying strategy: MANUAL ===
=== MANUAL CAPTCHA SOLVING ===
Please solve the CAPTCHA manually in the browser within 300s
Waiting for manual CAPTCHA solve... 240s remaining
Manual CAPTCHA timeout after 300s — skipping this job
```

## Cost Estimation

### 2Captcha Pricing:
- **Normal Image CAPTCHA**: ~$1-3 per 1000 solves
- **Your balance**: Check at runtime via API

### Expected Usage:
- **Estimated cost**: $5-15 for 9,000 jobs

## Testing

### Test Individual Strategies:
```python
# Test 2Captcha balance
from twocaptcha import TwoCaptcha
solver = TwoCaptcha(os.getenv("TWOCAPTCHA_API_KEY"))
print(f"Balance: ${solver.balance()}")
```

### Full Pipeline Test:
```bash
# Run with limited jobs to test
python scripts/run_job_scraper.py
# Choose small number when prompted
```

## Troubleshooting

### Common Issues:

1. **2Captcha API Error**:
   - Check API key validity
   - Verify account balance
   - Check network connectivity

2. **Manual Timeout**:
   - Increase `manual_skip_timeout` in settings
   - Job is skipped and logged when timeout expires

3. **Both Strategies Fail**:
   - Job is skipped with detailed log entry
   - Check logs for error details
   - Script auto-detects completion

### Debug Mode:
```python
# Enable detailed logging
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Integration Complete!

The enhanced CaptchaSolver now provides:
✅ **Fallback reliability** - Multiple solving methods  
✅ **Cost effective** - 2Captcha API with manual fallback  
✅ **High success rate** - Human solvers with timeout/skip  
✅ **User control** - Manual override always available