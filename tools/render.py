"""Render private configuration locally. This module never starts or deploys services."""
import argparse
import ast
import json
from pathlib import Path
import re
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
TOKEN = re.compile(r'__(CFG_\d{4})__')


class ConfigurationError(ValueError):
    pass


class Dumper(yaml.SafeDumper):
    pass


def string_representer(dumper, value):
    return dumper.represent_scalar('tag:yaml.org,2002:str', value, style='|' if '\n' in value else None)


Dumper.add_representer(str, string_representer)


def dump(value):
    return yaml.dump(value, Dumper=Dumper, allow_unicode=True, sort_keys=False, width=110)


def substitute(text, values):
    def value(match):
        key = match[1]
        if key not in values:
            raise ConfigurationError('Missing setting: ' + key)
        if not isinstance(values[key], str):
            raise ConfigurationError('Expected a string for ' + key)
        return values[key]
    return TOKEN.sub(value, text)


def render_python(text, values):
    class Replace(ast.NodeTransformer):
        def visit_Constant(self, node):
            if isinstance(node.value, str):
                return ast.copy_location(ast.Constant(substitute(node.value, values)), node)
            return node
    tree = ast.fix_missing_locations(Replace().visit(ast.parse(text)))
    return ast.unparse(tree) + '\n'


def render_literals(text, values, perl=False):
    """Escape placeholders inside quoted literals; reject unsafe unquoted values."""
    result = []
    quote = None
    i = 0
    while i < len(text):
        match = TOKEN.match(text, i)
        if match:
            value = substitute(match[0], values)
            if quote:
                if '\n' in value or '\r' in value or '\x00' in value:
                    raise ConfigurationError('Multiline value requires a YAML or certificate file setting: ' + match[1])
                value = value.replace('\\', '\\\\').replace(quote, '\\' + quote)
                if quote in {'"', '`'}:
                    value = value.replace('$', '\\$')
                    if perl:
                        value = value.replace('@', '\\@')
            elif not re.fullmatch(r'[A-Za-z0-9_./:@%+,=~-]+', value):
                raise ConfigurationError('Unsafe characters in unquoted setting: ' + match[1])
            result.append(value)
            i = match.end()
            continue
        char = text[i]
        if char == '\\' and i + 1 < len(text):
            result.append(text[i:i + 2])
            i += 2
            continue
        if char in {'"', "'", '`'}:
            if quote == char:
                quote = None
            elif quote is None:
                quote = char
        result.append(char)
        i += 1
    return ''.join(result)


def render_yaml(text, values):
    def walk(value):
        if isinstance(value, dict):
            return {key: walk(child) for key, child in value.items()}
        if isinstance(value, list):
            return [walk(child) for child in value]
        if isinstance(value, str):
            return substitute(value, values)
        return value
    return '---\n'.join(dump(walk(doc)) for doc in yaml.safe_load_all(text))


def render_file(path, text, values):
    if path.suffix == '.py':
        return render_python(text, values)
    if path.name.endswith(('.yaml', '.yml', '.yaml.disabled')):
        return render_yaml(text, values)
    if path.suffix == '.crt' or ('\n' not in text.strip() and TOKEN.fullmatch(text.strip())):
        return substitute(text, values)
    return render_literals(text, values, perl=path.suffix == '.pl')


def source_files(components):
    selected = {}
    for directory in ('components', 'manifests'):
        for path in sorted((ROOT / directory).rglob('*')):
            if path.is_file() and (not components or path.relative_to(ROOT).parts[1] in components):
                selected[path.relative_to(ROOT).as_posix()] = path.read_text(encoding='utf-8')
    return selected


def required_keys(files):
    return sorted({match[1] for text in files.values() for match in TOKEN.finditer(text)})


def load_values(path):
    try:
        settings = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(settings, dict):
            raise ConfigurationError('Settings must be a JSON object.')
        values = {}
        for key, value in settings.items():
            if isinstance(value, dict) and set(value) == {'file'}:
                private_file = Path(value['file']).expanduser()
                if not private_file.is_absolute():
                    private_file = path.parent / private_file
                values[key] = private_file.read_text(encoding='utf-8')
            elif isinstance(value, str):
                values[key] = value
            elif value is not None:
                raise ConfigurationError('Expected a string or file reference for ' + key)
        return values
    except ConfigurationError:
        raise
    except Exception:
        raise ConfigurationError('Cannot read private settings; values were not printed.') from None


def outside_repository(path):
    path = path.expanduser().resolve()
    if path.is_relative_to(ROOT):
        raise ConfigurationError('Private settings and rendered output must be outside the repository.')
    return path


def prepare(files, values):
    missing = set(required_keys(files)) - set(values)
    if missing:
        raise ConfigurationError('Missing settings: ' + ', '.join(sorted(missing)))
    rendered = {}
    for name, text in files.items():
        try:
            rendered[name] = render_file(Path(name), text, values)
        except ConfigurationError:
            raise
        except Exception:
            raise ConfigurationError('Cannot render ' + name + '; values were not printed.') from None
    bindings = json.loads((ROOT / 'config/configmap-files.json').read_text(encoding='utf-8'))
    for manifest, mapping in bindings.items():
        if manifest not in rendered:
            continue
        if any(asset not in rendered for asset in mapping.values()):
            raise ConfigurationError('Select the matching component for ' + manifest)
        doc = yaml.safe_load(rendered[manifest])
        doc['data'] = {key: rendered[asset] for key, asset in mapping.items()}
        rendered[manifest] = dump(doc)
    for name, text in rendered.items():
        if TOKEN.search(text) or '__SOURCE_FILE__' in text:
            raise ConfigurationError('Unresolved placeholder in ' + name)
    return rendered


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--component', action='append', default=[])
    parser.add_argument('--catalog', action='store_true', help='Print required field names only.')
    parser.add_argument('--write-settings', type=Path, help='Write empty settings outside the repository.')
    parser.add_argument('--settings', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    files = source_files(args.component)
    if not files:
        raise ConfigurationError('No matching component files.')
    keys = required_keys(files)
    if args.catalog:
        catalog = json.loads((ROOT / 'config/parameters.json').read_text(encoding='utf-8'))
        print(json.dumps({key: catalog[key] for key in keys}, ensure_ascii=False, indent=2))
        return
    if args.write_settings:
        path = outside_repository(args.write_settings)
        with path.open('x', encoding='utf-8', newline='\n') as handle:
            handle.write(json.dumps(dict.fromkeys(keys), indent=2) + '\n')
        print('Empty settings file created. No service was started.')
        return
    if not args.settings or not args.output:
        raise ConfigurationError('--settings and --output are required.')
    settings = outside_repository(args.settings)
    output = outside_repository(args.output)
    if output.exists():
        raise ConfigurationError('Output must be a new directory; existing files are never overwritten.')
    rendered = prepare(files, load_values(settings))
    # All validation finishes before writing any private output.
    for name, text in rendered.items():
        target = (output / name).resolve()
        if not target.is_relative_to(output):
            raise ConfigurationError('Invalid output path.')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding='utf-8', newline='\n')
    print(json.dumps({'rendered_files': len(rendered), 'services_started': 0}))


if __name__ == '__main__':
    try:
        main()
    except ConfigurationError as error:
        sys.exit(str(error))
