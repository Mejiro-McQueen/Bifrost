import pytest

from ait.core.alarms import Alarm_Check, Alarm_State, Alarm_Result
from random import randint
import itertools


@pytest.fixture(scope='session', autouse=True)
def text_yaml():
    x = """
packet_1:
  field_1:
    RED:
      - !!python/tuple [5, 7]
      - !!python/tuple [2, 3]
    YELLOW:
      - !!python/tuple [7, 10]
    BLUE:
      - !!python/tuple [22, 23]
    THRESHOLD: 5

  field_2:
    BLUE:
      - !!python/tuple [-.Inf, .inf]
    THRESHOLD: 10

packet_2:
  field_1:
    RED:
      - 22
    YELLOW:
      - !!python/tuple [7, 10]
    BLUE:
      - !!python/tuple [5, .inf]
    THRESHOLD: 6

packet_3:
  field_1:
    RED:
        - 'Some String or Enum'

packet_4:
  field_1:
    BLUE:
        - 5732edd7e4e1240b868e15bc95d36339

packet_5:
  field_1:
    """
    return x


@pytest.fixture()
def alarm_obj(text_yaml):
    a = Alarm_Check()
    a.side_load_yaml(text_yaml)
    yield a


@pytest.mark.parametrize("test_input, expected",
                         [
                             (('packet_1', 'field_1', 2), Alarm_Result(Alarm_State.RED, False)),
                             (('packet_1', 'field_2', 2), Alarm_Result(Alarm_State.BLUE, False)),
                             (('packet_1', 'field_2', 29), Alarm_Result(Alarm_State.BLUE, False)),
                             (('packet_2', 'field_1', 4), Alarm_Result(Alarm_State.GREEN, False)),
                             (('packet_1', 'field_2', randint(-1000, 1000)), Alarm_Result(Alarm_State.BLUE, False)),
                             (('packet_2', 'field_1', -22), Alarm_Result(Alarm_State.GREEN, False)),
                             (('packet_3', 'field_1', 'Some String or Enum'), Alarm_Result(Alarm_State.RED, True)),
                             (('packet_4', 'field_1', '5732edd7e4e1240b868e15bc95d36339'), Alarm_Result(Alarm_State.BLUE, False)),
                             (('packet_4', 'field_1', '6732edd7e4e1240b868e15bc95d36339'), Alarm_Result(Alarm_State.GREEN, False))
                         ])
def test_simple(test_input, expected, alarm_obj):
    assert alarm_obj(*test_input) == expected

@pytest.mark.parametrize("test_input, expected, threshold",
                         [
                             (('packet_1', 'field_1', 2), Alarm_Result(Alarm_State.RED, False), 4),
                         ])
def test_thresholds(test_input, expected, threshold, alarm_obj):
    stim = itertools.repeat(test_input, threshold)
    for i in stim:
        assert alarm_obj(*i) == expected

    threshold_exceeded = Alarm_Result(expected.state, True)
    for i in stim:
        assert alarm_obj(*i) == threshold_exceeded

@pytest.mark.parametrize("test_input, expected, threshold, good_val, good_state",
                         [
                             (('packet_1', 'field_1', 2), Alarm_Result(Alarm_State.RED, False), 4, 200, Alarm_State.GREEN),
                         ])
def test_threshold_recover(test_input, expected, threshold, good_val, good_state, alarm_obj):
    stim = itertools.repeat(test_input, threshold)
    for i in stim:
        assert alarm_obj(*i) == expected

    threshold_exceeded = Alarm_Result(expected.state, True)
    for i in stim:
        assert alarm_obj(*i) == threshold_exceeded

    packet, field, val = test_input
    good_input = (packet, field, good_val)
    assert alarm_obj(*good_input) == Alarm_Result(good_state, False)


@pytest.mark.parametrize("test_input, expected",
                         [
                             (('packet_5', 'field_1', 2), Alarm_Result(Alarm_State.GREEN, False)),
                         ])
def test_no_assocs(test_input, expected, alarm_obj):
    assert alarm_obj(*test_input) == expected
