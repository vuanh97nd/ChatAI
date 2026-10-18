# Chat AI original interface cues

These PCM WAV files are synthesized by `mobile/tool/generate_sounds.py`, using sine chirps and short notes with smooth attack/decay envelopes. No audio samples from Apple or other products are used. Regenerate with:

    python mobile/tool/generate_sounds.py

The Android scaffold packages them as raw resources and preloads them into a single-stream SoundPool. Playback checks ringer mode, Do Not Disturb and active audio, and uses the user's effect-volume setting. Voice-capture cues finish before the microphone opens. Effects never need network access or a paid speech API.
