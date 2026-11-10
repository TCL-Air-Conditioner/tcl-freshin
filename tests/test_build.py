import importlib.util
import json
from pathlib import Path
import re
import shutil
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]

class BuildTest(unittest.TestCase):
    def test_missing_and_available_media_build_without_changing_original(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/'source'; root.mkdir()
            for name in ('build_pages.py','template.html','player.js','sw-template.js','brand-logo.png'):
                shutil.copyfile(ROOT/name,root/name)
            spec=importlib.util.spec_from_file_location('freshin_build',root/'build_pages.py')
            mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
            slug=mod.TOPICS[0][0]; (root/slug).mkdir(); video=root/slug/(slug+'.mp4')
            original=b'sample original video bytes'; video.write_bytes(original)
            dest=Path(td)/'output'
            with mock.patch.object(mod,'cover',return_value=b'\xff\xd8sample-jpeg'):
                mod.build(dest)
                first=(dest/slug/'index.html').read_text()
                self.assertEqual((dest/slug/(slug+'.mp4')).read_bytes(), original)
                self.assertEqual(video.read_bytes(), original)
                catalog=json.loads(re.search(r'<script id="videoCatalog" type="application/json">(.*?)</script>',first).group(1))
                self.assertTrue(catalog['topics'][0]['cover'])
                self.assertIsNone(catalog['topics'][1]['file'])
                self.assertIn('Video coming soon.',(dest/mod.TOPICS[1][0]/'index.html').read_text())
                self.assertEqual(len(list(dest.glob('*/index.html'))),12)
                second=Path(td)/'second'; mod.build(second)
                self.assertEqual(first,(second/slug/'index.html').read_text())
                self.assertEqual((dest/'sw.js').read_text(),(second/'sw.js').read_text())

if __name__=='__main__': unittest.main()
