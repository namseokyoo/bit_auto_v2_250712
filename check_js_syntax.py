#!/usr/bin/env python3
import requests
import re
import json

url = "http://158.180.82.112:8080/"
response = requests.get(url)
html = response.text

# Extract JavaScript from HTML
script_match = re.search(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
if script_match:
    js_code = script_match.group(1)
    
    # Common syntax error patterns
    issues = []
    
    # Check for unclosed strings
    lines = js_code.split('\n')
    for i, line in enumerate(lines, 1):
        # Count quotes
        single_quotes = line.count("'") - line.count("\\'")
        double_quotes = line.count('"') - line.count('\\"')
        
        if single_quotes % 2 != 0:
            issues.append(f"Line {i}: Unclosed single quote")
            print(f"Line {i}: {line.strip()}")
        if double_quotes % 2 != 0:
            issues.append(f"Line {i}: Unclosed double quote")
            print(f"Line {i}: {line.strip()}")
            
    # Check for template literal issues
    for i, line in enumerate(lines, 1):
        if '`' in line:
            # Check for ${} inside backticks
            if '${' in line and not line.count('`') >= 2:
                issues.append(f"Line {i}: Template literal issue")
                print(f"Line {i}: {line.strip()}")
                
    # Look for common syntax errors
    for i, line in enumerate(lines, 1):
        # Check for stray characters
        if line.strip() and not line.strip().startswith('//'):
            # Check for invalid characters
            if '​' in line:  # Zero-width space
                issues.append(f"Line {i}: Contains zero-width space")
                print(f"Line {i} (has invisible character): {repr(line.strip())}")
            if '\xa0' in line:  # Non-breaking space
                issues.append(f"Line {i}: Contains non-breaking space")
                print(f"Line {i} (has nbsp): {repr(line.strip())}")
                
    # Check for unmatched brackets
    open_braces = js_code.count('{')
    close_braces = js_code.count('}')
    open_brackets = js_code.count('[')
    close_brackets = js_code.count(']')
    open_parens = js_code.count('(')
    close_parens = js_code.count(')')
    
    print(f"\nBracket counts:")
    print(f"  Braces: {{ {open_braces} vs }} {close_braces}")
    print(f"  Brackets: [ {open_brackets} vs ] {close_brackets}")
    print(f"  Parens: ( {open_parens} vs ) {close_parens}")
    
    if issues:
        print(f"\n❌ Found {len(issues)} potential issues:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("\n✅ No obvious syntax errors found")
        
    # Try to find the specific error location
    print("\nSearching for specific syntax patterns...")
    
    # Look for common typos
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped:
            # Missing semicolons after }
            if stripped.endswith('}') and i < len(lines) - 1:
                next_line = lines[i].strip()
                if next_line and not next_line.startswith(('/', '}', 'else', 'catch', 'finally', ',', ')', ';')):
                    print(f"Line {i}: Might need semicolon after }}")
                    
            # Double commas
            if ',,' in line:
                print(f"Line {i}: Double comma found")
                
            # Unclosed function calls
            if line.count('(') > line.count(')'):
                print(f"Line {i}: More ( than ) : {line.strip()}")