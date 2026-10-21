"""Download the complete public upstream and insert one reversible byte block."""
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
import urllib.error
import urllib.request

UPSTREAM_URL = 'https://johnshall.github.io/Shadowrocket-ADBlock-Rules-Forever/sr_top500_banlist_ad.conf'
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'dist/shadowrocket_personal.conf'
BEGIN = b'# BEGIN PERSONAL RULES'
END = b'# END PERSONAL RULES'
MAX_BYTES = 20 * 1024 * 1024


def custom_rules(text):
    result = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith(('#', ';')):
            continue
        fields = line.split(',')
        if len(fields) != 3 or fields[0] not in ('DOMAIN', 'DOMAIN-SUFFIX') or fields[2] != 'PROXY':
            raise ValueError('custom rule must be DOMAIN/DOMAIN-SUFFIX,domain,PROXY')
        domain = fields[1]
        if len(domain) > 253 or '.' not in domain or re.fullmatch(r'[0-9.]+', domain):
            raise ValueError('invalid domain')
        if any(not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?', label) for label in domain.split('.')):
            raise ValueError('invalid domain label')
        if line not in result:
            result.append(line)
    if not result:
        raise ValueError('no custom rules')
    return result


def inspect(data):
    if not data or len(data) > MAX_BYTES:
        raise ValueError('empty or oversized configuration')
    text = data.decode('utf-8-sig')
    if '\x00' in text or re.search(r'<\s*(?:!doctype\s+html|html|body)\b', text, re.I):
        raise ValueError('HTML or binary response')
    if BEGIN in data or END in data:
        raise ValueError('existing personal managed marker')
    lines = data.splitlines(keepends=True)
    sections = []
    offset = 0
    for index, line in enumerate(lines):
        value = line.decode('utf-8-sig').strip()
        if re.fullmatch(r'\[[^\]]+\]', value):
            sections.append((value, index, offset))
        # Fail closed: no automatic URL rewrite is permitted. Ordinary source comments are retained.
        if re.match(r'\s*#!', value) or re.match(r'\s*(?:#\s*)?(?:update[-_ ]?(?:url|interval)|config[-_ ]?url|subscription[-_ ]?url|url)\s*[:=]', value, re.I):
            raise ValueError('possible configuration update directive requires review')
        offset += len(line)
    if not any(s[0].lower() == '[general]' for s in sections):
        raise ValueError('missing General section')
    rules = [s for s in sections if s[0].lower() == '[rule]']
    if len(rules) != 1:
        raise ValueError('expected exactly one Rule section')
    _, start, position = rules[0]
    stop = next((s[1] for s in sections if s[1] > start), len(lines))
    active = [line.decode('utf-8').strip() for line in lines[start+1:stop]
              if line.strip() and not line.lstrip().startswith((b'#', b';'))]
    finals = [line for line in active if re.match(r'FINAL\b', line, re.I)]
    if len(finals) != 1 or finals[0] != active[-1] or not re.fullmatch(r'FINAL,[A-Za-z0-9_-]+(?:,dns-failed)?', finals[0], re.I):
        raise ValueError('expected one valid terminal FINAL rule')
    if any(',' not in line for line in active):
        raise ValueError('malformed active rule')
    header = lines[start]
    newline = b'\r\n' if header.endswith(b'\r\n') else b'\n'
    if not header.endswith(b'\n'):
        raise ValueError('Rule header must have a newline')
    return position + len(header), newline, len(active)


def patch(data, rules):
    position, newline, count = inspect(data)
    # Validate callers too, rather than trusting a pre-parsed list.
    rules = custom_rules('\n'.join(rules))
    block = newline.join([BEGIN, *(r.encode('ascii') for r in rules), END]) + newline
    output = data[:position] + block + data[position:]
    assert output[:position] + output[position+len(block):] == data
    return output, {'upstream_bytes': len(data), 'output_bytes': len(output),
                    'added_bytes': len(block), 'upstream_rules': count,
                    'output_rules': count + len(rules), 'upstream_sha256': hashlib.sha256(data).hexdigest(),
                    'output_sha256': hashlib.sha256(output).hexdigest(),
                    'byte_preservation': True, 'update_directive_rewrites': []}


class HTTPSRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        if not newurl.startswith('https://'):
            raise ValueError('insecure redirect rejected')
        return super().redirect_request(request, fp, code, msg, headers, newurl)


def download(url=UPSTREAM_URL, opener=None, sleep=time.sleep):
    if not url.startswith('https://'):
        raise ValueError('HTTPS required')
    if opener is None:
        opener = urllib.request.build_opener(HTTPSRedirect()).open
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'shadowrocket-personal-rules/1'})
            with opener(request, timeout=30) as response:
                if response.status != 200 or not response.geturl().startswith('https://'):
                    raise ValueError('unexpected HTTP status or insecure redirect')
                if 'html' in response.headers.get('Content-Type', '').lower():
                    raise ValueError('HTML content type')
                size = response.headers.get('Content-Length')
                if size and int(size) > MAX_BYTES:
                    raise ValueError('Content-Length exceeds limit')
                data = response.read(MAX_BYTES + 1)
                inspect(data)
                return data
        except (OSError, ValueError) as error:
            if attempt == 2:
                raise RuntimeError(f'upstream download/validation failed: {error}') from error
            sleep(attempt + 1)


def build(output=OUTPUT, fetch=download, rules_path=ROOT / 'custom_rules.txt'):
    rules = custom_rules(rules_path.read_text(encoding='utf-8'))
    data = fetch()
    result, report = patch(data, rules)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=output.parent, delete=False) as file:
            temporary = file.name
            file.write(result)
        os.replace(temporary, output)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
    return report


def main():
    try:
        report = build()
        print(json.dumps(report, indent=2))
        summary = f'Upstream: {UPSTREAM_URL}\n\nTests passed before build. Byte preservation: PASS.\n\n```json\n{json.dumps(report, indent=2)}\n```\n'
        code = 0
    except Exception as error:
        summary = f'Build FAILED: {error}\nLast published artifact is retained.\n'
        print(summary, file=sys.stderr)
        code = 1
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as file:
            file.write(summary)
    return code


if __name__ == '__main__':
    sys.exit(main())
