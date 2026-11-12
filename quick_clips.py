"""Optional fixed-length shortcuts share the existing rolling capture."""
DEFAULTS = (30, 120)
ACTIONS = ('clip_1', 'clip_2')
# Suggested shortcuts for new installs; never override a user's own choice.
SUGGESTED_KEYS = {'clip_1': 'Ctrl+Alt+F6', 'clip_2': 'Ctrl+Alt+F7'}


def durations(values=None):
    values = list(DEFAULTS) if values is None else values
    # Older versions stored three clips; keep the first two.
    if isinstance(values, list) and len(values) == 3:
        values = values[:2]
    if not isinstance(values, list) or len(values) != 2:
        raise ValueError('Укажите две длительности быстрых клипов')
    if any(type(value) is not int or not 5 <= value <= 1800 for value in values):
        raise ValueError('Длительность быстрого клипа: от 5 до 1800 секунд')
    return list(values)


def retention(replay):
    values = durations(replay.suite.cfg.get('quick_clips'))
    hotkeys = replay.suite.cfg.get('hotkeys', {})
    return max([replay.settings['seconds']] + [values[i] for i, key in enumerate(ACTIONS) if hotkeys.get(key)])


def migrate(cfg):
    """Two quick clips with ready shortcuts (version 1.14.5 Afterglow)."""
    if cfg.get('quick_clips_version') == 2:
        return False
    try:cfg['quick_clips'] = durations(cfg.get('quick_clips'))
    except ValueError:cfg['quick_clips'] = list(DEFAULTS)
    hotkeys = cfg.setdefault('hotkeys', {})
    hotkeys.pop('clip_3', None)
    used = {str(v).casefold() for k, v in hotkeys.items() if v}
    from hotkeys import DEFAULTS as BASE
    used |= {v.casefold() for k, v in BASE.items() if not hotkeys.get(k)}
    for action, combo in SUGGESTED_KEYS.items():
        if not hotkeys.get(action) and combo.casefold() not in used:
            hotkeys[action] = combo
            used.add(combo.casefold())
    cfg['quick_clips_version'] = 2
    return True
