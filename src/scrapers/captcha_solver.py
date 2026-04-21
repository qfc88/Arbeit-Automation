"""
Advanced CAPTCHA solver with multiple strategies:
1. TrOCR (anuashok/ocr-captcha-v3) - Local AI model
2. 2Captcha API - Human solving service  
3. Manual fallback - User intervention
"""

import cv2
import numpy as np
from PIL import Image
import logging
from typing import Optional, Tuple, Dict
import io
import asyncio
import time
from playwright.async_api import Page
import torch
import re
import sys
from pathlib import Path

# Add config path
sys.path.append(str(Path(__file__).parent.parent / "config"))

# TrOCR imports (optional)
try:
    from transformers import VisionEncoderDecoderModel, TrOCRProcessor
    TROCR_AVAILABLE = True
except ImportError:
    TROCR_AVAILABLE = False
    logging.warning("TrOCR not available. Install transformers and torch for local OCR.")

# Initialize logger after path setup
sys.path.append(str(Path(__file__).parent.parent / "utils"))
try:
    from logger import get_scraper_logger
    logger = get_scraper_logger('scrapers.captcha_solver')
except ImportError:
    logger = logging.getLogger(__name__)

# Manual 2Captcha implementation using requests
try:
    import requests
    REQUESTS_AVAILABLE = True
    TWOCAPTCHA_AVAILABLE = True  # We'll use manual implementation
    logging.info("Using manual 2Captcha API implementation")
except ImportError:
    REQUESTS_AVAILABLE = False
    TWOCAPTCHA_AVAILABLE = False
    logging.warning("Requests not available. Install requests for 2Captcha API.")

# Import settings - no fallback, fail fast if not configured
try:
    from settings import TWOCAPTCHA_API_KEY, CAPTCHA_SETTINGS
except ImportError:
    try:
        from config.settings import TWOCAPTCHA_API_KEY, CAPTCHA_SETTINGS
    except ImportError as e:
        raise ImportError(
            f"[ERROR] Settings import failed: {e}\n"
            "Please ensure src/config/settings.py exists and contains required settings."
        )

# Setup logging
logger = logging.getLogger(__name__)

class Manual2CaptchaClient:
    """Manual 2Captcha API client using requests"""
    
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = 'https://2captcha.com'
        self.timeout = 120  # 2 minutes max
        self.poll_interval = 5  # Check every 5 seconds
    
    def balance(self):
        """Get account balance"""
        try:
            response = requests.get(f'{self.base_url}/res.php', 
                                  params={'key': self.api_key, 'action': 'getbalance'})
            
            if response.text.startswith('ERROR'):
                raise Exception(f"Balance check failed: {response.text}")
            
            return float(response.text)
        except Exception as e:
            raise Exception(f"Failed to get balance: {e}")
    
    def normal(self, image_path_or_bytes, **kwargs):
        """Solve normal image captcha"""
        try:
            # Submit captcha
            captcha_id = self._submit_captcha(image_path_or_bytes, **kwargs)
            
            # Poll for result
            result = self._get_result(captcha_id)
            
            return result
        except Exception as e:
            raise Exception(f"2Captcha solving failed: {e}")
    
    def _submit_captcha(self, image_data, **kwargs):
        """Submit captcha image to 2Captcha"""
        try:
            # Prepare form data
            data = {
                'key': self.api_key,
                'method': 'post',
                'numeric': kwargs.get('numeric', 0),
                'min_len': kwargs.get('min_len', 0),
                'max_len': kwargs.get('max_len', 0),
                'phrase': kwargs.get('phrase', 0),
                'regsense': kwargs.get('case_sensitive', 0),
                'language': kwargs.get('lang', ''),
                'json': 1  # Get JSON response
            }
            
            # Handle image data
            if isinstance(image_data, str):
                # File path
                with open(image_data, 'rb') as f:
                    files = {'file': ('captcha.jpg', f.read(), 'image/jpeg')}
            else:
                # Raw bytes
                files = {'file': ('captcha.jpg', image_data, 'image/jpeg')}
            
            # Submit to 2Captcha
            response = requests.post(f'{self.base_url}/in.php', files=files, data=data)
            
            try:
                result = response.json()
                if result['status'] == 1:
                    logger.info(f"CAPTCHA submitted successfully, ID: {result['request']}")
                    return result['request']
                else:
                    raise Exception(f"Submit failed: {result.get('error_text', 'Unknown error')}")
            except:
                # Fallback to text response
                if 'OK|' in response.text:
                    captcha_id = response.text.split('|')[1]
                    logger.info(f"CAPTCHA submitted successfully, ID: {captcha_id}")
                    return captcha_id
                else:
                    raise Exception(f"Submit failed: {response.text}")
        
        except Exception as e:
            raise Exception(f"Failed to submit CAPTCHA: {e}")
    
    def _get_result(self, captcha_id):
        """Poll for CAPTCHA solution"""
        max_attempts = self.timeout // self.poll_interval
        
        for attempt in range(max_attempts):
            try:
                response = requests.get(f'{self.base_url}/res.php', 
                                      params={
                                          'key': self.api_key,
                                          'action': 'get',
                                          'id': captcha_id,
                                          'json': 1
                                      })
                
                try:
                    result = response.json()
                    if result['status'] == 1:
                        solution = result['request']
                        logger.info(f"CAPTCHA solved: '{solution}'")
                        return solution
                    elif result['status'] == 0 and 'NOT_READY' in result.get('error_text', ''):
                        logger.debug(f"CAPTCHA not ready, attempt {attempt + 1}/{max_attempts}")
                        time.sleep(self.poll_interval)
                        continue
                    else:
                        raise Exception(f"Solve failed: {result.get('error_text', 'Unknown error')}")
                except:
                    # Fallback to text response
                    if 'OK|' in response.text:
                        solution = response.text.split('|')[1]
                        logger.info(f"CAPTCHA solved: '{solution}'")
                        return solution
                    elif response.text == 'CAPCHA_NOT_READY':
                        logger.debug(f"CAPTCHA not ready, attempt {attempt + 1}/{max_attempts}")
                        time.sleep(self.poll_interval)
                        continue
                    else:
                        raise Exception(f"Solve failed: {response.text}")
            
            except Exception as e:
                if attempt == max_attempts - 1:
                    raise Exception(f"Polling failed: {e}")
                logger.debug(f"Polling error (attempt {attempt + 1}): {e}")
                time.sleep(self.poll_interval)
        
        raise Exception(f"Timeout: CAPTCHA not solved within {self.timeout} seconds")
    
    def report(self, captcha_id, correct=True):
        """Report captcha as correct or incorrect"""
        try:
            action = 'reportgood' if correct else 'reportbad'
            response = requests.get(f'{self.base_url}/res.php',
                                  params={
                                      'key': self.api_key,
                                      'action': action,
                                      'id': captcha_id
                                  })
            logger.debug(f"Reported CAPTCHA {captcha_id} as {'correct' if correct else 'incorrect'}")
        except Exception as e:
            logger.debug(f"Failed to report CAPTCHA: {e}")

class CaptchaSolver:
    def __init__(self):
        """Initialize multi-strategy CAPTCHA solver"""
        # Strategy configuration
        self.strategies = CAPTCHA_SETTINGS.get('solving_strategies', ['trocr', '2captcha', 'manual'])
        self.trocr_attempts = CAPTCHA_SETTINGS.get('trocr_attempts', 3)
        self.twocaptcha_attempts = CAPTCHA_SETTINGS.get('twocaptcha_attempts', 3)
        self.manual_timeout = CAPTCHA_SETTINGS.get('manual_timeout', 300)
        self.confidence_threshold = CAPTCHA_SETTINGS.get('confidence_threshold', 0.7)
        self.reload_between_attempts = CAPTCHA_SETTINGS.get('reload_captcha_between_attempts', True)
        self.max_total_attempts = CAPTCHA_SETTINGS.get('max_total_attempts', 10)
        
        # TrOCR configuration
        self.model_name = CAPTCHA_SETTINGS.get('trocr_model', 'anuashok/ocr-captcha-v3')
        self.processor = None
        self.model = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        
        # 2Captcha configuration
        self.twocaptcha_client = None
        
        # Statistics tracking
        self.stats = {
            'total_attempts': 0,
            'trocr_successes': 0,
            'twocaptcha_successes': 0,
            'manual_successes': 0,
            'failures': 0
        }
        
        logger.info(f"CaptchaSolver initializing with strategies: {self.strategies}")
        logger.info(f"Device: {self.device}, TrOCR attempts: {self.trocr_attempts}, 2Captcha attempts: {self.twocaptcha_attempts}")
        logger.info(f"Manual timeout: {self.manual_timeout}s, Reload between attempts: {self.reload_between_attempts}")
        logger.info(f"2Captcha API key configured: {'Yes' if TWOCAPTCHA_API_KEY else 'No'}")
        if TWOCAPTCHA_API_KEY:
            logger.info(f"API key: {TWOCAPTCHA_API_KEY[:8]}...{TWOCAPTCHA_API_KEY[-4:]}")
        
        # Initialize available strategies
        self._init_strategies()
    
    def _init_strategies(self):
        """Initialize available solving strategies"""
        available_strategies = []
        
        # Initialize TrOCR if available
        if 'trocr' in self.strategies and TROCR_AVAILABLE:
            try:
                self._load_trocr_model()
                available_strategies.append('trocr')
                logger.info("TrOCR strategy initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize TrOCR: {e}")
        
        # Initialize 2Captcha if available
        if '2captcha' in self.strategies and TWOCAPTCHA_AVAILABLE and TWOCAPTCHA_API_KEY:
            try:
                self._init_2captcha()
                available_strategies.append('2captcha')
                logger.info("2Captcha strategy initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize 2Captcha: {e}")
        
        # Manual strategy is always available
        if 'manual' in self.strategies:
            available_strategies.append('manual')
        
        # Update strategies to only include available ones
        self.active_strategies = available_strategies
        logger.info(f"Active strategies: {self.active_strategies}")
        
        if not self.active_strategies:
            logger.error("No CAPTCHA solving strategies available!")
    
    def _init_2captcha(self):
        """Initialize 2Captcha client"""
        if not TWOCAPTCHA_API_KEY:
            raise Exception("2Captcha API key not found")
        
        if not REQUESTS_AVAILABLE:
            raise Exception("Requests library not available for 2Captcha API")
        
        logger.info(f"Initializing manual 2Captcha client with API key: {TWOCAPTCHA_API_KEY[:8]}...{TWOCAPTCHA_API_KEY[-4:]}")
        
        # Use our manual implementation
        self.twocaptcha_client = Manual2CaptchaClient(TWOCAPTCHA_API_KEY)
        
        # Test API key by checking balance
        try:
            balance = self.twocaptcha_client.balance()
            logger.info(f"SUCCESS: 2Captcha API key valid! Balance: ${balance}")
        except Exception as e:
            logger.warning(f"2Captcha API key validation failed: {e}")
            raise e
    
    def _load_trocr_model(self):
        """Load the pre-trained anuashok/ocr-captcha-v3 model"""
        try:
            logger.info(f"Loading {self.model_name} model...")
            
            # Load processor and model
            self.processor = TrOCRProcessor.from_pretrained(self.model_name)
            self.model = VisionEncoderDecoderModel.from_pretrained(self.model_name)
            
            # Move model to appropriate device
            self.model.to(self.device)
            self.model.eval()  # Set to evaluation mode
            
            logger.info(f"[SUCCESS] Model {self.model_name} loaded successfully on {self.device}")
            
        except Exception as e:
            logger.error(f"[ERROR] Failed to load model {self.model_name}: {e}")
            logger.info("💡 Fallback: Install requirements with 'pip install transformers torch torchvision'")
            raise e
    
    def preprocess_image_for_trocr(self, image_data: bytes) -> Image.Image:
        """Preprocess CAPTCHA image specifically for TrOCR model"""
        try:
            # Convert bytes to PIL Image
            image = Image.open(io.BytesIO(image_data))
            
            # Convert to RGBA if needed for transparency handling
            if image.mode == 'RGBA':
                # Create white background for transparent images
                background = Image.new("RGBA", image.size, (255, 255, 255, 255))
                image = Image.alpha_composite(background, image)
            
            # Convert to RGB (required by TrOCR)
            image = image.convert("RGB")
            
            # Apply minimal preprocessing to preserve original CAPTCHA characteristics
            # TrOCR model is robust enough to handle distortions
            
            # Optional: Resize if image is too small (TrOCR works better with larger images)
            width, height = image.size
            if width < 150 or height < 50:
                scale_factor = max(150 / width, 50 / height)
                new_width = int(width * scale_factor)
                new_height = int(height * scale_factor)
                image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                logger.debug(f"Resized image from {width}x{height} to {new_width}x{new_height}")
            
            return image
            
        except Exception as e:
            logger.error(f"Error preprocessing image for TrOCR: {e}")
            return None
    
    def extract_text_with_trocr(self, image: Image.Image) -> Tuple[str, float]:
        """Extract text using the fine-tuned TrOCR model"""
        try:
            if not self.model or not self.processor:
                logger.error("Model not loaded properly")
                return "", 0.0
            
            # Prepare image for the model
            pixel_values = self.processor(image, return_tensors="pt").pixel_values
            pixel_values = pixel_values.to(self.device)
            
            # Generate text with model
            with torch.no_grad():
                # Generate with beam search for better accuracy
                generated_ids = self.model.generate(
                    pixel_values,
                    max_length=20,  # Max CAPTCHA length
                    num_beams=4,    # Beam search for better results  
                    early_stopping=True,
                    do_sample=False  # Deterministic output
                )
            
            # Decode the generated text
            generated_text = self.processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
            
            # Calculate confidence (simplified - TrOCR doesn't provide direct confidence scores)
            # We use text length and character validity as confidence proxies
            confidence = self._estimate_confidence(generated_text, image)
            
            logger.info(f"TrOCR extracted: '{generated_text}' (confidence: {confidence:.2f})")
            return generated_text.strip(), confidence
            
        except Exception as e:
            logger.error(f"Error extracting text with TrOCR: {e}")
            return "", 0.0
    
    def _estimate_confidence(self, text: str, image: Image.Image) -> float:
        """Estimate confidence based on text characteristics and image quality"""
        try:
            if not text:
                return 0.0
            
            confidence = 1.0
            
            # Length check (typical CAPTCHA length is 4-8 characters)
            if len(text) < 3 or len(text) > 10:
                confidence *= 0.7
            elif 4 <= len(text) <= 8:
                confidence *= 1.0
            
            # Character validity (alphanumeric only)
            if re.match(r'^[A-Za-z0-9]+$', text):
                confidence *= 1.0
            else:
                confidence *= 0.5
            
            # Case consistency (either all upper, all lower, or mixed)
            if text.isupper() or text.islower():
                confidence *= 1.0
            elif any(c.isupper() for c in text) and any(c.islower() for c in text):
                confidence *= 0.9  # Mixed case is common in CAPTCHAs
            
            # Image quality factor (basic check)
            width, height = image.size
            if width > 100 and height > 30:
                confidence *= 1.0
            else:
                confidence *= 0.8
            
            return min(confidence, 1.0)
            
        except Exception as e:
            logger.debug(f"Error estimating confidence: {e}")
            return 0.5
    
    def clean_extracted_text(self, text: str) -> str:
        """Clean and normalize extracted text for CAPTCHA submission"""
        if not text:
            return ""
        
        # Remove any whitespace
        text = re.sub(r'\s+', '', text)
        
        # Remove any non-alphanumeric characters (common OCR noise)
        text = re.sub(r'[^A-Za-z0-9]', '', text)
        
        # Arbeitsagentur CAPTCHAs are typically mixed case, so preserve original case
        return text
    
    def validate_solution(self, solution: str) -> bool:
        """Validate CAPTCHA solution before submission"""
        if not solution:
            return False
        
        # Basic validation rules for arbeitsagentur.de CAPTCHAs
        if len(solution)!=6:
            return False
        
        # Should contain only alphanumeric characters
        if not re.match(r'^[A-Za-z0-9]+$', solution):
            return False
        
        return True
    
    async def capture_captcha_image(self, page: Page, selector: str) -> Optional[bytes]:
        """Capture CAPTCHA image from webpage"""
        try:
            # Wait for image to load
            await page.wait_for_selector(selector, timeout=10000)
            await asyncio.sleep(1)  # Extra wait for image loading
            
            # Get the CAPTCHA element
            captcha_element = await page.query_selector(selector)
            if not captcha_element:
                logger.error("CAPTCHA element not found")
                return None
            
            # Check if image has loaded properly
            img_src = await captcha_element.get_attribute('src')
            if not img_src or 'data:' in img_src:
                logger.debug("CAPTCHA image still loading...")
                await asyncio.sleep(2)
            
            # Screenshot the CAPTCHA element
            screenshot_bytes = await captcha_element.screenshot()
            
            logger.info("[SUCCESS] CAPTCHA image captured successfully")
            return screenshot_bytes
            
        except Exception as e:
            logger.error(f"[ERROR] Error capturing CAPTCHA image: {e}")
            return None
    
    async def solve_captcha_from_page(self, page: Page, captcha_selector: str, input_selector: str, submit_selector: str) -> bool:
        """Main method to solve CAPTCHA using multiple strategies"""
        try:
            self.stats['total_attempts'] += 1
            logger.info("Starting multi-strategy CAPTCHA solving process...")
            logger.info(f"Available strategies: {self.active_strategies}")
            logger.info(f"Max total attempts allowed: {self.max_total_attempts}")
            
            total_attempts_used = 0
            
            # Try each strategy in order
            for strategy in self.active_strategies:
                if total_attempts_used >= self.max_total_attempts:
                    logger.warning(f"Maximum total attempts ({self.max_total_attempts}) reached")
                    break
                    
                logger.info(f"=== Trying strategy: {strategy.upper()} ===")
                
                if strategy == 'trocr':
                    success = await self._solve_with_trocr(page, captcha_selector, input_selector, submit_selector)
                    total_attempts_used += self.trocr_attempts
                    if success:
                        self.stats['trocr_successes'] += 1
                elif strategy == '2captcha':
                    success = await self._solve_with_2captcha(page, captcha_selector, input_selector, submit_selector)
                    total_attempts_used += self.twocaptcha_attempts
                    if success:
                        self.stats['twocaptcha_successes'] += 1
                elif strategy == 'manual':
                    logger.info("Falling back to manual solving...")
                    return False  # Let job_scraper handle manual solving
                
                if success:
                    logger.info(f"SUCCESS: CAPTCHA solved with {strategy.upper()}!")
                    logger.info(f"Statistics: {self._get_success_rate_summary()}")
                    return True
                else:
                    logger.warning(f"FAILED: {strategy.upper()} strategy failed")
                    # Reload CAPTCHA before trying next strategy
                    if self.reload_between_attempts:
                        logger.info("Reloading CAPTCHA before next strategy...")
                        await self._reload_captcha(page)
                        await asyncio.sleep(2)
            
            logger.error("All automated strategies failed")
            return False
            
        except Exception as e:
            logger.error(f"Error in multi-strategy CAPTCHA solving: {e}")
            return False
    
    async def _solve_with_trocr(self, page: Page, captcha_selector: str, input_selector: str, submit_selector: str) -> bool:
        """Solve CAPTCHA using TrOCR model"""
        if not TROCR_AVAILABLE or not self.model:
            logger.warning("TrOCR not available")
            return False
        
        try:
            logger.info(f"Trying TrOCR with {self.trocr_attempts} attempts...")
            
            for attempt in range(self.trocr_attempts):
                logger.info(f"TrOCR attempt {attempt + 1}/{self.trocr_attempts}")
                
                # Capture CAPTCHA image
                image_data = await self.capture_captcha_image(page, captcha_selector)
                if not image_data:
                    logger.error("Failed to capture CAPTCHA image")
                    continue
                
                # Preprocess image for TrOCR
                processed_image = self.preprocess_image_for_trocr(image_data)
                if processed_image is None:
                    logger.error("Failed to preprocess image")
                    continue
                
                # Extract text using TrOCR model
                extracted_text, confidence = self.extract_text_with_trocr(processed_image)
                
                if not extracted_text:
                    logger.warning("No text extracted, reloading CAPTCHA...")
                    await self._reload_captcha(page)
                    continue
                
                # Clean and validate solution
                solution = self.clean_extracted_text(extracted_text)
                logger.info(f"TrOCR solution: '{solution}' (confidence: {confidence:.2f})")
                
                if not self.validate_solution(solution):
                    logger.warning(f"Invalid solution format: '{solution}'")
                    await self._reload_captcha(page)
                    continue
                
                # Submit solution
                success = await self._submit_solution(page, solution, input_selector, submit_selector, captcha_selector)
                if success:
                    self._log_captcha_attempt(True, "trocr", solution, confidence)
                    return True
                else:
                    self._log_captcha_attempt(False, "trocr", solution, confidence)
                
                # Wait before next attempt
                await asyncio.sleep(2)
            
            logger.warning("All TrOCR attempts failed")
            return False
            
        except Exception as e:
            logger.error(f"Error in TrOCR solving: {e}")
            return False
    
    async def _solve_with_2captcha(self, page: Page, captcha_selector: str, input_selector: str, submit_selector: str) -> bool:
        """Solve CAPTCHA using 2Captcha API"""
        if not TWOCAPTCHA_AVAILABLE or not self.twocaptcha_client:
            logger.warning("2Captcha not available")
            return False
        
        try:
            logger.info(f"Solving CAPTCHA with 2Captcha API ({self.twocaptcha_attempts} attempts)...")
            
            for attempt in range(self.twocaptcha_attempts):
                logger.info(f"2Captcha attempt {attempt + 1}/{self.twocaptcha_attempts}")
                
                # Capture CAPTCHA image
                image_data = await self.capture_captcha_image(page, captcha_selector)
                if not image_data:
                    logger.error(f"Failed to capture CAPTCHA image for 2Captcha (attempt {attempt + 1})")
                    if attempt == self.twocaptcha_attempts - 1:
                        return False
                    continue
                
                # Save image temporarily
                import tempfile
                with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_file:
                    temp_file.write(image_data)
                    temp_image_path = temp_file.name
                
                # Submit to 2Captcha
                logger.info("Submitting CAPTCHA to 2Captcha API...")
                try:
                    result = self.twocaptcha_client.normal(
                        temp_image_path,
                        numeric=0,        # May contain letters and numbers
                        min_len=3,        # Minimum 3 characters
                        max_len=10,       # Maximum 10 characters
                        phrase=0,         # Single word
                        case_sensitive=1, # Case sensitive
                        lang='en'         # English
                    )
                    
                    solution = str(result)
                    logger.info(f"2Captcha solution received: '{solution}'")
                    
                    # Clean up temp file
                    import os
                    os.unlink(temp_image_path)
                    
                    # Validate solution
                    if not self.validate_solution(solution):
                        logger.warning(f"2Captcha returned invalid solution: '{solution}' (attempt {attempt + 1})")
                        if attempt == self.twocaptcha_attempts - 1:
                            return False
                        continue
                    
                    # Submit solution
                    success = await self._submit_solution(page, solution, input_selector, submit_selector, captcha_selector)
                    if success:
                        self._log_captcha_attempt(True, "2captcha", solution, 1.0)
                        return True
                    else:
                        self._log_captcha_attempt(False, "2captcha", solution, 1.0)
                        logger.warning(f"2Captcha solution '{solution}' was incorrect (attempt {attempt + 1})")
                        # Report incorrect solution to 2Captcha
                        try:
                            self.twocaptcha_client.report(result.id, False)
                        except:
                            pass
                        
                        # Try again if not the last attempt
                        if attempt < self.twocaptcha_attempts - 1:
                            logger.info("Reloading CAPTCHA and trying again...")
                            await self._reload_captcha(page, captcha_selector)
                            await asyncio.sleep(2)
                        
                except Exception as e:
                    logger.error(f"2Captcha error on attempt {attempt + 1}: {e}")
                    # Clean up temp file if it exists
                    try:
                        import os
                        os.unlink(temp_image_path)
                    except:
                        pass
                    
                    if attempt == self.twocaptcha_attempts - 1:
                        return False
            
            # If we've exhausted all attempts
            logger.error(f"All {self.twocaptcha_attempts} 2Captcha attempts failed")
            return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"2Captcha network error: {e}")
            return False
        except ValueError as e:
            logger.error(f"2Captcha validation error: {e}")
            return False
        except Exception as e:
            if "timeout" in str(e).lower():
                logger.error(f"2Captcha timeout error: {e}")
            else:
                logger.error(f"2Captcha API error: {e}")
            return False
    
    async def _submit_solution(self, page: Page, solution: str, input_selector: str, submit_selector: str, captcha_selector: str) -> bool:
        """Submit CAPTCHA solution and check if it was correct"""
        try:
            # Clear input field first
            await page.fill(input_selector, "")
            await asyncio.sleep(0.3)
            
            # Fill the solution
            await page.fill(input_selector, solution)
            await asyncio.sleep(0.5)
            
            # Submit the CAPTCHA
            logger.info(f"Submitting CAPTCHA solution: '{solution}'")
            await page.click(submit_selector)
            await asyncio.sleep(3)
            
            # Check if CAPTCHA was solved successfully
            success = await self._check_captcha_success(page, captcha_selector)
            return success
            
        except Exception as e:
            logger.error(f"Error submitting solution: {e}")
            return False
    
    async def _reload_captcha(self, page: Page):
        """Reload CAPTCHA image"""
        try:
            reload_btn = await page.query_selector('#kontaktdaten-captcha-reload-button')
            if reload_btn:
                await reload_btn.click()
                await asyncio.sleep(2)
                logger.info("🔄 CAPTCHA reloaded")
        except Exception as e:
            logger.debug(f"Could not reload CAPTCHA: {e}")
    
    async def _check_captcha_success(self, page: Page, captcha_selector: str) -> bool:
        """Check if CAPTCHA was solved successfully"""
        try:
            # Method 1: Check if contact info appears
            try:
                await page.wait_for_selector('#detail-bewerbung-adresse', timeout=5000)
                return True
            except:
                pass
            
            # Method 2: Check if CAPTCHA disappeared
            try:
                captcha_element = await page.query_selector(captcha_selector)
                if not captcha_element:
                    return True
            except:
                pass
            
            # Method 3: Check if application links are available
            try:
                await page.wait_for_selector('#detail-bewerbung-url', timeout=3000)
                return True
            except:
                pass
            
            return False
            
        except Exception as e:
            logger.debug(f"Error checking CAPTCHA success: {e}")
            return False
    
    def _log_captcha_attempt(self, success: bool, method: str, solution: str, confidence: float):
        """Log CAPTCHA solving attempts for debugging"""
        status = "SUCCESS" if success else "FAILED"
        logger.info(f"📊 CAPTCHA {status}: Method={method}, Solution='{solution}', Confidence={confidence:.2f}")
    
    def get_model_info(self) -> Dict:
        """Get information about the loaded model"""
        return {
            'model_name': self.model_name,
            'device': self.device,
            'trocr_attempts': self.trocr_attempts,
            'twocaptcha_attempts': self.twocaptcha_attempts,
            'manual_timeout': self.manual_timeout,
            'confidence_threshold': self.confidence_threshold,
            'reload_between_attempts': self.reload_between_attempts,
            'max_total_attempts': self.max_total_attempts,
            'active_strategies': self.active_strategies,
            'model_loaded': self.model is not None,
            'statistics': self.stats
        }
    
    def _get_success_rate_summary(self) -> str:
        """Get success rate summary for logging"""
        if self.stats['total_attempts'] == 0:
            return "No attempts yet"
        
        total_successes = (self.stats['trocr_successes'] + 
                          self.stats['twocaptcha_successes'] + 
                          self.stats['manual_successes'])
        
        success_rate = (total_successes / self.stats['total_attempts']) * 100
        
        return (f"Success rate: {success_rate:.1f}% "
                f"(TrOCR: {self.stats['trocr_successes']}, "
                f"2Captcha: {self.stats['twocaptcha_successes']}, "
                f"Manual: {self.stats['manual_successes']}, "
                f"Total: {total_successes}/{self.stats['total_attempts']})")
    
    def get_detailed_statistics(self) -> dict:
        """Get detailed statistics for monitoring"""
        total_attempts = self.stats['total_attempts']
        if total_attempts == 0:
            return {'no_data': True}
        
        total_successes = (self.stats['trocr_successes'] + 
                          self.stats['twocaptcha_successes'] + 
                          self.stats['manual_successes'])
        
        return {
            'total_attempts': total_attempts,
            'total_successes': total_successes,
            'total_failures': self.stats['failures'],
            'success_rate_percent': (total_successes / total_attempts) * 100,
            'strategy_breakdown': {
                'trocr': {
                    'successes': self.stats['trocr_successes'],
                    'rate_percent': (self.stats['trocr_successes'] / total_attempts) * 100
                },
                'twocaptcha': {
                    'successes': self.stats['twocaptcha_successes'], 
                    'rate_percent': (self.stats['twocaptcha_successes'] / total_attempts) * 100
                },
                'manual': {
                    'successes': self.stats['manual_successes'],
                    'rate_percent': (self.stats['manual_successes'] / total_attempts) * 100
                }
            },
            'configuration': {
                'strategies': self.strategies,
                'trocr_attempts': self.trocr_attempts,
                'twocaptcha_attempts': self.twocaptcha_attempts,
                'manual_timeout': self.manual_timeout,
                'max_total_attempts': self.max_total_attempts
            }
        }


# Utility functions
async def is_captcha_present(page: Page, selector: str) -> bool:
    """Check if CAPTCHA is present on page"""
    try:
        element = await page.query_selector(selector)
        return element is not None
    except:
        return False

async def wait_for_captcha_load(page: Page, selector: str, timeout: int = 10) -> bool:
    """Wait for CAPTCHA image to fully load"""
    try:
        await page.wait_for_selector(selector, timeout=timeout * 1000)
        await asyncio.sleep(2)  # Extra wait for TrOCR processing
        return True
    except:
        return False