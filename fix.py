with open(r'c:\projects\smartfind_v3\ai.py', 'r') as f:
    content = f.read()

# Replace _cb_until = time.time() + BREAKER_PAIZE with ai._cb_until = time.time() + BREAKER_PAUSE
# Only once (in ask_text function)
content = content.replace(
    '_cb_until = time.time() + BREAKER_PAUSE',
    'ai._cb_until = time.time() + BREAKER_PAUSE',
    1  # only replace first occurrence
)

with open(r'c:\projects\smartfind_v3\ai.py', 'w') as f:
    f.write(content)
print('Replacement done')