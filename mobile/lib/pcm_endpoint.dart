import 'dart:typed_data';

/// Endpointing from PCM frames, independent of Android's amplitude callbacks.
class PcmEndpoint {
  final List<int> _pending = [];
  int frames = 0, voiced = 0, lastVoice = 0;
  bool get heardSpeech => voiced >= 3;
  bool add(Uint8List bytes) {
    _pending.addAll(bytes);
    var offset = 0;
    while (offset + 640 <= _pending.length) {
      double energy = 0;
      for (var i = offset; i < offset + 640; i += 2) {
        var sample = _pending[i] | (_pending[i + 1] << 8);
        if (sample >= 32768) sample -= 65536;
        energy += (sample / 32768) * (sample / 32768);
      }
      frames++;
      if (energy / 320 > .00001225) { voiced++; lastVoice = frames; }
      offset += 640;
    }
    if (offset > 0) _pending.removeRange(0, offset);
    return heardSpeech && frames - lastVoice >= 40;
  }
}
