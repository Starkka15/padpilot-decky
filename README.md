# PadPilot for Decky

Turn Controller Companion `.ccp` Workshop profiles into Steam Input configs,
without leaving Game Mode.

Subscribe to a profile on the Workshop on your Deck, open this plugin, press
Install, restart Steam — the profile is there under **Templates** in the
controller configuration screen. No desktop-mode trip.

## Status

Working: listing subscribed profiles, converting them, and installing them as
Steam Input templates (one per controller type, since Steam lists a template
only for the type it declares).

Still being worked out: the `.ccp` **secondary layer**. It is converted into a
Steam action layer held with the View button, but the behaviour is not right on
hardware yet. Everything else in a profile converts.

## Why convert instead of remapping

[PadPilot](https://github.com/Starkka15/padpilot-linux) has its own remapper for
desktop Linux, but on a Deck that would be fighting Steam Input, which already
owns the controller and remaps per game. Steam's gap is that it cannot read
Controller Companion profiles. So this plugin translates them and hands them to
Steam, rather than running a second remapper.

That also keeps it cheap: the conversion is pure Python stdlib, so the plugin
needs no binary wheels, no root, and no `/dev/uinput`.

## What converts

Buttons, d-pad, triggers, shoulders, sticks-as-WASD, mouse movement, mouse
buttons and the scroll wheel.

Chords, the on-screen keyboard and Steam's own actions (Big Picture, controller
power off) convert too. What cannot is listed per profile in the UI rather than
dropped quietly — in practice that is Windows-only commands such as
`displayswitch.exe`.

## Install

No release yet — build it:

    ./sync-core.sh && pnpm install && pnpm run build && ./package.sh

then copy `PadPilot.zip` to the device, unzip into `~/homebrew/plugins/` and
restart Decky Loader:

    sudo unzip -o PadPilot.zip -d ~/homebrew/plugins/
    sudo systemctl restart plugin_loader

## Development

    ./sync-core.sh              # re-vendor the conversion core from the PadPilot repo
    pnpm install && pnpm run build
    ./package.sh                # produces PadPilot.zip

The conversion core in `py_modules/padpilot_core/` is copied verbatim from
PadPilot, not reimplemented; `sync-core.sh` refreshes it.
