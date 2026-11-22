import sys, time
sys.path.insert(0, r'c:\projects\smartfind_v3')
import ai

# Reset state
ai._consecutive_failures = 0
ai._cb_until = 0.0
print(f"Initial: _cb_until = {ai._cb_until}")

# Simulate two consecutive busy errors in ask_text
# This mimics what happens inside ask_text's except block
for _ in range(2):  # Two attempts
    # Simulate a TimeoutError busy failure
    _consecutive_failures = ai._consecutive_failures  # Read from module
    _consecutive_failures += 1
    print(f"After failure: _consecutive_failures = {_consecutive_failures}")
    if _consecutive_failures >= 2:
        ai._cb_until = time.time() + ai.BREAKER_PAUSE
        print(f"Set _cb_until = {ai._cb_until}")
        _consecutive_failures = 0
        break

print(f"Final: _cb_until = {ai._cb_until}")
print(f"is_available: {ai.is_available()}")