import 'dart:typed_data';
import 'live_search.dart' show foldVietnamese;

bool hasSpeechEnergy(Uint8List pcm) {
  final data=ByteData.sublistView(pcm);
  var activeFrames=0;
  // Require 250ms of audible PCM, rather than one microphone click.
  for(var offset=0;offset+640<=pcm.length;offset+=640) {
    var energy=0.0;
    for(var i=offset;i<offset+640;i+=2) { final sample=data.getInt16(i,Endian.little)/32768; energy+=sample*sample; }
    if(energy/320>0.00001225) activeFrames++;
  }
  return activeFrames>=13;
}

String cleanRecognizedSpeech(String text) {
  var result=text.trim();
  final folded=foldVietnamese(result);
  // A recurring Whisper training-caption hallucination, not ordinary mentions
  // of the channel name. Do not strip arbitrary words from actual questions.
  final caption=RegExp(r'(?:cac ban\s+)?(?:hay\s+|dung quen\s+)?dang k[yi]\s+(?:cho\s+)?kenh\s+la\s*la\s*school\s+de\s+khong\s+bo\s+lo\s+nhung\s+video\s+hap\s+dan[.!?]*',caseSensitive:false);
  for(final match in caption.allMatches(folded).toList().reversed) {
    result=result.replaceRange(match.start,match.end,' ');
  }
  result=result.replaceAll(RegExp(r'\s+'),' ').trim();
  if(RegExp(r'^la\s*la\s*school[.!?]*$').hasMatch(foldVietnamese(result)))return '';
  return result;
}
