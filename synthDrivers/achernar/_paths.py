"""Filesystem locations for the Achernar synthesizer add-on.

The helper binary, the espeak-ng runtime and the single Achernar voice model
all ship inside the add-on.
"""

import os

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))

BIN_DIR = os.path.join(_THIS_DIR, "bin")
HELPER_EXE = os.path.join(BIN_DIR, "piper-helper.exe")
ESPEAK_DLL = os.path.join(BIN_DIR, "espeak-ng", "libespeak-ng.dll")
ESPEAK_DATA = os.path.join(BIN_DIR, "espeak-ng")

VOICES_DIR = os.path.join(_THIS_DIR, "voices")
VOICE_KEY = "achernar"
MODEL_PATH = os.path.join(VOICES_DIR, VOICE_KEY + ".onnx")
CONFIG_PATH = os.path.join(VOICES_DIR, VOICE_KEY + ".onnx.json")

DISPLAY_NAME = "Achernar"
LANGUAGE = "en_US"
