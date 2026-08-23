"""Convert a `.ccp` profile into a Steam Input configuration (VDF).

Why this exists: on a Steam Deck, Steam Input already owns the controller and
does per-game remapping, so running PadPilot's own remapper there means fighting
it. What Steam cannot do is read Controller Companion's profiles. Converting
them means the Deck gets the profile without a second remapper, without root,
and without `/dev/uinput`.

The schema was taken from Steam's own templates in
`controller_base/templates/*.vdf`, not from documentation:

    "controller_mappings" { version 3, controller_type, group*, preset }

A `group` has an id, a `mode` (four_buttons / dpad / trigger / switches /
joystick_mouse) and named inputs, each holding activators -> bindings. The
`preset.group_source_bindings` block attaches each group to a physical source
(button_diamond, dpad, joystick, right_joystick, left_trigger, right_trigger,
switch).

Not everything survives the trip: Steam has no equivalent of the `.ccp`
secondary layer or of program-launching bindings. Those are reported rather
than silently dropped.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .ccp import Profile

# .NET Keys name (as .ccp stores it) -> Steam Input key token.
KEY_TO_STEAM = {
    **{c: c for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"},
    **{f"D{d}": str(d) for d in range(10)},
    **{f"F{n}": f"F{n}" for n in range(1, 13)},
    **{f"NUMPAD{d}": f"KEYPAD_{d}" for d in range(10)},
    "SPACE": "SPACE", "RETURN": "RETURN", "ENTER": "RETURN", "ESCAPE": "ESCAPE",
    "TAB": "TAB", "BACK": "BACKSPACE", "BACKSPACE": "BACKSPACE",
    "DELETE": "DELETE", "INSERT": "INSERT", "HOME": "HOME", "END": "END",
    "PRIOR": "PAGE_UP", "NEXT": "PAGE_DOWN",
    "UP": "UP_ARROW", "DOWN": "DOWN_ARROW", "LEFT": "LEFT_ARROW", "RIGHT": "RIGHT_ARROW",
    "LSHIFTKEY": "LEFT_SHIFT", "RSHIFTKEY": "RIGHT_SHIFT", "SHIFTKEY": "LEFT_SHIFT",
    "LCONTROLKEY": "LEFT_CONTROL", "RCONTROLKEY": "RIGHT_CONTROL",
    "CONTROLKEY": "LEFT_CONTROL",
    "LMENU": "LEFT_ALT", "RMENU": "RIGHT_ALT", "MENU": "LEFT_ALT",
    "LWIN": "LEFT_WINDOWS", "RWIN": "RIGHT_WINDOWS",
    "CAPITAL": "CAPSLOCK", "CAPSLOCK": "CAPSLOCK",
    "OEMCOMMA": "COMMA", "OEMPERIOD": "PERIOD", "OEMQUESTION": "FORWARD_SLASH",
    "OEM1": "SEMICOLON", "OEMSEMICOLON": "SEMICOLON", "OEMQUOTES": "SINGLE_QUOTE",
    "OEMTILDE": "BACKQUOTE", "OEM3": "BACKQUOTE",
    "OEMMINUS": "DASH", "OEMPLUS": "EQUALS",
    "OEMOPENBRACKETS": "LEFT_BRACKET", "OEMCLOSEBRACKETS": "RIGHT_BRACKET",
    "OEMPIPE": "BACKSLASH", "OEMBACKSLASH": "BACKSLASH",
    "VOLUMEUP": "VOLUME_UP", "VOLUMEDOWN": "VOLUME_DOWN", "VOLUMEMUTE": "MUTE",
    "MEDIANEXTTRACK": "NEXT_TRACK", "MEDIAPREVIOUSTRACK": "PREV_TRACK",
    "MEDIAPLAYPAUSE": "PLAY_PAUSE",
    "DECIMAL": "KEYPAD_PERIOD", "ADD": "KEYPAD_PLUS", "SUBTRACT": "KEYPAD_MINUS",
    "MULTIPLY": "KEYPAD_MULTIPLY", "DIVIDE": "KEYPAD_DIVIDE",
}

MOUSE_TO_STEAM = {
    "left": "mouse_button LEFT",
    "right": "mouse_button RIGHT",
    "middle": "mouse_button MIDDLE",
    "xbutton1": "mouse_button BACK",
    "xbutton2": "mouse_button FORWARD",
}

# .ccp input -> (group source, input name inside the group, group mode)
BUTTON_LAYOUT = {
    "a": ("button_diamond", "button_a", "four_buttons"),
    "b": ("button_diamond", "button_b", "four_buttons"),
    "x": ("button_diamond", "button_x", "four_buttons"),
    "y": ("button_diamond", "button_y", "four_buttons"),
    "dpad up": ("dpad", "dpad_north", "dpad"),
    "dpad down": ("dpad", "dpad_south", "dpad"),
    "dpad left": ("dpad", "dpad_west", "dpad"),
    "dpad right": ("dpad", "dpad_east", "dpad"),
    "left trigger": ("left_trigger", "click", "trigger"),
    "right trigger": ("right_trigger", "click", "trigger"),
    "left shoulder": ("switch", "left_bumper", "switches"),
    "right shoulder": ("switch", "right_bumper", "switches"),
    "start": ("switch", "button_escape", "switches"),
    "backbutton": ("switch", "button_menu", "switches"),
    "guide": ("switch", "button_capture", "switches"),
    "left thumb": ("joystick", "click", "joystick_move"),
    "right thumb": ("right_joystick", "click", "joystick_mouse"),
}

STICK_DIRECTIONS = ["dpad_north", "dpad_south", "dpad_west", "dpad_east"]


@dataclass
class Conversion:
    vdf: str
    dropped: list = field(default_factory=list)


def _binding_for(action: str, args: list[str], label: str) -> str | None:
    """One `.ccp` action as a Steam binding string, or None if it has no equivalent."""
    if action == "key":
        keys = [k for a in args for k in a.split("+")]
        tokens = [KEY_TO_STEAM.get(k.strip().upper()) for k in keys]
        if not tokens or any(t is None for t in tokens):
            return None
        # Steam expresses a chord as several keys in one binding.
        return "key_press " + ", ".join(tokens) + (f", {label}" if label else "")
    if action == "mouse":
        sub = (args[0] if args else "").lower()
        if sub in MOUSE_TO_STEAM:
            return MOUSE_TO_STEAM[sub]
        if sub == "scroll":
            direction = "SCROLL_DOWN" if args[1:2] == ["down"] else "SCROLL_UP"
            return f"mouse_wheel {direction}"
    return None


def _input_block(name: str, binding: str, indent: str) -> str:
    i = indent
    return (
        f'{i}"{name}"\n{i}{{\n'
        f'{i}\t"activators"\n{i}\t{{\n'
        f'{i}\t\t"Full_Press"\n{i}\t\t{{\n'
        f'{i}\t\t\t"bindings"\n{i}\t\t\t{{\n'
        f'{i}\t\t\t\t"binding"\t\t"{binding}"\n'
        f'{i}\t\t\t}}\n{i}\t\t}}\n{i}\t}}\n{i}}}\n'
    )


def steam_template_dirs() -> list:
    """Where Steam keeps the templates it lists in the controller config UI.

    Dropping a `controller_*.vdf` here makes it appear under Templates, which is
    the only route that does not involve the Workshop or Steam's own UI.
    """
    from pathlib import Path
    roots = [
        Path.home() / ".steam/steam",
        Path.home() / ".steam/debian-installation",
        Path.home() / ".local/share/Steam",
        Path.home() / ".var/app/com.valvesoftware.Steam/data/Steam",
    ]
    return [r / "controller_base/templates" for r in roots
            if (r / "controller_base/templates").is_dir()]


def convert(profile: Profile, controller_type: str = "controller_steamdeck") -> Conversion:
    """Build a Steam Input config from a parsed `.ccp` profile."""
    dropped: list[str] = []
    # source -> (mode, {input name: binding})
    groups: dict[str, tuple[str, dict]] = {}

    def put(source: str, mode: str, input_name: str, binding: str) -> None:
        groups.setdefault(source, (mode, {}))[1][input_name] = binding

    for b in profile.bindings:
        if b.layer == "back":
            dropped.append(f"{b.input} (secondary layer): {b.label}")
            continue
        if b.action in ("null", "modifier"):
            continue
        if b.action in ("cmd", "virtualkeyboard"):
            dropped.append(f"{b.input}: {b.label} [{b.action} {' '.join(b.args)}]")
            continue

        if b.is_stick:
            source = "joystick" if b.input == "left stick" else "right_joystick"
            sub = (b.args[0] if b.args else "").lower()
            if b.action == "mouse" and sub == "movement":
                groups.setdefault(source, ("joystick_mouse", {}))
                continue
            if b.action == "key" and len(b.args) >= 4:
                # four keys, in .ccp order: up, down, left, right
                for direction, key in zip(STICK_DIRECTIONS, b.args[:4]):
                    binding = _binding_for("key", [key], "")
                    if binding:
                        put(source, "dpad", direction, binding)
                    else:
                        dropped.append(f"{b.input} {direction}: {key} (no Steam key)")
                continue
            dropped.append(f"{b.input}: {b.label} [{b.action} {' '.join(b.args)}]")
            continue

        placement = BUTTON_LAYOUT.get(b.input)
        if placement is None:
            dropped.append(f"{b.input}: {b.label} (no Steam equivalent)")
            continue
        source, input_name, mode = placement
        binding = _binding_for(b.action, b.args, b.label)
        if binding is None:
            dropped.append(f"{b.input}: {b.label} [{b.action} {' '.join(b.args)}]")
            continue
        put(source, mode, input_name, binding)

    lines = [
        '"controller_mappings"',
        "{",
        '\t"version"\t\t"3"',
        f'\t"title"\t\t"{profile.name} (from Controller Companion)"',
        f'\t"description"\t\t"Converted from {profile.source or "a .ccp profile"} by PadPilot"',
        f'\t"controller_type"\t\t"{controller_type}"',
    ]
    bindings_by_id: dict[int, str] = {}
    for group_id, (source, (mode, inputs)) in enumerate(sorted(groups.items())):
        bindings_by_id[group_id] = source
        lines.append('\t"group"')
        lines.append("\t{")
        lines.append(f'\t\t"id"\t\t"{group_id}"')
        lines.append(f'\t\t"mode"\t\t"{mode}"')
        lines.append('\t\t"inputs"')
        lines.append("\t\t{")
        for name, binding in inputs.items():
            lines.append(_input_block(name, binding, "\t\t\t").rstrip("\n"))
        lines.append("\t\t}")
        lines.append("\t}")

    lines.append('\t"preset"')
    lines.append("\t{")
    lines.append('\t\t"id"\t\t"0"')
    lines.append('\t\t"name"\t\t"Default"')
    lines.append('\t\t"group_source_bindings"')
    lines.append("\t\t{")
    for group_id, source in bindings_by_id.items():
        lines.append(f'\t\t\t"{group_id}"\t\t"{source} active"')
    lines.append("\t\t}")
    lines.append("\t}")
    lines.append("}")
    return Conversion(vdf="\n".join(lines) + "\n", dropped=dropped)


def parse_vdf(text: str) -> dict:
    """Minimal VDF reader, only good enough to verify what we emit."""
    import re
    tokens = re.findall(r'"([^"]*)"|([{}])', text)
    stack = [{}]
    pending = None
    for quoted, brace in tokens:
        if brace == "{":
            node: dict = {}
            key = pending or f"_{len(stack[-1])}"
            existing = stack[-1].get(key)
            if existing is None:
                stack[-1][key] = node
            elif isinstance(existing, list):
                existing.append(node)
            else:
                stack[-1][key] = [existing, node]
            stack.append(node)
            pending = None
        elif brace == "}":
            stack.pop()
        elif pending is None:
            pending = quoted
        else:
            stack[-1][pending] = quoted
            pending = None
    return stack[0]


def _tests_placeholder() -> None:  # pragma: no cover
    """Tests live in tests/test_steaminput.py."""
