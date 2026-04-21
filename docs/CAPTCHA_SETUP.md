# 2Captcha Integration Setup Guide

## Installation

```bash
# Install 2captcha-python library
pip install 2captcha-python

# Optional: Install TrOCR dependencies (if not already installed)
pip install transformers torch torchvision
```

## Configuration

Your API key is already configured in `src/config/settings.py`:
```python
TWOCAPTCHA_API_KEY = "5865b4e02e5bc91f671a60bc18fd75d1"
```

## Strategy Flow

The CaptchaSolver now uses a 3-tier approach:

### 1. TrOCR Strategy (First Choice)
- **Local AI model**: Fast, free, offline
- **Attempts**: 5 tries with CAPTCHA reload
- **Confidence threshold**: 0.7

### 2. 2Captcha API (Second Choice)  
- **Human solvers**: High accuracy
- **Cost**: ~$1-3 per 1000 CAPTCHAs
- **Timeout**: 2 minutes max
- **Error reporting**: Wrong solutions reported back

### 3. Manual Fallback (Last Resort)
- **User intervention**: Browser pause for manual solving
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
    'solving_strategies': ['trocr', '2captcha', 'manual'],  # Order matters
    'max_attempts': 5,                                     # TrOCR attempts
    'confidence_threshold': 0.7,                           # TrOCR confidence
}
```

### Strategy Customization
```python
# Only use 2Captcha (skip TrOCR)
'solving_strategies': ['2captcha', 'manual']

# Only use TrOCR (skip 2Captcha)
'solving_strategies': ['trocr', 'manual']

# Manual only (disable automation)
'solving_strategies': ['manual']
```

## Expected Behavior

### Success Flow:
```
=== Trying strategy: TROCR ===
TrOCR attempt 1/5
TrOCR solution: 'ABC123' (confidence: 0.85)
Submitting CAPTCHA solution: 'ABC123'
SUCCESS: CAPTCHA solved with TROCR!
```

### Fallback Flow:
```
=== Trying strategy: TROCR ===
All TrOCR attempts failed
FAILED: TROCR strategy failed

=== Trying strategy: 2CAPTCHA ===
Solving CAPTCHA with 2Captcha API...
Submitting CAPTCHA to 2Captcha API...
2Captcha solution received: 'XYZ789'
Submitting CAPTCHA solution: 'XYZ789'
SUCCESS: CAPTCHA solved with 2CAPTCHA!
```

### Manual Fallback:
```
=== Trying strategy: 2CAPTCHA ===
2Captcha timeout error: Timeout
FAILED: 2CAPTCHA strategy failed

All automated strategies failed
Auto-solve failed, falling back to manual solving...
=== MANUAL CAPTCHA SOLVING ===
Please solve the CAPTCHA manually in the browser
```

## Cost Estimation

### 2Captcha Pricing:
- **Normal Image CAPTCHA**: ~$1-3 per 1000 solves
- **Your balance**: Check at runtime via API

### Expected Usage:
- **TrOCR success rate**: ~60-80% (free)
- **2Captcha usage**: Only for remaining 20-40%
- **Estimated cost**: $5-15 for 9,000 jobs (if TrOCR fails on all)

## Testing

### Test Individual Strategies:
```python
# Test 2Captcha balance
from twocaptcha import TwoCaptcha
solver = TwoCaptcha("5865b4e02e5bc91f671a60bc18fd75d1")
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

2. **TrOCR Not Loading**:
   - Install: `pip install transformers torch`
   - Check GPU/CPU availability
   - Verify model download

3. **Both Strategies Fail**:
   - Falls back to manual solving
   - User solves in browser
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
✅ **Cost optimization** - Free TrOCR first, paid API second  
✅ **High success rate** - Human solvers when AI fails  
✅ **User control** - Manual override always available