"""Parser for Controller Companion `.ccp` profiles.

The format is line based and human readable. Header lines are `key: value`;
binding lines are `<input> @ <label>: <action> [args...] [norepeat]`. A line is
a binding if and only if it contains ' @ ' before the first colon — headers such
as `title: Call of Duty: Modern Warfare` may themselves contain colons.

Inputs may carry a `back ` prefix, meaning the binding belongs to the secondary
layer that is active while the button bound to `modifier back` is held.

Grammar observed across the shipped Workshop profiles:

    process: iw3sp iw3mp
    title: Call of Duty: Modern Warfare
    mouse acceleration: 3000
    mouse wheel speed: 600
    workshop id: 490457861
    icon: <base64 png>
    a @ Space: key Space norepeat
    start @ Esc+F10: key Escape+F10 norepeat
    left stick @ WSAD keys: key W S A D norepeat
    right stick @ Mouse movement: mouse movement
    left trigger @ Right mouse button: mouse right
    dpad up @ Mouse scroll up: mouse scroll up norepeat
    backbutton @ Use Secondary Bindings: modifier back
    back x @ Minimize all windows: cmd keyCombo LWin M
    back guide @ Turn off controller: cmd turnOffController
    left thumb @ Show Virtual Keyboard: virtualkeyboard show
    guide @ Launch Steam Big-Picture: cmd process steam://open/bigpicture
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# Inputs as they are spelled in .ccp, mapped to our canonical names. The names
# already match one-to-one with SDL's game controller vocabulary, which is why
# SDL is used for input rather than raw evdev button codes.
DIGITAL_INPUTS = {
    'a', 'b', 'x', 'y',
    'start', 'guide', 'backbutton',
    'left shoulder', 'right shoulder',
    'left thumb', 'right thumb',
    'dpad up', 'dpad down', 'dpad left', 'dpad right',
    'left trigger', 'right trigger',
}
STICK_INPUTS = {'left stick', 'right stick'}
ALL_INPUTS = DIGITAL_INPUTS | STICK_INPUTS


class CcpError(Exception):
    pass


@dataclass
class Binding:
    """One `<input> @ <label>: <action>` line."""
    input: str                     # canonical input name, without 'back '
    layer: str                     # 'main' or 'back'
    label: str                     # human label from the profile
    action: str                    # key | mouse | cmd | virtualkeyboard | modifier
    args: list[str] = field(default_factory=list)
    norepeat: bool = False
    raw: str = ''

    @property
    def is_stick(self) -> bool:
        return self.input in STICK_INPUTS


@dataclass
class Profile:
    title: str = ''
    processes: list[str] = field(default_factory=list)
    mouse_speed: int = 0
    mouse_acceleration: int = 0
    mouse_wheel_speed: int = 0
    workshop_id: str = ''
    icon_b64: str = ''
    bindings: list[Binding] = field(default_factory=list)
    source: str = ''
    unsupported: list[str] = field(default_factory=list)
    is_workshop: bool = False
    # Controller Companion blocks program-launching bindings in Workshop
    # profiles until the user approves them; same rule here.
    launch_allowed: bool = True

    @property
    def name(self) -> str:
        return self.title or self.workshop_id or self.source or 'untitled'

    def binding_for(self, input_name: str, layer: str) -> Binding | None:
        for b in self.bindings:
            if b.input == input_name and b.layer == layer:
                return b
        return None

    @property
    def back_modifier_input(self) -> str | None:
        """Input that switches to the secondary layer while held, if any."""
        for b in self.bindings:
            if b.action == 'modifier' and b.args[:1] == ['back']:
                return b.input
        return None


_HEADER_KEYS = {
    'process', 'title', 'mouse speed', 'mouse acceleration',
    'mouse wheel speed', 'workshop id', 'icon', 'description', 'author',
}


def _split_binding(line: str) -> tuple[str, str, str] | None:
    """Return (input, label, action) for a binding line, else None."""
    if ' @ ' not in line:
        return None
    head, _, rest = line.partition(' @ ')
    if ':' not in rest:
        return None
    label, _, action = rest.partition(':')
    return head.strip(), label.strip(), action.strip()


def parse_string(text: str, source: str = '') -> Profile:
    prof = Profile(source=source)
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip('﻿').strip()
        if not line or line.startswith('#'):
            continue

        split = _split_binding(line)
        if split is None:
            key, _, value = line.partition(':')
            key = key.strip().lower()
            value = value.strip()
            if key == 'process':
                prof.processes = value.split()
            elif key == 'title':
                prof.title = value
            elif key == 'mouse speed':
                prof.mouse_speed = _int(value)
            elif key == 'mouse acceleration':
                prof.mouse_acceleration = _int(value)
            elif key == 'mouse wheel speed':
                prof.mouse_wheel_speed = _int(value)
            elif key == 'workshop id':
                prof.workshop_id = value
            elif key == 'icon':
                prof.icon_b64 = value
            elif key not in _HEADER_KEYS:
                prof.unsupported.append(f'{source}:{lineno}: unknown header {key!r}')
            continue

        input_name, label, action_str = split
        input_name = input_name.strip().lower()
        layer = 'main'
        if input_name.startswith('back ') and input_name != 'back button':
            layer = 'back'
            input_name = input_name[len('back '):].strip()
        input_name = _canonical_input(input_name)
        if input_name not in ALL_INPUTS:
            prof.unsupported.append(f'{source}:{lineno}: unknown input {input_name!r}')
            continue

        tokens = action_str.split()
        if not tokens:
            prof.unsupported.append(f'{source}:{lineno}: empty action')
            continue
        norepeat = False
        if tokens[-1].lower() == 'norepeat':
            norepeat = True
            tokens = tokens[:-1]
        action = tokens[0].lower()
        args = tokens[1:]
        if action == 'null':
            # explicitly unbound in the editor; keep it so it masks a default
            prof.bindings.append(Binding(
                input=input_name, layer=layer, label=label, action='null',
                args=[], norepeat=True, raw=line,
            ))
            continue
        if action not in ('key', 'mouse', 'cmd', 'virtualkeyboard', 'modifier'):
            prof.unsupported.append(f'{source}:{lineno}: unknown action {action!r}')
            continue

        prof.bindings.append(Binding(
            input=input_name, layer=layer, label=label, action=action,
            args=args, norepeat=norepeat, raw=line,
        ))
    return prof


def dump(profile: Profile) -> str:
    """Serialise back to .ccp, in the same shape Controller Companion writes."""
    lines: list[str] = []
    if profile.processes:
        lines.append(f'process: {" ".join(profile.processes)}')
    if profile.title:
        lines.append(f'title: {profile.title}')
    if profile.mouse_speed:
        lines.append(f'mouse speed: {profile.mouse_speed}')
    if profile.mouse_acceleration:
        lines.append(f'mouse acceleration: {profile.mouse_acceleration}')
    if profile.mouse_wheel_speed:
        lines.append(f'mouse wheel speed: {profile.mouse_wheel_speed}')
    for b in profile.bindings:
        name = f'back {b.input}' if b.layer == 'back' else b.input
        action = b.action if b.action == 'null' else ' '.join([b.action, *b.args])
        suffix = ' norepeat' if b.norepeat and b.action != 'null' else ''
        lines.append(f'{name} @ {b.label}: {action}{suffix}')
    if profile.icon_b64:
        lines.append(f'icon: {profile.icon_b64}')
    if profile.workshop_id:
        lines.append(f'workshop id: {profile.workshop_id}')
    return '\n'.join(lines) + '\n'


def write_file(profile: Profile, path) -> None:
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(dump(profile))


def parse_file(path) -> Profile:
    with open(path, encoding='utf-8', errors='replace') as fh:
        return parse_string(fh.read(), source=str(path))


def _int(value: str) -> int:
    m = re.search(r'-?\d+', value)
    return int(m.group()) if m else 0


_INPUT_ALIASES = {
    'back button': 'backbutton',
    'back_button': 'backbutton',
    'select': 'backbutton',
    'lb': 'left shoulder',
    'rb': 'right shoulder',
    'lt': 'left trigger',
    'rt': 'right trigger',
    'ls': 'left stick',
    'rs': 'right stick',
    'l3': 'left thumb',
    'r3': 'right thumb',
}


def _canonical_input(name: str) -> str:
    name = ' '.join(name.split())
    return _INPUT_ALIASES.get(name, name)
