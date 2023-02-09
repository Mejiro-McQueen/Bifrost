from bifrost.common.deep_dictionary_get import deep_get
from pathlib import Path
import os
import yaml


def get_services():
    config = load_config()
    services = deep_get(config, 'bifrost.services', {})
    d = {d['service']['name']: d['service'] for d in services}
    return d


def get_config_path():
    return Path(os.environ.get('BIFROST_SERVICES_CONFIG'))


def load_config():
    config_path = get_config_path()
    with config_path.open() as f:
        data = os.path.expandvars(f.read())
        return yaml.load(data, Loader=yaml.Loader)
