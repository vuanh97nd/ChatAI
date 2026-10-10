import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:url_launcher/url_launcher.dart';

const currentBuild = int.fromEnvironment('CHAT_AI_BUILD', defaultValue: 25);
const updateManifest = 'https://github.com/vuanh97nd/ChatAI/releases/download/android-latest/build-info.json';

class AppUpdate {
  final String version, url;
  final int build;
  AppUpdate(this.version, this.build, this.url);
  static AppUpdate parse(Map<String, dynamic> data) {
    final build = int.tryParse('${data['build']}');
    final version = data['version'];
    final file = data['file'];
    if (build == null || build < 1 || version is! String || file is! String ||
        !RegExp(r'^ChatAI-[a-zA-Z0-9.+-]+\.apk$').hasMatch(file)) {
      throw const FormatException('Thông tin cập nhật không hợp lệ.');
    }
    return AppUpdate(version, build,
      'https://github.com/vuanh97nd/ChatAI/releases/download/android-latest/$file');
  }
}

Future<AppUpdate> checkAppUpdate({http.Client? client}) async {
  final transport = client ?? http.Client();
  try {
    final response = await transport.get(Uri.parse(updateManifest),
      headers: {'Cache-Control': 'no-cache'}).timeout(const Duration(seconds: 15));
    if (response.statusCode == 404) throw Exception('Chưa có APK được phát hành. Vui lòng thử lại sau.');
    if (response.statusCode != 200) throw Exception('Không kiểm tra được cập nhật (${response.statusCode}).');
    return AppUpdate.parse(jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>);
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
      final result = await checkAppUpdate();
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
