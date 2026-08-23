"""PadPilot for Decky — convert Controller Companion profiles on the Deck.

Subscribing to a `.ccp` profile on the Workshop and then having to reach for
desktop mode to use it is the problem this solves. Everything here is stdlib
plus the vendored conversion core, so the plugin needs no binary wheels, no
root, and no /dev/uinput — unlike PadPilot's own remapper, which would be
fighting Steam Input in Game Mode anyway.
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "py_modules"))

from padpilot_core import ccp  # noqa: E402
from padpilot_core.steaminput import convert  # noqa: E402

WORKSHOP_APP_ID = "367670"          # Controller Companion
STEAM_ROOTS = [
    "~/.steam/steam",
    "~/.local/share/Steam",
    "~/.steam/debian-installation",
    "~/.var/app/com.valvesoftware.Steam/data/Steam",
]


def _expand(path):
    # realpath, not abspath: on SteamOS ~/.steam/steam is a symlink to
    # ~/.local/share/Steam, so both spellings are the same directory. Without
    # resolving, every profile is found twice and every install is written
    # twice — the device reported 22 subscribed profiles for 11 files.
    return os.path.realpath(os.path.expanduser(path))


def _dedupe(paths):
    seen, out = set(), []
    for p in paths:
        real = os.path.realpath(p)
        if real not in seen:
            seen.add(real)
            out.append(real)
    return out


def _steam_roots():
    return _dedupe([_expand(r) for r in STEAM_ROOTS if os.path.isdir(_expand(r))])


def _library_paths():
    """Every Steam library, so Workshop content on an SD card is found too."""
    import re
    found = []
    for root in _steam_roots():
        found.append(root)
        vdf = os.path.join(root, "steamapps", "libraryfolders.vdf")
        try:
            with open(vdf, errors="replace") as fh:
                text = fh.read()
        except OSError:
            continue
        for m in re.finditer(r'"path"\s+"([^"]+)"', text):
            if os.path.isdir(m.group(1)):
                found.append(m.group(1))
    return _dedupe(found)


def _workshop_dirs():
    return _dedupe([
        os.path.join(lib, "steamapps", "workshop", "content", WORKSHOP_APP_ID)
        for lib in _library_paths()
        if os.path.isdir(os.path.join(lib, "steamapps", "workshop", "content",
                                      WORKSHOP_APP_ID))
    ])


def _template_dirs():
    return _dedupe([
        os.path.join(r, "controller_base", "templates") for r in _steam_roots()
        if os.path.isdir(os.path.join(r, "controller_base", "templates"))
    ])


def _safe_name(name):
    return "".join(c if c.isalnum() else "_" for c in name).strip("_").lower() or "profile"


def _installed_path(name):
    dirs = _template_dirs()
    if not dirs:
        return None
    return os.path.join(dirs[0], f"controller_padpilot_{_safe_name(name)}.vdf")


class Plugin:
    async def _main(self):
        pass

    async def _unload(self):
        pass

    async def list_profiles(self) -> dict:
        """Every subscribed .ccp profile, with what conversion would cost."""
        out = []
        for d in _workshop_dirs():
            for entry in sorted(os.listdir(d)):
                path = os.path.join(d, entry, "profile.ccp")
                if not os.path.isfile(path):
                    continue
                try:
                    profile = ccp.parse_file(path)
                    result = convert(profile)
                except Exception as exc:      # a bad profile must not kill the list
                    out.append({
                        "id": entry, "title": entry, "error": str(exc),
                        "bindings": 0, "dropped": [], "installed": False,
                    })
                    continue
                installed = _installed_path(profile.name)
                out.append({
                    "id": entry,
                    "title": profile.name,
                    "processes": profile.processes,
                    "bindings": len(profile.bindings),
                    "dropped": result.dropped,
                    "installed": bool(installed and os.path.exists(installed)),
                    "path": path,
                })
        return {"profiles": out, "workshop_dirs": _workshop_dirs(),
                "template_dirs": _template_dirs()}

    async def install_profile(self, path: str) -> dict:
        """Convert one profile and drop it into Steam's templates."""
        try:
            profile = ccp.parse_file(path)
            result = convert(profile)
        except Exception as exc:
            return {"ok": False, "error": f"could not convert: {exc}"}

        targets = _template_dirs()
        if not targets:
            return {"ok": False, "error": "no Steam templates directory found"}
        written = []
        for d in targets:
            dest = os.path.join(d, f"controller_padpilot_{_safe_name(profile.name)}.vdf")
            try:
                with open(dest, "w") as fh:
                    fh.write(result.vdf)
                written.append(dest)
            except OSError as exc:
                return {"ok": False, "error": f"writing {dest}: {exc}"}
        return {"ok": True, "written": written, "dropped": result.dropped,
                "title": profile.name}

    async def install_all(self) -> dict:
        listed = await self.list_profiles()
        done, failed = [], []
        for p in listed["profiles"]:
            if p.get("error"):
                failed.append(p["title"])
                continue
            r = await self.install_profile(p["path"])
            (done if r.get("ok") else failed).append(p["title"])
        return {"installed": done, "failed": failed}

    async def remove_profile(self, title: str) -> dict:
        removed = []
        for d in _template_dirs():
            path = os.path.join(d, f"controller_padpilot_{_safe_name(title)}.vdf")
            if os.path.exists(path):
                try:
                    os.remove(path)
                    removed.append(path)
                except OSError as exc:
                    return {"ok": False, "error": str(exc)}
        return {"ok": True, "removed": removed}

    async def status(self) -> dict:
        workshop = _workshop_dirs()
        templates = _template_dirs()
        count = sum(len([e for e in os.listdir(d)
                         if os.path.isfile(os.path.join(d, e, "profile.ccp"))])
                    for d in workshop)
        return {
            "workshop_dirs": workshop,
            "template_dirs": templates,
            "subscribed": count,
            "ready": bool(workshop and templates),
            "checked": time.strftime("%H:%M:%S"),
        }
