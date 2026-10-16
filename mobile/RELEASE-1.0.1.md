# Android 1.0.1 (50)

- Weather/news questions explicitly fetch online data before asking the model to answer.
- Weather without a location asks for the city; a city reply continues the question.
- Sources and data timestamps accompany current-information answers. Failed search
  never becomes an unsupported claim of live weather or news.
- Worker update adds Open-Meteo geocoding/current conditions/three-day forecast;
  older Workers continue to accept the same search request using Bing snippets.
- Microphone PCM must contain at least 250ms of audible energy before transcription.
  This is an energy gate, not a guarantee of speech/noise classification.
- Known Lalaschool advertising captions are removed from recognizer output; normal
  questions mentioning the channel remain intact. No automatic question from an
  empty/filtered transcript.
- Keeps parallel direct billing and primary-only online AI routing.

Build via `.github/workflows/android-apk.yml`, pinned Flutter 3.35.7. Reuses the
existing test signing identity so the artifact can update previous test APKs.
A Worker code deployment is required for structured Open-Meteo results and the
server-side silence guard. The client-side intent and transcript fixes work with
older deployed Workers. No billing migration or wallet reset is required.
