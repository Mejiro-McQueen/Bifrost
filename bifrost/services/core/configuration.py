from bifrost.common.deep_dictionary_get import deep_get
from pathlib import Path
import os
import yaml
from ait.core import log

configuration_service = 'bifrost.services.core.configuration_service.Configuration'


def get_services():
    config = load_config()
    services = deep_get(config, 'bifrost.services', {})
    d = {d['service']['name']: d['service'] for d in services}
    # Promote config service to top, so that it is always started first.
    d = {configuration_service: d.pop(configuration_service), **d}
    return d


def get_config_path():
    res = Path(os.environ.get('BIFROST_SERVICES_CONFIG'))
    if not any([i in str(res) for i in ['service', 'svc']]):
        log.warn(f"Hueristic: Ambigious filename for bifrost dictionary {res}")
    if not res.exists():
        log.error(f"{res} not found.")
    return res


def get_tlm_dict_path():
    res = Path(os.environ.get('TLM_DICT_FILEPATH'))
    if not any([i in str(res) for i in ['tlm', 'telemetry']]):
        log.warn(f"Hueristic: Ambigious filename for telemetry dictionary {res}")
    if not res.exists():
        log.error(f"{res} not found.")
    return res


def get_cmd_dict_path():
    res = Path(os.environ.get('CMD_DICT_FILEPATH'))
    if not any([i in str(res) for i in ['cmd', 'command']]):
        log.warn(f"Heuristic: Ambigious filename for telemetry dictionary {res}")
    if not res.exists():
        log.error(f"{res} not found.")
    return res


def load_config():
    config_path = get_config_path()
    with config_path.open() as f:
        data = os.path.expandvars(f.read())
        return yaml.load(data, Loader=yaml.Loader)


def get_key_values():
    config = load_config()
    res = deep_get(config, 'bifrost.services')
    for i in res:
        if deep_get(i, 'service.name') == configuration_service:
            res = i
            break
    res = deep_get(res, 'service.key_values')
    return res
