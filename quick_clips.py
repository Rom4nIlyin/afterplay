"""Optional fixed-length shortcuts share the existing rolling capture."""
DEFAULTS = (30, 120, 300)
ACTIONS = ('clip_1', 'clip_2', 'clip_3')


def durations(values=None):
    values = list(DEFAULTS) if values is None else values
    if not isinstance(values, list) or len(values) != 3:
        raise ValueError('Укажите три длительности быстрых клипов')
    if any(type(value) is not int or not 5 <= value <= 1800 for value in values):
        raise ValueError('Длительность быстрого клипа: от 5 до 1800 секунд')
    return list(values)


def retention(replay):
    values = durations(replay.suite.cfg.get('quick_clips'))
    hotkeys = replay.suite.cfg.get('hotkeys', {})
    return max([replay.settings['seconds']] + [values[i] for i, key in enumerate(ACTIONS) if hotkeys.get(key)])
