"""Karaoke-style narration subtitles (Reise-Insider format).

Transcribes the voice-over with faster-whisper (word timestamps), groups
words into short phrases, and writes an ASS subtitle file:
  - bold sans-serif, UPPERCASE, bottom center
  - white text, no background box, soft shadow
  - the word currently being spoken is highlighted yellow
"""
from pathlib import Path

PLAY_W, PLAY_H = 1920, 1080
MAX_WORDS = 5          # words per phrase on screen
MAX_GAP = 0.8          # seconds of silence that force a phrase break
PHRASE_END_CHARS = ".!?,;:"

ASS_HEADER = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {PLAY_W}
PlayResY: {PLAY_H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Karaoke,DejaVu Sans,62,&H00FFFFFF,&H00FFFFFF,&H00101010,&H96000000,-1,0,0,0,100,100,1,0,1,2.5,2,2,60,60,95,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

YELLOW = r"{\c&H00E5FF&}"   # BGR: slightly warm yellow
WHITE = r"{\c&HFFFFFF&}"


def _ts(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int(seconds % 3600 // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def transcribe_words(audio: Path, model_size: str = "base.en", log=print):
    """Return [(word, start, end), ...] for the narration audio."""
    from faster_whisper import WhisperModel
    log(f"  loading whisper model '{model_size}' ...")
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, info = model.transcribe(str(audio), language="en",
                                      word_timestamps=True, vad_filter=True)
    words = []
    for seg in segments:
        for w in seg.words or []:
            token = w.word.strip()
            if token:
                words.append((token, w.start, w.end))
    log(f"  transcribed {len(words)} words "
        f"({info.duration:.0f}s audio)")
    return words


def group_phrases(words):
    """Split the word stream into short display phrases."""
    phrases, current = [], []
    for i, (token, start, end) in enumerate(words):
        current.append((token, start, end))
        gap_next = (words[i + 1][1] - end) if i + 1 < len(words) else 99
        if (len(current) >= MAX_WORDS
                or token[-1] in PHRASE_END_CHARS
                or gap_next > MAX_GAP):
            phrases.append(current)
            current = []
    if current:
        phrases.append(current)
    return phrases


def build_ass(words, out_path: Path):
    """One Dialogue event per word: full phrase shown, current word yellow."""
    lines = [ASS_HEADER]
    for phrase in group_phrases(words):
        for j, (token, start, end) in enumerate(phrase):
            # keep the phrase on screen until the next word starts
            until = phrase[j + 1][1] if j + 1 < len(phrase) else end
            text = " ".join(
                (YELLOW + w.upper() + WHITE) if k == j else w.upper()
                for k, (w, _, _) in enumerate(phrase)
            )
            # strip punctuation-only flicker: minimum display time
            if until - start < 0.02:
                until = start + 0.02
            lines.append(
                f"Dialogue: 0,{_ts(start)},{_ts(until)},Karaoke,,0,0,0,,{text}"
            )
    out_path.write_text("".join(l if l.endswith("\n") else l + "\n"
                                for l in lines), encoding="utf-8")
    return out_path


def load_timings(path: Path):
    """Word timings supplied by the user's TTS tool:
    [{"word": ..., "start": ..., "end": ...}, ...]"""
    import json
    data = json.loads(Path(path).read_text())
    return [(d["word"].strip(), float(d["start"]), float(d["end"]))
            for d in data if d.get("word", "").strip()]


def make_subtitles(audio: Path, out_path: Path,
                   model_size: str = "base.en",
                   timings: Path | None = None, log=print) -> Path | None:
    if timings:
        words = load_timings(timings)
        log(f"  using {len(words)} provided word timings from {timings}")
    else:
        words = transcribe_words(audio, model_size, log=log)
    if not words:
        log("  WARNING: no speech detected, skipping subtitles")
        return None
    return build_ass(words, out_path)
