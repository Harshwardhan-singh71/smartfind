import sys
sys.path.insert(0, r'c:\projects\smartfind_v3')
e = TimeoutError('Request timed out')
msg = str(e).lower()
print(f'message={msg}')
print(f'timed out in msg: {"timed out" in msg}')
print(f'timeout in msg: {"timeout" in msg}')