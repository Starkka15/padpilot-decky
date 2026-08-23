# PadPilot for Decky

Turn Controller Companion `.ccp` Workshop profiles into Steam Input configs,
without leaving Game Mode.

Subscribe to a profile on the Workshop on your Deck, open this plugin, press
Install, restart Steam — the profile is there under **Templates** in the
controller configuration screen. No desktop-mode trip.

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

Two things cannot, and the plugin says so per profile rather than dropping them
quietly:

- the `.ccp` **secondary layer** (bindings held behind the Back button) — Steam
  Input has no equivalent
- **program-launching** bindings (`cmd process`) — Steam Input cannot launch
  things

## Install

Download `PadPilot.zip` from Releases, unzip into
`~/homebrew/plugins/`, and restart Decky Loader.

## Development

    ./sync-core.sh              # re-vendor the conversion core from the PadPilot repo
    pnpm install && pnpm run build
    ./package.sh                # produces PadPilot.zip

The conversion core in `py_modules/padpilot_core/` is copied verbatim from
PadPilot, not reimplemented; `sync-core.sh` refreshes it.
