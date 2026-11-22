import sys, time
sys.path.insert(0, r'c:\projects\smartfind_v3')
import ai

# Reset state
ai._consecutive_failures = 0
ai._cb_until = 0.0
print(f"Before: _cb_until = {ai._cb_until}")

# Simulate what ask_text does with two consecutive busy errors
# This is the logic from ask_text's except block
busy = True  # TimeoutError "timed out" is always busy
_consecutive_failures = ai._consecutive_failures

# Attempt 1
print(f"Attempt 1: _consecutive_failures before = {_consecutive_failures}")
_consecutive_failures += 1
print(f"Attempt 1: _consecutive_failures after = {_consecutive_failures}")
if _consecutive_failures >= 2:
    ai._cb_until = time.time() + ai.BREAKER_PAUSE
    print(f"set _cb_until = {ai._cb_until}")
    _consecutive_failures = 0
else:
    print("not enough failures yet, would continue to attempt 2")

# Attempt 2 (simulate)
_consecutive_failures = ai._consecutive_failures  # reset to 0 after first simulation
print(f"\nAttempt 2: _consecutive_failures before = {_consecutive_failures}")
_consecutive_failures += 1
print(f"Attempt 2: _consecutive_failures after = {_consecutive_failures}")
if _consecutive_failures >= 2:
    ai._cb_until = time.time() + ai.BREAKER_PAUSE
    print(f"set _cb_until = {ai._cb_until}")
    _consecutive_failures = 0
else:
    print("not enough failures")

print(f"\nAfter: _cb_until = {ai._cb_until}")