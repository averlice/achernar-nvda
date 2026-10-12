"""NVDA speech synthesizer for the Achernar Piper voice.

A dedicated, single-voice driver: one bundled Piper model, spoken through the
bundled piper-helper.exe child process. There is no catalog, no download
manager, no language switching and no on-disk cache, so the voice NVDA loads
is always the voice that speaks.
"""

import os
import sys
import threading
from collections import OrderedDict

import addonHandler
import config
import nvwave
from autoSettingsUtils.driverSetting import (
    BooleanDriverSetting,
    NumericDriverSetting,
)
from logHandler import log
from synthDriverHandler import (
    SynthDriver as SynthDriverBase,
    VoiceInfo,
    synthDoneSpeaking,
    synthIndexReached,
)

from speech.commands import (
    BreakCommand,
    CharacterModeCommand,
    IndexCommand,
    LangChangeCommand,
    PhonemeCommand,
    PitchCommand,
    RateCommand,
    VolumeCommand,
)

from . import _audio, _helperProc, _paths
from . import _protocol as proto

addonHandler.initTranslation()

SAMPLE_RATE = 22050

_PITCH_SEMITONE_RANGE = 4.0
_VARIANCE_AT_MIN = 0.4
_VARIANCE_AT_MID = 1.0
_VARIANCE_AT_MAX = 1.6
_ADVANCED_MID = 50.0
_STRETCH_AT_MIN_RATE = 0.6
_STRETCH_AT_MID_RATE = 1.0
_STRETCH_AT_MAX_RATE = 2.0
_RATE_BOOST_MAX_EXTRA = 1.5


class SynthDriver(SynthDriverBase):
    name = "achernar"
    description = "Achernar"

    @classmethod
    def _base_settings(cls):
        return (
            SynthDriverBase.VoiceSetting(),
            SynthDriverBase.RateSetting(),
            SynthDriverBase.RateBoostSetting(),
            SynthDriverBase.PitchSetting(),
            SynthDriverBase.VolumeSetting(),
            BooleanDriverSetting(
                "advancedMode",
                _("Show &advanced voice parameters"),
                defaultVal=False,
            ),
        )

    @classmethod
    def _simple_settings(cls):
        return (
            NumericDriverSetting(
                "variance",
                _("&Expressiveness"),
                availableInSettingsRing=True,
                defaultVal=50,
                minStep=5,
            ),
        )

    @classmethod
    def _advanced_settings(cls):
        return (
            NumericDriverSetting(
                "noiseScale",
                _("&Noise scale (variability)"),
                availableInSettingsRing=True,
                defaultVal=50,
                minStep=5,
            ),
            NumericDriverSetting(
                "noiseW",
                _("Noise &W (phoneme length variation)"),
                availableInSettingsRing=True,
                defaultVal=50,
                minStep=5,
            ),
            NumericDriverSetting(
                "lengthScale",
                _("&Length scale (model pace)"),
                availableInSettingsRing=True,
                defaultVal=50,
                minStep=5,
            ),
        )

    def _get_supportedSettings(self):
        if getattr(self, "_advancedMode", False):
            return self._base_settings() + self._advanced_settings()
        return self._base_settings() + self._simple_settings()

    def getConfigSpec(self):
        return self._getConfigSpecForSettings(
            self._base_settings() + self._simple_settings()
            + self._advanced_settings())

    def _register_config_spec(self):
        try:
            section = config.conf["speech"][self.name]
        except KeyError:
            return
        try:
            section.spec.update(self.getConfigSpec())
        except Exception:
            log.exception("achernar: could not register the config spec early")

    supportedCommands = frozenset({
        IndexCommand,
        CharacterModeCommand,
        LangChangeCommand,
        BreakCommand,
        PhonemeCommand,
        PitchCommand,
        RateCommand,
        VolumeCommand,
    })
    supportedNotifications = frozenset({synthIndexReached, synthDoneSpeaking})

    @classmethod
    def check(cls):
        return os.path.isfile(_paths.HELPER_EXE)

    def __init__(self):
        super().__init__()
        self._register_config_spec()
        self._rate = 50
        self._pitch = 50
        self._volume = 90
        self._rateBoost = False
        self._variance = _clamp_percent(self._load_conf("variance", 50))
        self._advancedMode = bool(self._load_conf("advancedMode", False))
        self._noiseScale = _clamp_percent(self._load_conf("noiseScale", 50))
        self._noiseW = _clamp_percent(self._load_conf("noiseW", 50))
        self._lengthScale = _clamp_percent(self._load_conf("lengthScale", 50))
        self._voice = _paths.VOICE_KEY
        self._utterance_counter = 0
        self._cancelled_upto = 0
        self._lock = threading.Lock()

        _warn_if_unsupported_windows()
        self._player = _create_player()
        self._pump = _audio.AudioPump(self._player, self._on_index, self._on_done)
        self._helper = _helperProc.HelperProcess(
            _paths.HELPER_EXE, self._helper_args(),
            on_frame=self._on_frame, on_restart=self._on_helper_restart)
        self._helper.start()

    def _helper_args(self):
        return [
            "--espeak-dll", _paths.ESPEAK_DLL,
            "--espeak-data", _paths.ESPEAK_DATA,
        ]

    def terminate(self):
        try:
            self._helper.terminate()
        except Exception:
            pass
        try:
            self._pump.shutdown()
        except Exception:
            pass
        try:
            self._player.close()
        except Exception:
            pass
        super().terminate()

    def _on_frame(self, msg_type, payload):
        if msg_type in (proto.AUDIO, proto.MARKER, proto.DONE):
            if msg_type == proto.AUDIO:
                uid = proto.audio_utterance_id(payload)
            else:
                uid = proto.parse_json(payload).get("utteranceId")
            if uid is not None and uid <= self._cancelled_upto:
                return
            self._pump.handle_frame(msg_type, payload)
        elif msg_type == proto.ERROR:
            info = proto.parse_json(payload)
            log.warning("achernar helper error %s: %s"
                        % (info.get("code"), info.get("message")))
        elif msg_type == proto.LOG:
            info = proto.parse_json(payload)
            level = info.get("level", "info")
            getattr(log, level if hasattr(log, level) else "info")(
                "achernar helper: %s" % info.get("message"))

    def _on_helper_restart(self):
        pass

    def _on_index(self, index):
        synthIndexReached.notify(synth=self, index=index)

    def _on_done(self):
        synthDoneSpeaking.notify(synth=self)

    def speak(self, speechSequence):
        job = self._build_job(speechSequence)
        try:
            self._helper.send(proto.SPEAK, job)
        except Exception:
            log.exception("achernar: failed to send speak job")

    def _build_job(self, speechSequence):
        with self._lock:
            self._utterance_counter += 1
            uid = self._utterance_counter

        model = _paths.MODEL_PATH
        char_mode = False
        pitch = self._pitch
        rate = self._rate
        volume = self._volume
        segments = []
        pending_indexes = []
        pending_break = 0
        cur = None
        symbol_lang = None

        def new_segment():
            _speed, stretch = self._rate_to_stretch(rate)
            return {
                "text": "",
                "modelPath": model,
                "sid": 0,
                "stretch": stretch,
                "pitchSemis": self._pitch_to_semitones(pitch),
                "volume": max(0.0, min(1.0, volume / 100.0)),
                "breakMsBefore": 0,
                "indexesBefore": [],
                "charMode": char_mode,
                "scales": self._scales(),
                "ipa": False,
                "sentencePauseMs": 0,
            }

        def open_segment():
            nonlocal cur, pending_indexes, pending_break
            cur = new_segment()
            cur["indexesBefore"] = pending_indexes
            cur["breakMsBefore"] = pending_break
            pending_indexes = []
            pending_break = 0

        def close_segment():
            nonlocal cur
            if cur is None:
                return
            if cur["charMode"]:
                cur["text"] = _spoken_symbol(cur["text"], symbol_lang)
            keep = (cur["text"].strip() or cur["breakMsBefore"]
                    or cur["indexesBefore"]
                    or (cur["charMode"] and cur["text"]))
            if keep:
                segments.append(cur)
            cur = None

        for item in speechSequence:
            if isinstance(item, str):
                if cur is None:
                    open_segment()
                cur["text"] += item
            elif isinstance(item, IndexCommand):
                close_segment()
                pending_indexes.append(item.index)
            elif isinstance(item, CharacterModeCommand):
                close_segment()
                char_mode = item.state
            elif isinstance(item, PhonemeCommand):
                close_segment()
                if item.ipa:
                    open_segment()
                    cur["text"] = item.ipa
                    cur["ipa"] = True
                    cur["fallbackText"] = item.text or ""
                    close_segment()
                elif item.text:
                    open_segment()
                    cur["text"] = item.text
                    close_segment()
            elif isinstance(item, LangChangeCommand):
                close_segment()
                symbol_lang = item.lang or None
            elif isinstance(item, BreakCommand):
                close_segment()
                pending_break += int(item.time)
            elif isinstance(item, PitchCommand):
                close_segment()
                pitch = _clamp_percent(item.newValue)
            elif isinstance(item, RateCommand):
                close_segment()
                rate = _clamp_percent(item.newValue)
            elif isinstance(item, VolumeCommand):
                close_segment()
                volume = _clamp_percent(item.newValue)
        close_segment()

        if pending_indexes or pending_break:
            open_segment()
            close_segment()

        return {"utteranceId": uid, "segments": segments, "indexesAfter": []}

    def cancel(self):
        with self._lock:
            self._cancelled_upto = self._utterance_counter
        self._pump.cancel()
        try:
            self._helper.send(proto.CANCEL, {})
        except Exception:
            pass

    def pause(self, switch):
        self._pump.pause(switch)

    def _rate_to_stretch(self, rate):
        rate = _clamp_percent(rate)
        if rate <= 50:
            stretch = _STRETCH_AT_MIN_RATE + (rate / 50.0) * (
                _STRETCH_AT_MID_RATE - _STRETCH_AT_MIN_RATE)
        else:
            stretch = _STRETCH_AT_MID_RATE + ((rate - 50) / 50.0) * (
                _STRETCH_AT_MAX_RATE - _STRETCH_AT_MID_RATE)
        if self._rateBoost:
            stretch *= 1.0 + (rate / 100.0) * _RATE_BOOST_MAX_EXTRA
        return 1.0, round(stretch, 3)

    def _variance_factor(self):
        value = _clamp_percent(self._variance)
        if value <= 50:
            factor = _VARIANCE_AT_MIN + (value / 50.0) * (
                _VARIANCE_AT_MID - _VARIANCE_AT_MIN)
        else:
            factor = _VARIANCE_AT_MID + ((value - 50) / 50.0) * (
                _VARIANCE_AT_MAX - _VARIANCE_AT_MID)
        return round(factor, 2)

    def _scales(self):
        if self._advancedMode:
            return {
                "noiseScale": _advanced_factor(self._noiseScale),
                "noiseW": _advanced_factor(self._noiseW),
                "lengthScale": _advanced_factor(self._lengthScale),
            }
        variance = self._variance_factor()
        return {
            "noiseScale": variance,
            "noiseW": variance,
            "lengthScale": 1.0,
        }

    def _pitch_to_semitones(self, pitch):
        pitch = _clamp_percent(pitch)
        return round((pitch - 50) / 50.0 * _PITCH_SEMITONE_RANGE, 3)

    def _get_rate(self):
        return self._rate

    def _set_rate(self, v):
        self._rate = _clamp_percent(v)

    def _get_rateBoost(self):
        return self._rateBoost

    def _set_rateBoost(self, v):
        self._rateBoost = bool(v)

    def _get_pitch(self):
        return self._pitch

    def _set_pitch(self, v):
        self._pitch = _clamp_percent(v)

    def _get_volume(self):
        return self._volume

    def _set_volume(self, v):
        self._volume = _clamp_percent(v)

    def _get_voice(self):
        return self._voice

    def _set_voice(self, value):
        self._voice = _paths.VOICE_KEY

    def _getAvailableVoices(self):
        result = OrderedDict()
        result[_paths.VOICE_KEY] = VoiceInfo(
            _paths.VOICE_KEY, _paths.DISPLAY_NAME, _paths.LANGUAGE)
        return result

    def _get_variance(self):
        return self._variance

    def _set_variance(self, value):
        value = _clamp_percent(value)
        if value != self._variance:
            self._variance = value
            self._save_conf("variance", value)

    def _get_noiseScale(self):
        return self._noiseScale

    def _set_noiseScale(self, value):
        self._set_scale_setting("noiseScale", value)

    def _get_noiseW(self):
        return self._noiseW

    def _set_noiseW(self, value):
        self._set_scale_setting("noiseW", value)

    def _get_lengthScale(self):
        return self._lengthScale

    def _set_lengthScale(self, value):
        self._set_scale_setting("lengthScale", value)

    def _set_scale_setting(self, name, value):
        value = _clamp_percent(value)
        attr = "_" + name
        if value == getattr(self, attr):
            return
        setattr(self, attr, value)
        self._save_conf(name, value)

    def _get_advancedMode(self):
        return self._advancedMode

    def _set_advancedMode(self, value):
        value = bool(value)
        if value == self._advancedMode:
            return
        self._advancedMode = value
        self._save_conf("advancedMode", value)
        if not _refresh_settings_panel():
            _announce_settings_change()

    def _load_conf(self, key, default):
        try:
            return config.conf["speech"][self.name].get(key, default)
        except Exception:
            return default

    def _save_conf(self, key, value):
        try:
            config.conf["speech"][self.name][key] = value
        except Exception:
            pass


def _spoken_symbol(text, language=None):
    if len(text) != 1 or text.isalnum():
        return text
    try:
        import characterProcessing
        import languageHandler
        locale = language or languageHandler.getLanguage()
        replacement = characterProcessing.processSpeechSymbol(locale, text)
    except Exception:
        log.debugWarning("achernar: symbol name lookup failed", exc_info=True)
        return text
    return replacement if replacement else text


def _advanced_factor(percent):
    return round(_clamp_percent(percent) / _ADVANCED_MID, 2)


def _refresh_settings_panel():
    try:
        import wx
        from gui.settingsDialogs import NVDASettingsDialog
    except Exception:
        return False
    try:
        for window in wx.GetTopLevelWindows():
            if not isinstance(window, NVDASettingsDialog):
                continue
            panel = getattr(window, "currentCategory", None)
            for candidate in (getattr(panel, "voicePanel", None), panel):
                update = getattr(candidate, "updateDriverSettings", None)
                if update is not None:
                    update()
                    return True
    except Exception:
        log.debug("achernar: could not refresh the settings panel", exc_info=True)
    return False


def _announce_settings_change():
    try:
        import ui
        ui.message(
            _("Reopen Speech settings to see the changed parameters"))
    except Exception:
        pass


_MIN_WINDOWS_BUILD = 22000


def _warn_if_unsupported_windows():
    try:
        version = sys.getwindowsversion()
    except AttributeError:
        return
    if version.build < _MIN_WINDOWS_BUILD:
        log.warning(
            "achernar: Windows build %d is older than Windows 11, which is "
            "the supported minimum; this configuration is untested"
            % version.build)


def _clamp_percent(value):
    try:
        value = int(round(value))
    except (TypeError, ValueError):
        return 50
    return max(0, min(100, value))


def _create_player():
    kwargs = dict(channels=1, samplesPerSec=SAMPLE_RATE, bitsPerSample=16,
                  wantDucking=True)
    try:
        return nvwave.WavePlayer(purpose=nvwave.AudioPurpose.SPEECH, **kwargs)
    except (AttributeError, TypeError):
        pass
    try:
        outputDevice = config.conf["speech"]["outputDevice"]
        return nvwave.WavePlayer(outputDevice=outputDevice, **kwargs)
    except TypeError:
        return nvwave.WavePlayer(**kwargs)
