"""Live check of ai.py. Run: D:\\PYTHON\\python.exe check_ai.py"""
import ai

print("Key found and AI available:", ai.is_available())
print("Privacy filter demo:")
print("  ", ai.redact("Call me on 9876543210 or mail a@b.com, card 4111 1111 1111 1111, id 1234 5678 9012"))

answer = ai.ask_json(
    'Turn this into JSON with the keys "title", "category", "colour". '
    'Message: "I lost my black Boat earphones near the library yesterday"'
)
print("Gemini JSON answer:", answer)
if answer is None:
    print("Reason:", ai.last_error)
    print("That is fine for the site (it falls back), but send me the Reason line above (not your key).")
