#!/usr/bin/env python3
"""Validate Gathering 15 outputs without network or line-folder writes."""
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import struct
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'shared/wall-thumbnail'))
import thumbnail

BARE = 'https://api.imd.fun/artifacts/250525790c1987cbb52114bd4e77926f023ac1dc10b73ffc2e1f56e32dfb8a36'


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.articles = 0
        self.scripts = 0
        self.images = []
        self.section = None
        self.sections = {}
        self.capture = False
        self.heading = ''

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'section':
            self.section = attrs.get('id')
            self.sections.setdefault(self.section, [])
        if tag == 'article':
            self.articles += 1
        if tag == 'img':
            self.images.append(attrs['src'])
        if tag == 'script':
            self.scripts += 1
        if tag == 'h3':
            self.capture = True
            self.heading = ''

    def handle_data(self, data):
        if self.capture:
            self.heading += data

    def handle_endtag(self, tag):
        if tag == 'h3' and self.capture:
            match = re.match(r'Round ([0-9]+)', self.heading)
            if match and self.section:
                self.sections[self.section].append(int(match[1]))
            self.capture = False
        if tag == 'section':
            self.section = None


def jpeg_dimensions(raw):
    assert raw[:2] == b'\xff\xd8' and raw[-2:] == b'\xff\xd9'
    at = 2
    while at < len(raw):
        assert raw[at] == 255
        marker = raw[at + 1]
        size = int.from_bytes(raw[at + 2:at + 4], 'big')
        if marker == 0xc0:
            depth, height, width, channels = struct.unpack('>BHHB', raw[at + 4:at + 10])
            assert depth == 8 and channels == 3
            return width, height
        at += 2 + size
    raise ValueError('no baseline JPEG frame')


def main():
    wall = Path('artifacts/gathering/wall-v15.png')
    raw = wall.read_bytes()
    width, height, rows = thumbnail.png_rgb(wall)
    assert (width, height) == (1254, 1254)
    assert Path('artifacts/gathering/wall.png').read_bytes() == raw
    digest = hashlib.sha256(raw).hexdigest()
    jpg = Path('dist/gathering/15.jpg').read_bytes()
    assert jpeg_dimensions(jpg) == (512, 512) and len(jpg) < 100_000
    record = json.loads(Path('dist/gathering/15.json').read_text())
    assert set(record) == {'name', 'image', 'attributes'}
    assert record['image'] == 'https://api.imd.fun/artifacts/' + digest
    traits = record['attributes']
    assert [t['trait_type'] for t in traits] == ['Cave', 'Wall', 'Number', 'Left behind', 'Meaning', 'One thing']
    assert all(set(t) == {'trait_type', 'value'} for t in traits)
    assert [t['value'] for t in traits[:3]] == ['Moss', 'Gathering', 15]
    assert type(traits[2]['value']) is int and traits[-1]['value'] == 'Gathering'
    assert traits[3]['value'] == 'Shared Return Bounds'
    goals = json.loads(Path('dist/goals.json').read_text())
    assert goals == [{'line': n, 'goal': Path(f'line-{n}/GOAL.md').read_text().strip()} for n in range(1, 5)]
    records = list(Path('dist').glob('*/[0-9][0-9].json'))
    painted = pending = 0
    for p in records:
        item = json.loads(p.read_text())
        if item['name'] == 'Not painted yet':
            pending += 1
            assert item['image'] == BARE and item['attributes'] == [{'trait_type': 'Cave', 'value': 'Moss'}]
            assert not p.with_suffix('.jpg').exists()
        else:
            painted += 1
            assert p.with_suffix('.jpg').is_file()
    assert (len(records), painted, pending) == (161, 75, 86)
    for n in range(16, 22):
        assert json.loads(Path(f'dist/gathering/{n:02}.json').read_text())['name'] == 'Not painted yet'
    page = Path('dist/index.html').read_text()
    parsed = Page()
    parsed.feed(page)
    assert parsed.articles == len(records) and parsed.scripts == 0
    assert all(src.startswith('https://api.imd.fun/artifacts/') or (Path('dist') / src).is_file()
               for src in parsed.images)
    for slug in ('line-1', 'line-2', 'line-3', 'line-4', 'gathering'):
        painted_numbers = [int(p.stem) for p in sorted(Path('dist', slug).glob('[0-9][0-9].json'), reverse=True)
                           if json.loads(p.read_text())['name'] != 'Not painted yet']
        section_order = parsed.sections[slug][:len(painted_numbers)]
        assert section_order == painted_numbers
    visual = json.loads(Path('gathering/visual-checks.json').read_text())
    assert visual['output_sha256'] == digest and visual['changed_pixels_outside_addition'] == 0
    assert visual['source_sha256'] == json.loads(Path('dist/gathering/14.json').read_text())['image'].rsplit('/', 1)[-1]
    assert visual['format'] == 'PNG RGB 8-bit' and [visual['width'], visual['height']] == [width, height]
    assert visual['left_hand_digits'] == visual['right_hand_digits'] == 5 and visual['new_hands'] == 0
    assert visual['unmet_visual_requirements_observed'] == []
    checks = json.loads(Path('gathering/check-results.json').read_text())
    assert checks['all_passed'] and len(checks['checks']) == 146
    test_count = sum(c.get('test_count', 0) for c in checks['checks'])
    assert test_count == 1015 and all(c['passed'] for c in checks['checks'])
    shared_suite = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'shared/return-bounds', '-p', 'test_*.py'],
                                  capture_output=True, text=True, check=True)
    assert 'Ran 17 tests' in shared_suite.stderr
    demo = subprocess.run([sys.executable, '-B', 'shared/return-bounds/return_bounds.py', 'demo'],
                          capture_output=True, text=True, check=True)
    assert json.loads(demo.stdout)['verdict'] == 'ready'
    changed = subprocess.run(['git', 'diff', 'HEAD', '--name-only'], capture_output=True, text=True, check=True).stdout.splitlines()
    assert not any(p.startswith(('line-1/', 'line-2/', 'line-3/', 'line-4/', 'dist/line-')) for p in changed)
    oversized = [str(p) for root in ('gathering', 'shared', 'dist') for p in Path(root).rglob('*')
                 if p.is_file() and p.stat().st_size >= 100_000]
    assert not oversized, oversized
    assert Path('gathering/COINS.md').read_text().splitlines()[0] == 'none'
    assert not Path('gathering/coin-order.json').exists() and not Path('gathering/deploy-order.json').exists()
    result = {'schema': 'gathering-delivery-checks-v15',
              'authority': 'Local contributor checks; not independent certification.',
              'wall': {'path': str(wall), 'format': 'PNG RGB 8-bit', 'width': width, 'height': height,
                       'sha256': digest, 'bytes': len(raw), 'chunk_crcs_and_raster_valid': True,
                       'required_png_untracked': not subprocess.run(['git','ls-files',str(wall)],capture_output=True,text=True,check=True).stdout.strip()},
              'thumbnail': {'path': 'dist/gathering/15.jpg', 'format': 'baseline JPEG',
                            'width': 512, 'height': 512, 'bytes': len(jpg)},
              'visual_review': {'left_hand_digits': 5, 'right_hand_digits': 5, 'new_hands': 0,
                                'unmet_requirements_observed': [], 'changed_pixels': visual['changed_pixels'],
                                'changed_pixels_outside_addition': visual['changed_pixels_outside_addition']},
              'records': len(records), 'painted': painted, 'placeholders': pending,
              'gallery_articles': parsed.articles, 'goals': len(goals),
              'line_sources_and_records_unchanged': True, 'offline_tests': test_count,
              'offline_commands': len(checks['checks']), 'offline_expected_exits_matched': True,
              'shared_return_bounds_tests': 17, 'shared_return_bounds_demo': 'ready',
              'oversized_output_source_files': oversized}
    Path('gathering/delivery-checks-15.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
