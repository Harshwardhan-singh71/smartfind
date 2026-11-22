with open(r'c:\projects\smartfind_v3\test_ai_limits.py', 'r') as f:
    content = f.read()

# The file has single backslash causing \P warning
# Need to replace 'Run:  D:\PYTHON\python.exe test_ai_limits.py' with raw string equivalent

# Find and fix the Run line
import re
# Replace the Windows path with double backslashes
old_path = 'Run:  D:\\PYTHON\\python.exe test_ai_limits.py'
new_path = r'Run:  D:\PYTHON\python.exe test_ai_limits.py'  # raw string

# Actually, the issue is that \P is an invalid escape. The fix is to use \\P
# So change D:\PYTHON to D:\\PYTHON and D:\python to D:\\python

content = content.replace(
    'Run:  D:\\PYTHON\\python.exe test_ai_limits.py',
    'Run:  D:\\\\PYTHON\\\\python.exe test_ai_limits.py'
)

with open(r'c:\projects\smartfind_v3\test_ai_limits.py', 'w') as f:
    f.write(content)
print('Fixed the \\\\P issue')