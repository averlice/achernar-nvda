# Third-party components, licences, and credits

This add-on bundles or links the components below. The licences impose
obligations, notably espeak-ng's GPL v3.

## Bundled in the add-on package

| Component | Role | Licence | Source |
|-----------|------|---------|--------|
| espeak-ng | Text to phonemes, loaded by the helper as `libespeak-ng.dll` | GPL-3.0-or-later | https://github.com/espeak-ng/espeak-ng |
| ONNX Runtime | Neural network inference, statically linked into `piper-helper.exe` | MIT | https://github.com/microsoft/onnxruntime |
| Visual C++ runtime | `msvcp140.dll`, `msvcp140_1.dll`, `vcruntime140.dll`, `vcruntime140_1.dll`, which the helper and espeak-ng link against | Microsoft redistributable | Redistributed under the Visual Studio distributable-code terms. Shipping them beside the executable means users need no separate redistributable install. |
| Achernar voice | `voices/achernar.onnx` and its config | See the voice's MODEL_CARD | Custom Piper voice |

Because espeak-ng is GPL v3 and is loaded by the helper, `piper-helper.exe` is
distributed under GPL-v3-compatible terms.

### Rust crates linked into the helper

| Crate | Role | Licence |
|-------|------|---------|
| [`ort`](https://crates.io/crates/ort) | ONNX Runtime bindings, and the source of the bundled runtime binary | MIT OR Apache-2.0 |
| [`anyhow`](https://crates.io/crates/anyhow) | Error handling | MIT OR Apache-2.0 |
| [`serde`](https://crates.io/crates/serde), [`serde_json`](https://crates.io/crates/serde_json) | Protocol and voice-config JSON | MIT OR Apache-2.0 |
| [`libloading`](https://crates.io/crates/libloading) | Loading `libespeak-ng.dll` at runtime | ISC |

## Credits

- **[Piper Neural Voices for NVDA](https://github.com/Community-Access/piper-nvda)**
  (GPL-2.0-or-later) by Jeff Bishop: the NVDA-side driver code in this add-on
  is adapted from that project. This add-on is a derivative work and retains
  the original copyright notice.
- **[Piper](https://github.com/rhasspy/piper)** (MIT) by Michael Hansen and
  contributors: the voice models and the phoneme-id conventions the inference
  code follows. This project is not affiliated with the Piper project.
- **[espeak-ng](https://github.com/espeak-ng/espeak-ng)**: phonemization.
- **[NV Access](https://www.nvaccess.org/)** (NVDA is GPL-2.0): NVDA and its
  synthesizer driver API, which this add-on is written against.

## This add-on's own code

Licensed GPL-2.0-or-later (see [LICENSE](LICENSE)), the conventional licence
for NVDA add-ons. The NVDA-side Python code contains no third-party code
beyond the Python standard library and NVDA's own API.
