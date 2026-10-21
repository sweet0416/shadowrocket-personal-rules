import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch as mock_patch
import urllib.error

from scripts import build_config as b

BASE = b'[General]\nipv6 = false\n[Rule]\nDOMAIN-SUFFIX,meta.ai,PROXY\nFINAL,DIRECT\n[Host]\na = 1\n'
RULES = ['DOMAIN-SUFFIX,metaaivm.com,PROXY', 'DOMAIN-SUFFIX,meta.ai,PROXY', 'DOMAIN-SUFFIX,ai.meta.com,PROXY']


class Response(io.BytesIO):
    status = 200
    headers = {'Content-Type': 'text/plain'}

    def geturl(self):
        return 'https://example.com/config'


class Tests(unittest.TestCase):
    def test_bytes_formats_and_determinism(self):
        for newline in (b'\n', b'\r\n'):
            for bom in (b'', b'\xef\xbb\xbf'):
                for ending in (True, False):
                    with self.subTest(newline=newline, bom=bom, ending=ending):
                        source = bom + BASE.replace(b'\n', newline)
                        if not ending:
                            source = source[:-len(newline)]
                        output, report = b.patch(source, RULES)
                        start = output.index(b.BEGIN)
                        stop = output.index(b.END) + len(b.END) + len(newline)
                        self.assertEqual(output[:start] + output[stop:], source)
                        self.assertEqual(output, b.patch(source, RULES)[0])
                        self.assertEqual(output.count(b'DOMAIN-SUFFIX,meta.ai,PROXY'), 2)
                        self.assertEqual(report['output_rules'], report['upstream_rules'] + 3)
                        self.assertEqual(output.index(b.BEGIN), source.index(b'[Rule]') + len(b'[Rule]') + len(newline))
                        with self.assertRaises(ValueError):
                            b.patch(output, RULES)

    def test_custom_comments_blank_dedup(self):
        self.assertEqual(b.custom_rules('\n# hi\n; hi\n' + RULES[0] + '\n' + RULES[0]), [RULES[0]])
        self.assertEqual(b.custom_rules('DOMAIN,example.com,PROXY'), ['DOMAIN,example.com,PROXY'])

    def test_invalid_custom(self):
        for text in ('', 'DOMAIN,a..com,PROXY', 'DOMAIN,-x.com,PROXY', 'DOMAIN,x-.com,PROXY',
                     'DOMAIN,*.com,PROXY', 'DOMAIN,127.0.0.1,PROXY', 'DOMAIN,x.com,DIRECT',
                     'DOMAIN,x.com,PROXY,extra', '[Rule]', 'DOMAIN,x.com,PROXY\n[MITM]',
                     'DOMAIN,x com,PROXY', 'DOMAIN,https://x.com,PROXY', 'DOMAIN,中.com,PROXY'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                b.custom_rules(text)

    def test_invalid_structure(self):
        for data in (BASE.replace(b'[Rule]', b'[Other]'), BASE + b'[Rule]\nFINAL,DIRECT\n',
                     BASE.replace(b'FINAL,DIRECT\n', b''), BASE.replace(b'FINAL,DIRECT', b'FINAL'),
                     BASE.replace(b'FINAL,DIRECT', b'FINAL,DIRECT,extra'),
                     BASE.replace(b'FINAL,DIRECT', b'FINAL,DIRECT\nDOMAIN,x.com,PROXY'),
                     BASE.replace(b'FINAL,DIRECT', b'FINAL,DIRECT\nFINAL,PROXY'),
                     b'', b'<html>Error</html>', b'not configuration',
                     BASE + b'#!update-url=https://example.com\n',
                     BASE + b'update-url = https://example.com\n'):
            with self.subTest(data=data), self.assertRaises(ValueError):
                b.patch(data, RULES)

    def test_download_failures_preserve_artifact(self):
        def failing(error):
            def opener(*args, **kwargs):
                raise error
            return opener
        def response(data, status=200, headers=None):
            def opener(*args, **kwargs):
                self.assertEqual(kwargs['timeout'], 30)
                obj = Response(data)
                obj.status = status
                if headers is not None:
                    obj.headers = headers
                return obj
            return opener
        openers = [failing(TimeoutError('timeout')),
                   failing(urllib.error.HTTPError('https://example.com', 503, 'Unavailable', {}, None)),
                   response(BASE, 404), response(b''), response(b'<html>error</html>'),
                   response(BASE, headers={'Content-Type': 'text/html'}),
                   response(BASE, headers={'Content-Length': str(b.MAX_BYTES + 1)}),
                   response(b'x' * (b.MAX_BYTES + 1))]
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'valid.conf'
            target.write_bytes(b'LAST VALID')
            for opener in openers:
                calls = []
                with self.subTest(opener=opener), self.assertRaises(RuntimeError):
                    b.build(target, fetch=lambda: b.download(opener=opener, sleep=calls.append))
                self.assertEqual(calls, [1, 2])
                self.assertEqual(target.read_bytes(), b'LAST VALID')
            with self.assertRaises(OSError), mock_patch.object(b.os, 'replace', side_effect=OSError('failure')):
                b.build(target, fetch=lambda: BASE)
            self.assertEqual(target.read_bytes(), b'LAST VALID')
            self.assertEqual(list(Path(directory).iterdir()), [target])

    def test_https_and_valid_download(self):
        with self.assertRaises(ValueError):
            b.download('http://example.com')
        self.assertEqual(b.download(opener=lambda *a, **k: Response(BASE)), BASE)
        with self.assertRaises(ValueError):
            b.HTTPSRedirect().redirect_request(None, None, 302, '', {}, 'http://example.com')
        for end in (b'FINAL,DIRECT', b'FINAL,DIRECT\n', b'FINAL,DIRECT\r\n'):
            source = b'[General]\nipv6=false\n[Rule]\n' + end
            output, _ = b.patch(source, RULES)
            self.assertTrue(output.endswith(end))


if __name__ == '__main__':
    unittest.main()
