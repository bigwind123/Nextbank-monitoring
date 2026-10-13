"""Offline source, template and publication checks. Application modules are not imported."""
import ast
import json
from pathlib import Path
import re
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
TOKEN = re.compile(r'__(CFG_\d{4})__')
SKIP = {'.git', '.local', '.venv', '__pycache__'}


class UniqueLoader(yaml.SafeLoader):
    pass


def mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise ValueError('Duplicate YAML key')
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)


def main():
    errors = []
    counts = {'python': 0, 'yaml': 0, 'json': 0, 'files': 0}
    catalog = json.loads((ROOT / 'config/parameters.json').read_text(encoding='utf-8'))
    bindings = json.loads((ROOT / 'config/configmap-files.json').read_text(encoding='utf-8'))
    manifests = {}
    for path in sorted(ROOT.rglob('*')):
        if not path.is_file() or any(part in SKIP for part in path.relative_to(ROOT).parts):
            continue
        name = path.relative_to(ROOT).as_posix()
        counts['files'] += 1
        try:
            text = path.read_text(encoding='utf-8')
            if path.suffix == '.py':
                ast.parse(text)
                counts['python'] += 1
            if path.name.endswith(('.yml', '.yaml', '.yaml.disabled')):
                docs = list(yaml.load_all(text, Loader=UniqueLoader))
                counts['yaml'] += 1
                if name.startswith('manifests/'):
                    for doc in docs:
                        manifests[doc['kind'], doc['metadata']['name']] = (name, doc)
            if path.suffix == '.json':
                json.loads(text)
                counts['json'] += 1
            if name.startswith(('components/', 'manifests/')):
                for match in TOKEN.finditer(text):
                    if match[1] not in catalog or name not in catalog[match[1]]['files']:
                        errors.append(name + ': unregistered parameter')
                if re.search(r'(?:\d{1,3}\.){3}\d{1,3}|-----BEGIN [^-]*(?:KEY|CERTIFICATE)-----', text):
                    errors.append(name + ': embedded address or certificate')
            if path.suffix == '.md':
                if text.count('```') % 2:
                    errors.append(name + ': unclosed fence')
                for link in re.findall(r'\]\(([^)]+)\)', re.sub(r'```.*?```', '', text, flags=re.S)):
                    if not link.startswith(('https://', 'http://', '#')) and not (path.parent / link.split('#')[0]).exists():
                        errors.append(name + ': broken document link')
        except Exception as error:
            errors.append(name + ': ' + type(error).__name__)
    for manifest, sources in bindings.items():
        try:
            doc = yaml.safe_load((ROOT / manifest).read_text(encoding='utf-8'))
            if set(doc['data']) != set(sources):
                errors.append(manifest + ': ConfigMap key mismatch')
            for asset in sources.values():
                if not (ROOT / asset).is_file():
                    errors.append(manifest + ': missing source file')
        except Exception as error:
            errors.append(manifest + ': ' + type(error).__name__)
    external = json.loads((ROOT / 'config/external-resources.json').read_text(encoding='utf-8'))
    for name, doc in manifests.values():
        if doc['kind'] in {'Deployment', 'StatefulSet'}:
            pod = doc['spec']['template']
        elif doc['kind'] == 'CronJob':
            pod = doc['spec']['jobTemplate']['spec']['template']
        else:
            continue
        if 'serviceaccount' in pod:
            errors.append(name + ': invalid service account field')
        volumes = {volume['name']: volume for volume in pod['spec'].get('volumes', [])}
        for container in pod['spec'].get('containers', []):
            for mount in container.get('volumeMounts', []):
                volume = volumes.get(mount['name'], {})
                if 'configMap' not in volume:
                    continue
                config_name = volume['configMap']['name']
                config = manifests.get(('ConfigMap', config_name))
                if config:
                    keys = config[1]['data']
                else:
                    declaration = next((x for x in external if x['kind'] == 'ConfigMap' and x['name'] == config_name and x['scope'] == Path(name).parts[1]), None)
                    if declaration is None:
                        errors.append(name + ': missing ConfigMap')
                        continue
                    keys = declaration['keys']
                if 'subPath' in mount and mount['subPath'] not in keys:
                    errors.append(name + ': missing ConfigMap subPath')
    poster = ast.parse((ROOT / 'components/alerting/CM-Alert-poster/ticket_creater.py').read_text(encoding='utf-8'))
    handlers = next(node.value for node in ast.walk(poster) if isinstance(node, ast.Assign) and any(ast.unparse(target) == 'self.handlers' for target in node.targets))
    known_handlers = {key.value for key in handlers.keys}
    for path in (ROOT / 'components/alerting/CM-Alert-condition').glob('*.yaml'):
        rule = yaml.safe_load(path.read_text(encoding='utf-8'))
        if len(rule.get('command', [])) > 3 and rule['command'][3] not in known_handlers:
            errors.append(path.name + ': unregistered event handler')
    if any((ROOT / '.github/workflows').glob('*')):
        errors.append('Unexpected automated workflow')
    print(json.dumps({'counts': counts, 'errors': errors}, ensure_ascii=False))
    return bool(errors)


if __name__ == '__main__':
    sys.exit(main())
