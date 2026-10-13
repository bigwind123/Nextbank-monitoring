"""File-only tests; monitoring programs and network clients are never imported."""
import ast
import json
from pathlib import Path
import tempfile
import unittest

import yaml

from tools import render


class RenderTests(unittest.TestCase):
    def test_yaml_round_trip_preserves_special_characters(self):
        value = "'\"\\\n$:@ #"
        text = render.render_yaml('setting: __CFG_0001__\n', {'CFG_0001': value})
        self.assertEqual(yaml.safe_load(text)['setting'], value)

    def test_python_round_trip_preserves_literal(self):
        value = "'\"\\\n$:@ #"
        text = render.render_python("setting = '__CFG_0001__'\n", {'CFG_0001': value})
        tree = ast.parse(text)
        self.assertEqual(tree.body[0].value.value, value)

    def test_perl_quoted_value_escapes_interpolation(self):
        text = render.render_literals('my $x = "__CFG_0001__";', {'CFG_0001': '$@"'}, perl=True)
        self.assertEqual(text, 'my $x = "\\$\\@\\\"";')

    def test_unquoted_directive_rejects_control_characters(self):
        with self.assertRaises(render.ConfigurationError) as caught:
            render.render_literals('proxy_pass __CFG_0001__;', {'CFG_0001': 'private; directive'})
        self.assertNotIn('private;', str(caught.exception))

    def test_missing_setting_is_reported_by_key(self):
        with self.assertRaisesRegex(render.ConfigurationError, 'CFG_0001'):
            render.prepare({'components/access/config.conf': '__CFG_0001__'}, {})

    def test_repository_cannot_receive_private_output(self):
        with self.assertRaises(render.ConfigurationError):
            render.outside_repository(render.ROOT / 'private-output')

    def test_invalid_private_json_does_not_echo_input(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'settings.json'
            path.write_text('private-invalid-value', encoding='utf-8')
            with self.assertRaises(render.ConfigurationError) as caught:
                render.load_values(path)
            self.assertNotIn('private-invalid-value', str(caught.exception))

    def test_certificate_file_is_read_relative_to_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'material').write_text('line-one\nline-two\n', encoding='utf-8')
            settings = root / 'settings.json'
            settings.write_text(json.dumps({'CFG_0001': {'file': 'material'}}), encoding='utf-8')
            self.assertEqual(render.load_values(settings)['CFG_0001'], 'line-one\nline-two\n')

    def test_all_configmaps_are_assembled_without_executing_code(self):
        files = render.source_files([])
        values = {key: 'value' for key in render.required_keys(files)}
        rendered = render.prepare(files, values)
        bindings = json.loads((render.ROOT / 'config/configmap-files.json').read_text(encoding='utf-8'))
        for name, mapping in bindings.items():
            doc = yaml.safe_load(rendered[name])
            for key, asset in mapping.items():
                self.assertEqual(doc['data'][key], rendered[asset])
        for name, text in rendered.items():
            if name.endswith('.py'):
                ast.parse(text)
            if name.endswith(('.yaml', '.yml', '.yaml.disabled')):
                list(yaml.safe_load_all(text))


if __name__ == '__main__':
    unittest.main()
