import yaml
from enum import Enum
from pathlib import Path
from collections import deque, defaultdict, namedtuple
import itertools

from ait.core import log
import ait

Alarm_Result = namedtuple('Alarm_Result', 'state threshold')

default_yaml = ait.config.get('alarms.filename')


def partition(items, predicate):
    a, b = itertools.tee((predicate(item), item) for item in items)
    return ((item for pred, item in a if not pred),
            (item for pred, item in b if pred))


class Alarm_State(Enum):
    # Values are comments
    # Green is lowest priority, Red is highest
    # We return as soon as one of these matches
    # Otherwise, return green
    RED = 'PANIC'
    YELLOW = 'CAUTION'
    BLUE = 'NOTIFY'
    GREEN = 'GO'


class Alarm_Check():

    @classmethod
    def load_yaml(cls, yaml_filepath=None):
        if not yaml_filepath:
            yaml_filepath = default_yaml
        cls.alarm_filepath = Path(yaml_filepath)
        try:
            with cls.alarm_filepath.open() as f:
                cls.alarm_map = yaml.full_load(f.read())
        except Exception as e:
            log.error(f"Could not open limits yaml: {cls.alarm_filepath}")
            raise e

    def __init__(self, yaml_filepath=None):
        self.load_yaml(yaml_filepath)
        self.threshold_tracker = defaultdict(lambda: defaultdict(dict))

    @classmethod
    def get_alarm_state(cls, packet_name, packet_field, value):
        alarm_associations = cls.alarm_map.get(packet_name, {}).get(packet_field, None)
        if alarm_associations is None:
            log.debug((f"could not find alarms for {packet_name}:{packet_field}"
                       f"check {cls.alarm_filepath}. "
                       f"assuming state is {Alarm_State.GREEN}"))
            return Alarm_State.GREEN

        for color in Alarm_State:
            alarm_values = alarm_associations.get(color.name, None)
            if alarm_values is None:
                continue

            exact_alarms, interval_alarms = partition(alarm_values, (lambda i: isinstance(i, (tuple))))
            f = (lambda low, high: low <= value and value < high)
            g = (lambda i: i == value)
            interval_results = any(f(*interval) for interval in interval_alarms)
            exact_results = any(g(exact) for exact in exact_alarms)
            res = interval_results or exact_results
            if res:
                return Alarm_State[color.name]
        return Alarm_State.GREEN

    @classmethod
    def side_load_yaml(cls, yaml_str):
        cls.alarm_map = yaml.full_load(yaml_str)

    def get_alarm_thresholds(self, packet_name, field):
        a = self.threshold_tracker[packet_name][field]
        if not a:
            self.init_alarm_threshold(packet_name, field)
            a = self.threshold_tracker[packet_name][field]
        return a

    def init_alarm_threshold(self, packet_name, field):
        try:
            alarm_values = self.alarm_map[packet_name][field]
        except KeyError:
            alarm_values = None

        if alarm_values is None:
            return

        threshold = alarm_values.get('THRESHOLD', 0)
        self.threshold_tracker[packet_name][field] = deque(itertools.repeat(None, threshold), maxlen=threshold)

    def check_state(self, packet_name, field, value):
        threshold_states = self.get_alarm_thresholds(packet_name, field)
        instant_state = self.get_alarm_state(packet_name, field, value)

        if threshold_states:
            threshold_states.append(instant_state)

        if instant_state is Alarm_State.GREEN:
            return Alarm_Result(instant_state, False)

        elif instant_state is Alarm_State.BLUE:
            log.info(f"{packet_name}:{field} is in notify state {instant_state}")
            return Alarm_Result(instant_state, False)

        elif instant_state is Alarm_State.RED or instant_state is Alarm_State.YELLOW:
            if (all((i is Alarm_State.RED or i is Alarm_State.YELLOW) for i in threshold_states)):
                log.warn(f"Packet: {packet_name} field: {field} with value {value} has triggered its threshold and is in {instant_state}")
                return Alarm_Result(instant_state, True)
            else:
                log.warn(f"{packet_name}:{field} is in {instant_state} but has not triggered threshold")
                return Alarm_Result(instant_state, False)

    def __call__(self, packet_name, field, value):
        if self.alarm_map is None:
            return Alarm_Result(Alarm_State.GREEN, False)

        res = self.check_state(packet_name, field, value)
        return res
