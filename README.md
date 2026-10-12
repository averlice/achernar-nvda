# Achernar for NVDA

A dedicated NVDA speech synthesizer for a single Piper voice, **Achernar**.
It runs fully offline: the voice model, the espeak-ng runtime, and the
synthesis engine all ship inside the add-on.

Unlike the general-purpose Piper add-ons, Achernar has **no voice catalog, no
downloads, no lexicon, and no automatic language switching**. It always speaks
with its one bundled voice, which removes the class of bug where a different
installed voice is loaded instead of the one selected.

## Requirements

- NVDA 2026.1 or later
- Windows 11, 64-bit

## Install

1. Download `achernar-1.0.0.nvda-addon` from the
   [latest release](https://github.com/averlice/achernar-nvda/releases/latest).
2. In NVDA, open **Tools → Add-on Store → Install from file…**, choose the
   downloaded file, and restart NVDA.
3. In **Speech settings**, select **Achernar** as the synthesizer.

## Settings

- **Rate**, **Rate boost**, **Pitch**, **Volume**: the usual NVDA controls.
- **Expressiveness**: how much the voice varies its delivery. 50 keeps the
  voice exactly as trained; lower is flatter and steadier, higher is more
  varied.
- **Show advanced voice parameters**: reveals Piper's own inference controls.
  Each is a percentage of the voice's trained value, where 50 is that value.
  - **Noise scale (variability)** — Piper's `noise_scale`
  - **Noise W (phoneme length variation)** — Piper's `noise_w`
  - **Length scale (model pace)** — Piper's `length_scale`

## Repository layout

The repository root *is* the add-on package, so it can be zipped directly into
a working `.nvda-addon`:

```
manifest.ini
doc/en/readme.html
synthDrivers/achernar/
  __init__.py            NVDA synthesizer driver
  _paths.py              bundled-file locations
  _protocol.py           driver <-> helper framing
  _helperProc.py         child-process management
  _audio.py              audio pump / index notifications
  bin/                   piper-helper.exe, CRT DLLs, espeak-ng runtime
  voices/                achernar.onnx + achernar.onnx.json
helper/                  Rust source for piper-helper.exe
  Cargo.toml, Cargo.lock
  src/                   inference, espeak-ng binding, protocol, DSP
  examples/
```

`synthDrivers/achernar/bin/piper-helper.exe` is built from `helper/` and is
committed prebuilt so the add-on works without a toolchain.

## Building the add-on package

Run the packaging script from the repository root:

```
python build_addon.py
```

It writes `dist/achernar-1.0.0.nvda-addon`.

The `helper/` directory is the Rust source of `piper-helper.exe`. Rebuilding it
requires a Rust toolchain and the espeak-ng runtime and ONNX Runtime assets; the
prebuilt binary already committed under `synthDrivers/achernar/bin/` is what the
add-on ships.

## Licence

GPL-2.0-or-later — see [LICENSE](LICENSE). This add-on is a derivative of
[Piper Neural Voices for NVDA](https://github.com/Community-Access/piper-nvda)
by Jeff Bishop; the original copyright notice is retained. Bundled third-party
components and their licences are listed in
[THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).
