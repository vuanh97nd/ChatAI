import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;
import 'package:url_launcher/url_launcher.dart';

const currentBuild = int.fromEnvironment('CHAT_AI_BUILD', defaultValue: 57);
const updateManifest = 'https://github.com/vuanh97nd/ChatAI/releases/download/android-latest/build-info.json';

class AppUpdate {
  final String version, url;
  final int build;
  AppUpdate(this.version, this.build, this.url);
  static AppUpdate parse(Map<String, dynamic> data, {String? expectedSigner}) {
    final build = int.tryParse('${data['build']}');
    final version = data['version'];
    final file = data['file'];
    if (build == null || build < 1 || version is! String || file is! String ||
        !RegExp(r'^ChatAI-[a-zA-Z0-9.+-]+\.apk$').hasMatch(file)) {
      throw const FormatException('Thông tin cập nhật không hợp lệ.');
    }
    final tag = data['release_tag'] ?? 'android-latest';
    if (tag is! String || !RegExp(r'^android-[a-zA-Z0-9.+-]+$').hasMatch(tag)) throw const FormatException('Kênh cập nhật không hợp lệ.');
    if (expectedSigner != null && data['signer_sha256'] != expectedSigner) {
      throw const FormatException('Bản phát hành có chữ ký khác. Giữ ứng dụng hiện tại để tránh mất dữ liệu.');
    }
    return AppUpdate(version, build,
      'https://github.com/vuanh97nd/ChatAI/releases/download/$tag/$file');
  }
}

Future<AppUpdate> checkAppUpdate({http.Client? client, String? signerSha256}) async {
  final transport = client ?? http.Client();
  try {
    if (signerSha256 != null && !RegExp(r'^[a-f0-9]{64}$').hasMatch(signerSha256)) throw const FormatException('Chữ ký ứng dụng không hợp lệ.');
    final manifest = signerSha256 == null ? updateManifest :
      'https://github.com/vuanh97nd/ChatAI/releases/download/android-signed-$signerSha256/build-info.json';
    final response = await transport.get(Uri.parse(manifest).replace(queryParameters: {'t': '${DateTime.now().millisecondsSinceEpoch}'}),
      headers: {'Cache-Control': 'no-cache'}).timeout(const Duration(seconds: 15));
    if (response.statusCode == 404) throw Exception('Chưa có bản cập nhật cùng chữ ký được công bố. Giữ ứng dụng hiện tại; không cần gỡ cài đặt.');
    if (response.statusCode != 200) throw Exception('Không kiểm tra được cập nhật (${response.statusCode}).');
    return AppUpdate.parse(jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>, expectedSigner: signerSha256);
  } finally { if (client == null) transport.close(); }
}

class UpdatePage extends StatefulWidget {
  const UpdatePage({super.key});
  @override
  State<UpdatePage> createState() => _UpdatePageState();
}
class _UpdatePageState extends State<UpdatePage> {
  bool checking = false;
  AppUpdate? update;
  String? message;
  @override
  void initState() { super.initState(); check(); }
  Future<void> check() async {
    setState(() { checking = true; message = null; });
    try {
      final signer = await const MethodChannel('vn.chatai/app_identity').invokeMethod<String>('signerSha256');
      if (signer == null) throw Exception('Chưa xác minh được chữ ký ứng dụng. Hãy thử lại.');
      final result = await checkAppUpdate(signerSha256: signer);
      if (!mounted) return;
      setState(() { update = result; message = result.build > currentBuild
        ? 'Có bản mới: ${result.version} · build ${result.build}' : 'Chưa có bản phát hành mới hơn bản đang dùng.'; });
    } catch (e) { if (mounted) setState(() => message = '$e'); }
    finally { if (mounted) setState(() => checking = false); }
  }
  Future<void> download() async {
    try {
      if (!await launchUrl(Uri.parse(update!.url), mode: LaunchMode.externalApplication)) {
        throw Exception('Không mở được trình duyệt tải APK.');
      }
    } catch (e) { if (mounted) setState(() => message = '$e'); }
  }
  @override
  Widget build(BuildContext context) => Scaffold(appBar: AppBar(title: const Text('Cập nhật ứng dụng')),
    body: ListView(padding: const EdgeInsets.all(24), children: [
      Text('Bản đang dùng: build $currentBuild'), const SizedBox(height: 16),
      if (checking) const LinearProgressIndicator(),
      if (message != null) Padding(padding: const EdgeInsets.symmetric(vertical: 16), child: Text(message!)),
      if (!checking && update != null && update!.build > currentBuild)
        FilledButton.icon(onPressed: download, icon: const Icon(Icons.download), label: const Text('Tải bản mới')),
      TextButton(onPressed: checking ? null : check, child: const Text('Kiểm tra lại')),
      const Text('APK mở trong trình duyệt. Sau khi tải xong, mở file và xác nhận Cài đặt trên Android. Giữ ứng dụng hiện tại để cập nhật và giữ dữ liệu.'),
    ]));
}
