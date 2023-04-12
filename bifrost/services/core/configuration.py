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


def get_tlm_dict_path():
    fname = Path(os.environ.get('TLM_DICT_FILENAME'))
    root = Path(os.environ.get('AIT_CONFIG')) # This is stupid, just use a real envar
    tlm_dict = Path(root.parent) / fname
    return tlm_dict


def get_cmd_dict_path():
    fname = Path(os.environ.get('CMD_DICT_FILENAME'))
    root = Path(os.environ.get('AIT_CONFIG')) # This is stupid, just use a real envar
    tlm_dict = Path(root.parent) / fname
    return tlm_dict

def load_config():
    config_path = get_config_path()
    with config_path.open() as f:
        data = os.path.expandvars(f.read())
        return yaml.load(data, Loader=yaml.Loader)
