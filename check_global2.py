import sys
sys.path.insert(0, r'c:\projects\smartfind_v3')
import ai

print(f'Before: ai._cb_until = {ai._cb_until}')

# Simulate what ask_text does
global__cb = ai._cb_until
print(f'Access via global: {global__cb}')

# Try to set it like ask_text would
ai._cb_until = 999.0
print(f'After set: ai._cb_until = {ai._cb_until}')

# Reset
ai._cb_until = 0.0
print(f'Reset: ai._cb_until = {ai._cb_until}')