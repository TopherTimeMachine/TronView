# _onspeed_frame.py — OnSpeed `#4` display-serial frame codec (VENDORED).
#
# This file is a verbatim copy of `tools/onspeed_py/frame.py` from the
# OnSpeed-Gen3 firmware repo (flyonspeed/OnSpeed-Gen3, PR #1152 lineage).
# Do not hand-edit — refresh it wholesale from upstream when the wire
# format changes.  Upstream CI byte-parity-tests this module against the
# firmware's C++ encoder/decoder in both directions.
#
# Wire-format reference: https://dev.flyonspeed.org/reference/serial-protocol/
#
# The leading underscore keeps this file out of TronView's input-module
# listing (lib/inputs/*.py without a leading underscore are selectable
# inputs); `serial_onspeedaoa.py` imports from it.

"""OnSpeed `#4` display-serial wire-frame builder and parser.

Builds and parses the 86-byte ASCII frame (v4.25 size) that the
firmware emits at 40 Hz and that `onspeed_core::ParseDisplayFrame`
decodes on the M5 side. Single source of truth for the Python side of
the wire — `tools/m5-replay/replay.py` and `tools/synth-record/`
import `Frame` from here, and third-party consumers (e.g. TronView's
`serial_onspeedaoa` input) vendor `parse_frame` + `FrameAccumulator`.

The byte-for-byte contract lives in
`software/Libraries/onspeed_core/src/proto/DisplaySerial.h`. Tests in
`tools/onspeed_py/tests/` and `tools/m5-replay/test_replay.py`
(Layer 2 round-trip) verify the firmware's `ParseDisplayFrame` accepts
what `Frame.to_bytes()` emits; `test/test_host_main_cli/
test_frame_parity.py` verifies `parse_frame` accepts what the C++
`BuildDisplayFrame` emits.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Optional


# Wire-format constants. Mirror onspeed_core/proto/DisplaySerial.h
# (kDisplayFrameSizeBytes / kDisplayFrameChecksumLen).
PAYLOAD_LEN = 82   # bytes 0..81 — ASCII fields through decelKtPerSec
FRAME_LEN   = 86   # PAYLOAD_LEN + 2 hex CRC + CRLF
MAGIC = "#4"   # display-frame wire version; mirrors
               # onspeed_core/proto/DisplaySerial.h::kDisplayFrameMagic.
               # The C++<->Python parity test (test/test_host_main_cli)
               # fails CI if this drifts from the C++ constant.

# IAS-invalid wire sentinel.  Mirrors `kIasInvalidWireSentinel` in
# onspeed_core/proto/DisplaySerial.h: when the producer marks air-data
# invalid, the iasKt %04u field carries 9999.  The M5 parser detects
# this exact value, sets `iasIsValid=false` on the parsed frame, and
# renders dashes for both IAS and percentLift.  Picked as the maximum
# of the field width — far above any operational airspeed — so a
# consumer that ignores `iasIsValid` still sees an obviously bogus
# rather than a plausibly-low IAS reading.
IAS_INVALID_WIRE_SENTINEL = 9999


def _clamp_int(v: float, lo: int, hi: int) -> int:
    """C-style truncation-toward-zero + clamp, matching SafeScaledInt."""
    # ints are always finite; guarding the isfinite call keeps arbitrary-
    # precision Python ints (beyond float range) from raising OverflowError
    # on the float conversion inside math.isfinite.
    if not isinstance(v, int) and not math.isfinite(v):
        return 0
    # int() in Python truncates toward zero, matching C's (int)cast.
    i = int(v)
    if i < lo:
        return lo
    if i > hi:
        return hi
    return i


def _clamp_uint(v: float, lo: int, hi: int) -> int:
    if not isinstance(v, int) and not math.isfinite(v):
        return lo
    i = int(v)
    if i < lo:
        return lo
    if i > hi:
        return hi
    return i


@dataclass
class Frame:
    """All fields transmitted in one `#4` payload (decel ×100, issue #776).

    Field names and units mirror `DisplayBuildInputs` in
    `onspeed_core/proto/DisplaySerial.h`.

    Lateral G is BODY-FRAME (positive = airframe accelerating rightward),
    matching `DisplayBuildInputs::lateralG` — the canonical convention,
    shared with the SD log's `imuLateralG` and the WebSocket `lateralGLoad`.
    The wire carries body-frame; slip-skid ball renderers (the M5 and the
    LiveView slipBall) negate locally to draw ball-frame. The encoder below
    scales `lateral_g * 1000` with no sign flip.

    `percent_lift_pct` is in whole-percent units (0.0..99.9); the wire
    encoder scales ×10 and truncates to int for the v4.23 `%03u` field
    (range 0..999) — the wire still carries tenths-of-a-percent for
    sub-pixel temporal smoothness, but every consumer surfaces a float.
    The four band-edge percents (`tones_on_pct_lift`,
    `onspeed_fast_pct_lift`, etc.) stay at integer percent (0..99);
    they only move on detent or config-save events.

    `pip_pct_lift` (v4.22+) is the visual L/Dmax pip percent — separated
    from `tones_on_pct_lift` per PR #336.
    """

    pitch_deg:             float = 0.0
    roll_deg:              float = 0.0
    ias_kts:               float = 0.0
    # Air-data validity flag.  Mirrors `DisplayBuildInputs::iasValid` in
    # onspeed_core/proto/DisplaySerial.h.  When False, `to_bytes()`
    # writes the IAS_INVALID_WIRE_SENTINEL (9999) into the iasKt field
    # regardless of the `ias_kts` value, which the M5 parser uses to
    # flip `iasIsValid=false` and render dashes for IAS and percentLift.
    # Default True keeps live-mode and v2-log producers (all-numeric
    # IAS) emitting the live value unchanged.
    ias_valid:             bool  = True
    palt_ft:               float = 0.0
    turnrate_dps:          float = 0.0
    lateral_g:             float = 0.0
    vertical_g:            float = 1.0
    percent_lift_pct:      float = 0.0  # whole percent (0.0..99.9); v4.23 wire encoder scales ×10 to tenths
    vsi_fpm:               float = 0.0
    oat_c:                 int   = 15
    flightpath_deg:        float = 0.0
    flap_deg:              int   = 0
    tones_on_pct_lift:     int   = 0
    onspeed_fast_pct_lift: int   = 0
    onspeed_slow_pct_lift: int   = 0
    stall_warn_pct_lift:   int   = 0
    flaps_min_deg:         int   = 0
    flaps_max_deg:         int   = 0
    g_onset_rate:          float = 0.0
    spin_cue:              int   = 0
    data_mark:             int   = 0
    pip_pct_lift:          int   = 0   # v4.22+, visual L/Dmax pip
    sideslip_deg:          float = 0.0   # v4.25, body sideslip β (deg); lateral FPM input
    decel_kt_per_sec:      float = 0.0   # v4.25, IAS deceleration rate (kt/s)

    def to_bytes(self) -> bytes:
        """Serialize to the 86-byte wire frame (payload + CRC + CRLF, v4.25).

        Matches the printf format in
        `onspeed_core/proto/DisplaySerial.cpp::BuildDisplayFrame`.
        """
        # Wire contract: when `ias_valid` is False, write
        # IAS_INVALID_WIRE_SENTINEL (9999) into the iasKt %04u field.
        # The M5 parser detects this exact value and flips
        # `iasIsValid=false`, which the M5 firmware uses to render
        # dashes for IAS and percentLift.  See iasValid contract in
        # onspeed_core/proto/DisplaySerial.h.  Invalidity wins over
        # the live `ias_kts` value — a defensively-set NaN with
        # `ias_valid=True` still falls through `_clamp_uint`'s NaN
        # branch (returns the lower clamp 0), but the canonical caller
        # (live mode / v3 log replay) pairs NaN with `ias_valid=False`.
        ias10_field = (
            IAS_INVALID_WIRE_SENTINEL if not self.ias_valid
            else _clamp_uint(self.ias_kts * 10, 0, 9999)
        )
        payload = (
            MAGIC +
            f"{_clamp_int(self.pitch_deg * 10, -999, 999):+04d}"
            f"{_clamp_int(self.roll_deg * 10, -9999, 9999):+05d}"
            f"{ias10_field:04d}"
            f"{_clamp_int(self.palt_ft, -99999, 99999):+06d}"
            f"{_clamp_int(self.turnrate_dps * 10, -9999, 9999):+05d}"
            f"{_clamp_int(self.lateral_g * 1000, -999, 999):+04d}"
            f"{_clamp_int(self.vertical_g * 10, -99, 99):+03d}"
            f"{_clamp_uint(self.percent_lift_pct * 10.0, 0, 999):03d}"
            f"{_clamp_int(self.vsi_fpm / 10, -999, 999):+04d}"
            f"{_clamp_int(self.oat_c, -99, 99):+03d}"
            f"{_clamp_int(self.flightpath_deg * 10, -999, 999):+04d}"
            f"{_clamp_int(self.flap_deg, -99, 99):+03d}"
            f"{_clamp_uint(self.tones_on_pct_lift, 0, 99):02d}"
            f"{_clamp_uint(self.onspeed_fast_pct_lift, 0, 99):02d}"
            f"{_clamp_uint(self.onspeed_slow_pct_lift, 0, 99):02d}"
            f"{_clamp_uint(self.stall_warn_pct_lift, 0, 99):02d}"
            f"{_clamp_int(self.flaps_min_deg, -99, 99):+03d}"
            f"{_clamp_int(self.flaps_max_deg, -99, 99):+03d}"
            f"{_clamp_int(self.g_onset_rate * 100, -999, 999):+04d}"
            f"{_clamp_int(self.spin_cue, -9, 9):+02d}"
            # dataMark WRAPS mod 100 (the pilot's counter increments without
            # bound; the wire carries counter % 100).  Mirrors the C++
            # `static_cast<unsigned>(in.dataMark) % 100u` — the 32-bit mask
            # reproduces the unsigned cast over the full C++-representable
            # domain, negatives included.
            f"{(self.data_mark & 0xFFFFFFFF) % 100:02d}"
            f"{_clamp_uint(self.pip_pct_lift, 0, 99):02d}"
            f"{_clamp_int(self.sideslip_deg * 10, -999, 999):+04d}"
            f"{_clamp_int(self.decel_kt_per_sec * 100, -999, 999):+04d}"
        )
        if len(payload) != PAYLOAD_LEN:
            raise AssertionError(
                f"payload length {len(payload)} != {PAYLOAD_LEN}: {payload!r}"
            )
        crc = sum(payload.encode("ascii")) & 0xFF
        return f"{payload}{crc:02X}\r\n".encode("ascii")


# ---------------------------------------------------------------------------
# Parser — the inverse of Frame.to_bytes().
#
# Contract: accepts every frame `to_bytes()` (equivalently, per the CI
# byte-parity test, the firmware's C++ BuildDisplayFrame) can emit;
# returns None for everything else.  Deliberately STRICTER than the C++
# ParseDisplayFrame at the margins: the payload must match the producer's
# exact printf sign/width grammar (the C++ strtol-based field scan
# tolerates some space-padded / sign-flexible variants) and the CRLF
# terminator is required (the C++ one-shot parser never inspects it).
# Extra strictness cannot reject a genuine frame, since the producer
# grammar is exact.
# ---------------------------------------------------------------------------

# The producer's printf grammar, one named group per field, anchored to the
# full 82-byte payload.  Group order matches the wire field order in
# onspeed_core/proto/DisplaySerial.h.
_PAYLOAD_RE = re.compile(
    r"\A#4"
    r"(?P<pitch10>[+-]\d{3})"       # pitchDeg        %+04d ×10
    r"(?P<roll10>[+-]\d{4})"        # rollDeg         %+05d ×10
    r"(?P<ias10>\d{4})"             # iasKt           %04u  ×10 (9999 = invalid sentinel)
    r"(?P<palt>[+-]\d{5})"          # paltFt          %+06d ×1
    r"(?P<turnrate10>[+-]\d{4})"    # turnRateDps     %+05d ×10
    r"(?P<latg1000>[+-]\d{3})"      # lateralG        %+04d ×1000
    r"(?P<vertg10>[+-]\d{2})"       # verticalG       %+03d ×10
    r"(?P<pctlift10>\d{3})"         # percentLift     %03u  ×10 (tenths of a percent)
    r"(?P<vsi10>[+-]\d{3})"         # vsiFpm10        %+04d (already fpm/10)
    r"(?P<oat>[+-]\d{2})"           # oatC            %+03d ×1
    r"(?P<fpa10>[+-]\d{3})"         # flightPathDeg   %+04d ×10
    r"(?P<flaps>[+-]\d{2})"         # flapsDeg        %+03d ×1
    r"(?P<tones>\d{2})"             # tonesOnPctLift  %02u
    r"(?P<fast>\d{2})"              # onSpeedFastPctLift %02u
    r"(?P<slow>\d{2})"              # onSpeedSlowPctLift %02u
    r"(?P<warn>\d{2})"              # stallWarnPctLift   %02u
    r"(?P<flapsmin>[+-]\d{2})"      # flapsMinDeg     %+03d ×1
    r"(?P<flapsmax>[+-]\d{2})"      # flapsMaxDeg     %+03d ×1
    r"(?P<gonset100>[+-]\d{3})"     # gOnsetRate      %+04d ×100
    r"(?P<spin>[+-]\d)"             # spinRecoveryCue %+02d ×1
    r"(?P<datamark>\d{2})"          # dataMark        %02u
    r"(?P<pip>\d{2})"               # pipPctLift      %02u
    r"(?P<sideslip10>[+-]\d{3})"    # sideslipDeg     %+04d ×10
    r"(?P<decel100>[+-]\d{3})"      # decelKtPerSec   %+04d ×100
    r"\Z"
)


def parse_frame(data: bytes) -> Optional[Frame]:
    """Parse one `#4` wire frame; return None if it is not valid.

    Mirrors `onspeed_core::ParseDisplayFrame`: at least FRAME_LEN bytes
    (extra bytes beyond the first frame are ignored), `#4` magic, CRC over
    bytes 0..81 matching the two hex digits at 82..83 (lowercase accepted,
    as the C++ strtol does — the producer always emits uppercase), then
    CRLF.

    The returned `Frame` carries engineering units.  For the IAS-invalid
    wire sentinel (iasKt field == 9999), `ias_valid` is False and
    `ias_kts` keeps the raw decoded 999.9 — consumers must gate on
    `ias_valid`, not on the number (same contract as the C++
    `DisplayFrame::iasIsValid`).
    """
    if len(data) < FRAME_LEN:
        return None
    try:
        payload = data[:PAYLOAD_LEN].decode("ascii")
        crc_str = data[PAYLOAD_LEN:PAYLOAD_LEN + 2].decode("ascii")
    except UnicodeDecodeError:
        return None
    if data[PAYLOAD_LEN + 2:FRAME_LEN] != b"\r\n":
        return None
    if not re.fullmatch(r"[0-9A-Fa-f]{2}", crc_str):
        return None
    if int(crc_str, 16) != sum(data[:PAYLOAD_LEN]) & 0xFF:
        return None
    m = _PAYLOAD_RE.match(payload)
    if m is None:
        return None

    ias10 = int(m["ias10"])
    return Frame(
        pitch_deg=int(m["pitch10"]) / 10.0,
        roll_deg=int(m["roll10"]) / 10.0,
        ias_kts=ias10 / 10.0,
        ias_valid=(ias10 != IAS_INVALID_WIRE_SENTINEL),
        palt_ft=float(int(m["palt"])),
        turnrate_dps=int(m["turnrate10"]) / 10.0,
        lateral_g=int(m["latg1000"]) / 1000.0,
        vertical_g=int(m["vertg10"]) / 10.0,
        percent_lift_pct=int(m["pctlift10"]) / 10.0,
        vsi_fpm=int(m["vsi10"]) * 10.0,
        oat_c=int(m["oat"]),
        flightpath_deg=int(m["fpa10"]) / 10.0,
        flap_deg=int(m["flaps"]),
        tones_on_pct_lift=int(m["tones"]),
        onspeed_fast_pct_lift=int(m["fast"]),
        onspeed_slow_pct_lift=int(m["slow"]),
        stall_warn_pct_lift=int(m["warn"]),
        flaps_min_deg=int(m["flapsmin"]),
        flaps_max_deg=int(m["flapsmax"]),
        g_onset_rate=int(m["gonset100"]) / 100.0,
        spin_cue=int(m["spin"]),
        data_mark=int(m["datamark"]),
        pip_pct_lift=int(m["pip"]),
        sideslip_deg=int(m["sideslip10"]) / 10.0,
        decel_kt_per_sec=int(m["decel100"]) / 100.0,
    )


class FrameAccumulator:
    """Byte-stream framing for the `#4` wire.

    Mirrors `onspeed_core::DisplayFrameAccumulator::Inject` exactly:

      * Any '#' byte resets to start-of-frame (a genuine payload never
        contains '#', so this only fires on glitches / partial frames).
      * Bytes before the first '#' are ignored.
      * On the byte that fills FRAME_LEN, the frame parses only if that
        byte is LF; the buffer resets either way.

    At 40 Hz a consumer resynchronises within one frame (25 ms) of any
    line disturbance.
    """

    def __init__(self) -> None:
        self._buf = bytearray()

    def reset(self) -> None:
        self._buf.clear()

    @property
    def in_progress(self) -> bool:
        return len(self._buf) > 0

    def inject(self, byte: int) -> Optional[Frame]:
        """Feed one byte; return a Frame on the byte that completes a
        valid frame, else None."""
        if byte == 0x23:                    # '#'
            self._buf[:] = b"#"
            return None
        if not self._buf:
            return None
        self._buf.append(byte)
        if len(self._buf) < FRAME_LEN:
            return None
        buf = bytes(self._buf)
        self._buf.clear()
        if byte != 0x0A:                    # LF must complete the frame
            return None
        return parse_frame(buf)

    def feed(self, data: bytes) -> list[Frame]:
        """Feed a chunk of bytes; return every frame completed within it.

        Framing state carries across calls, so the stream may be
        delivered in arbitrary chunk sizes.  A drain-and-keep-latest
        consumer publishes `frames[-1]` when the list is non-empty.
        """
        frames = []
        for b in data:
            f = self.inject(b)
            if f is not None:
                frames.append(f)
        return frames
