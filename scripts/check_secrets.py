#!/usr/bin/env python3
"""
pre-commit hook：掃描檔案中的機密模式（API key、private key 等）。
由 .pre-commit-config.yaml 的 secret-pattern-check hook 呼叫。
"""
import re
import sys

PATTERNS = [
    (r'AIza[0-9A-Za-z_-]{35}', 'Google API Key'),
    (r'AKIA[0-9A-Z]{16}', 'AWS Access Key'),
    (r'sk-[a-zA-Z0-9]{20,}', 'OpenAI/Stripe Secret Key'),
    (r'ghp_[a-zA-Z0-9]{36}', 'GitHub PAT'),
    (r'-----BEGIN (?:RSA |EC )?PRIVATE KEY', 'Private Key'),
]


def main() -> int:
    found = False
    for filepath in sys.argv[1:]:
        try:
            content = open(filepath, 'r', encoding='utf-8', errors='ignore').read()
            for pat, name in PATTERNS:
                for _ in re.finditer(pat, content):
                    print(f'  [FAIL] {name} detected in {filepath}')
                    found = True
        except Exception:
            pass
    return 1 if found else 0


if __name__ == '__main__':
    sys.exit(main())
