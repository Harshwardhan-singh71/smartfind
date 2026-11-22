import sys
sys.path.insert(0, r'c:\projects\smartfind_v3')
import ai
import time

print(f"Before: ai._cb_until = {ai._cb_until}")

# Simulate what ask_text does
ai._cb_until = time.time() + ai.BREAKER_PAUSE
print(f"After: ai._cb_until = {ai._cb_until}")

# Check if it's the same object
print(f"Module dict: {ai.__dict__['_cb_until']}")