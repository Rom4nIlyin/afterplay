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


# Recording and markers are core actions; suggest keys once so they work out of the box.
SUGGESTED_CORE_KEYS = {'record': 'Ctrl+Alt+F9', 'mark': 'Ctrl+Alt+F11'}


def suggest_core_keys(cfg):
    """One-time: offer record/mark shortcuts if the user has none and the combo is free."""
    if cfg.get('core_keys_version') == 1:
        return False
    hotkeys = cfg.setdefault('hotkeys', {})
    from hotkeys import DEFAULTS as BASE
    used = {str(v).casefold() for v in hotkeys.values() if v}
    used |= {v.casefold() for k, v in BASE.items() if not hotkeys.get(k)}
    for action, combo in SUGGESTED_CORE_KEYS.items():
        if action not in hotkeys and combo.casefold() not in used:
            hotkeys[action] = combo
            used.add(combo.casefold())
    cfg['core_keys_version'] = 1
    return True


def migrate(cfg):
    """Two quick clips with ready shortcuts (version 1.15.0)."""
    suggest_core_keys(cfg)
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
