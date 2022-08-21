import yaml
from enum import Enum
from pathlib import Path
from collections import deque, defaultdict, namedtuple
import itertools

from ait.core import log

Alarm_Result = namedtuple('Alarm_Result', 'state threshold')


def partition(items, predicate):
    a, b = itertools.tee((predicate(item), item) for item in items)
    return ((item for pred, item in a if not pred),
            (item for pred, item in b if pred))


class Alarm_State(Enum):
    # Values are comments
    # Green is lowest priority, Red is highest
    RED = 'PANIC'
    YELLOW = 'CAUTION'
    BLUE = 'NOTIFY'
    GREEN = 'GO'


class Alarm_Check():

    @classmethod
    def load_yaml(cls, yaml_filepath):
        cls.alarm_filepath = Path(yaml_filepath)
        with cls.alarm_filepath.open() as f:
            cls.alarm_map = yaml.full_load(f.read())

    def __init__(self, yaml_path=None):
        if yaml_path:
            self.load_yaml(yaml_path)
        self.threshold_tracker = defaultdict(lambda: defaultdict(dict))


    @classmethod
    def get_alarm_state(cls, packet_name, packet_field, value):
        alarm_associations = cls.alarm_map[packet_name][packet_field]
        if not alarm_associations:
            return Alarm_State.GREEN
        for color, alarm_values in alarm_associations.items():
            if alarm_values is None or color == "THRESHOLD": # Skip empty and Threshold key
                continue

            exact_alarms, interval_alarms = partition(alarm_values, (lambda i: isinstance(i, (tuple))))
            f = (lambda low, high: low <= value and value < high)
            g = (lambda i: i == value)
            interval_results = any(f(*interval) for interval in interval_alarms)
            exact_results = any(g(exact) for exact in exact_alarms)
            res = interval_results or exact_results
            if res:
                return Alarm_State[color]
        log.info("No matches")
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
        alarm_values = self.alarm_map[packet_name][field]
        if alarm_values is None:
            return
        else:
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
                log.warn(f"{packet_name}:{field} has triggered its threshold")
                log.warn(f"{packet_name}:{field} is in {instant_state}")
                return Alarm_Result(instant_state, True)
            else:
                log.warn(f"{packet_name}:{field} is in {instant_state} but has not triggered threshold")
                return Alarm_Result(instant_state, False)

    def __call__(self, packet_name, field, value):
        res = self.check_state(packet_name, field, value)
        return res
