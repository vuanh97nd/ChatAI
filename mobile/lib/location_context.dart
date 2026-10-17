import 'package:flutter/foundation.dart';
import 'package:geolocator/geolocator.dart';

class NearbyPosition {
  final double latitude, longitude;
  const NearbyPosition(this.latitude, this.longitude);
  Map<String, double> toJson() => {'latitude': latitude, 'longitude': longitude};
}

final locationForQuestions = ValueNotifier<bool>(true);

/// Foreground, one-shot position only. No location history or background stream.
Future<NearbyPosition?> questionPosition() async {
  if (!locationForQuestions.value) return null;
  try {
    if (!await Geolocator.isLocationServiceEnabled()) return null;
    var permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) permission = await Geolocator.requestPermission();
    if (permission != LocationPermission.whileInUse && permission != LocationPermission.always) return null;
    final position = await Geolocator.getCurrentPosition(locationSettings: const LocationSettings(
      accuracy: LocationAccuracy.low, timeLimit: Duration(seconds: 12)));
    return NearbyPosition(double.parse(position.latitude.toStringAsFixed(3)), double.parse(position.longitude.toStringAsFixed(3)));
  } catch (_) { return null; }
}
