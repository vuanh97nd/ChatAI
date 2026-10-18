import 'ios_settings.dart';
import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'plaxis_agent_api.dart';
import 'math_markdown.dart';
import 'package:flutter_markdown/flutter_markdown.dart';

class PlaxisAgentPage extends StatefulWidget {
  final String storageKey;
  final PlaxisAgentApi Function(String, String)? clientFactory;
  const PlaxisAgentPage({
    super.key,
    required this.storageKey,
    this.clientFactory,
  });
  @override
  State<PlaxisAgentPage> createState() => _PlaxisAgentPageState();
}

class _PlaxisAgentPageState extends State<PlaxisAgentPage>
    with WidgetsBindingObserver {
  static const vault = FlutterSecureStorage();
  final address = TextEditingController(), token = TextEditingController();
  final project = TextEditingController(text: 'project-1'),
      prompt = TextEditingController();
  final metric = TextEditingController(),
      target = TextEditingController(),
      unit = TextEditingController();
  PlaxisAgentApi? api;
  String version = '2d', comparison = 'le';
  String? jobId, error;
  Map<String, dynamic>? job;
  bool busy = false, active = true, ready = false, uncertain = false;
  Timer? timer;
  String get key => 'plaxis-agent:${widget.storageKey}';
  bool get running =>
      jobId != null &&
      !['finished', 'failed', 'stopped'].contains(job?['status']);

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    restore();
  }

  void changed(VoidCallback fn) {
    if (mounted) setState(fn);
  }

  Future<void> restore() async {
    try {
      final raw = await vault.read(key: key);
      if (raw != null && mounted) {
        final saved = jsonDecode(raw) as Map<String, dynamic>;
        changed(() {
          address.text = saved['address'] as String? ?? '';
          token.text = saved['token'] as String? ?? '';
          project.text = saved['project'] as String? ?? 'project-1';
          jobId = saved['job_id'] as String?;
          uncertain = saved['uncertain'] == true;
          version = saved['version'] == '3d' ? '3d' : '2d';
        });
      }
    } catch (_) {
      changed(() => error = 'Chưa đọc được cấu hình kết nối đã lưu.');
    }
  }

  Future<void> save() => vault.write(
    key: key,
    value: jsonEncode({
      'address': address.text.trim(),
      'token': token.text.trim(),
      'project': project.text.trim(),
      'version': version,
      'job_id': jobId,
      'uncertain': uncertain,
    }),
  );
  Future<void> action(Future<void> Function() operation) async {
    if (busy) return;
    changed(() {
      busy = true;
      error = null;
    });
    try {
      await operation();
    } catch (e) {
      changed(() => error = '$e');
    } finally {
      changed(() => busy = false);
      schedule();
    }
  }

  Future<void> connect() => action(() async {
    final next =
        widget.clientFactory?.call(address.text, token.text.trim()) ??
        PlaxisAgentApi(address.text, token.text.trim());
    try {
      final health = await next.connect();
      if (health['ok'] != true) throw StateError('Agent chưa sẵn sàng.');
      if (!mounted) {
        next.close();
        return;
      }
      api?.close();
      api = next;
      changed(() => ready = true);
      await save();
      if (jobId != null) await readJob();
    } catch (_) {
      if (api != next) next.close();
      rethrow;
    }
  });
  Future<void> readJob() async {
    if (api == null || jobId == null) return;
    final result = await api!.inspect(jobId!);
    changed(() => job = result);
  }

  void schedule() {
    timer?.cancel();
    if (mounted && active && ready && running) {
      timer = Timer(
        Duration(seconds: error == null ? 2 : 15),
        () => action(readJob),
      );
    }
  }

  Future<void> send() => action(() async {
    if (api == null || running || uncertain) return;
    if (prompt.text.trim().isEmpty ||
        !RegExp(r'^[\w.-]{1,80}$').hasMatch(project.text.trim())) {
      throw ArgumentError(
        'Nhập yêu cầu và mã dự án gồm chữ, số, dấu gạch hoặc dấu chấm.',
      );
    }
    final criteria = <Map<String, dynamic>>[];
    if ([metric.text, target.text, unit.text].any((v) => v.trim().isNotEmpty)) {
      final value = double.tryParse(target.text.trim());
      if (!RegExp(
            r'^[A-Za-z][A-Za-z0-9_]{0,79}$',
          ).hasMatch(metric.text.trim()) ||
          value == null ||
          !value.isFinite ||
          unit.text.trim().isEmpty) {
        throw ArgumentError('Nhập đủ chỉ tiêu, giới hạn hữu hạn và đơn vị.');
      }
      criteria.add({
        'metric': metric.text.trim(),
        'operator': comparison,
        'target': value,
        'unit': unit.text.trim(),
      });
    }
    // Persist before POST: process death/timeout must never silently replay a write.
    changed(() => uncertain = true);
    await save();
    final result = await api!.submit(
      prompt.text.trim(),
      version,
      project.text.trim(),
      criteria: criteria,
    );
    final id = result['id'];
    if (id is! String || id.isEmpty)
      throw StateError('Agent chưa trả mã tác vụ.');
    changed(() {
      jobId = id;
      uncertain = false;
      job = {'status': result['status']};
    });
    await save();
    await readJob();
  });
  Future<void> stop() => action(() async {
    if (api == null || jobId == null) return;
    await api!.stop(jobId!);
    await readJob();
  });
  Future<void> clearUncertain() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => IosAlertDialog(
        title: const Text('Kiểm tra công việc trên PC'),
        content: const Text(
          'Yêu cầu trước có thể đã chạy. Chỉ mở gửi việc lại sau khi đã kiểm tra PC để tránh chạy trùng.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Giữ nguyên'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Đã kiểm tra PC'),
          ),
        ],
      ),
    );
    if (confirmed == true) {
      changed(() {
        uncertain = false;
        jobId = null;
        job = null;
      });
      await save();
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    active = state == AppLifecycleState.resumed;
    if (!active) {
      timer?.cancel();
    } else {
      schedule();
    }
  }

  @override
  void dispose() {
    timer?.cancel();
    WidgetsBinding.instance.removeObserver(this);
    api?.close();
    for (final field in [
      address,
      token,
      project,
      prompt,
      metric,
      target,
      unit,
    ]) {
      field.dispose();
    }
    super.dispose();
  }

  String statusName(dynamic status) =>
      const {
        'queued': 'Đang chờ PC',
        'running': 'AI đang thực hiện',
        'stopping': 'Đang chờ dừng',
        'stopped': 'Đã dừng',
        'finished': 'Agent đã kết thúc',
        'failed': 'Chưa đạt hoặc có lỗi',
      }[status] ??
      '$status';
  @override
  Widget build(BuildContext context) {
    final result = job?['result'] as Map<String, dynamic>?;
    final events = job?['events'] as List<dynamic>? ?? [];
    final review = result?['criteria_review'] as Map<String, dynamic>?;
    return Scaffold(
      appBar: AppBar(title: const Text('Agent PLAXIS trên PC')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          const Text(
            'Dùng agent Ollama/LangGraph, bộ nhớ dự án và tài liệu RAG trên PC. PC cần bật dịch vụ agent và kết nối HTTPS.',
          ),
          TextField(
            controller: address,
            onChanged: (_) => changed(() => ready = false),
            enabled: !busy && !running,
            keyboardType: TextInputType.url,
            decoration: const InputDecoration(
              labelText: 'Địa chỉ HTTPS của agent PC',
            ),
          ),
          TextField(
            controller: token,
            onChanged: (_) => changed(() => ready = false),
            enabled: !busy && !running,
            obscureText: true,
            autocorrect: false,
            enableSuggestions: false,
            decoration: const InputDecoration(labelText: 'Mã kết nối agent'),
          ),
          FilledButton(
            onPressed: busy || running && ready ? null : connect,
            child: const Text('Kết nối agent'),
          ),
          if (ready)
            const Text('Đã kết nối dịch vụ. Chưa xác minh kết nối PLAXIS.'),
          if (busy) const LinearProgressIndicator(),
          if (error != null)
            Text(
              error!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          if (uncertain) ...[
            const Text(
              'Yêu cầu trước chưa rõ đã được nhận hay chưa. Không tự gửi lại.',
            ),
            TextButton(
              onPressed: busy ? null : clearUncertain,
              child: const Text('Đã kiểm tra tác vụ trên PC'),
            ),
          ],
          const SizedBox(height: 16),
          TextField(
            controller: project,
            enabled: !busy && !running,
            decoration: const InputDecoration(
              labelText: 'Mã dự án để lưu bộ nhớ',
            ),
          ),
          DropdownButtonFormField<String>(
            key: ValueKey(version),
            initialValue: version,
            decoration: const InputDecoration(labelText: 'Sản phẩm PLAXIS'),
            items: const [
              DropdownMenuItem(value: '2d', child: Text('PLAXIS 2D')),
              DropdownMenuItem(value: '3d', child: Text('PLAXIS 3D')),
            ],
            onChanged: busy || running
                ? null
                : (v) => changed(() => version = v!),
          ),
          TextField(
            controller: prompt,
            minLines: 3,
            maxLines: 8,
            maxLength: 12000,
            enabled: !busy && !running,
            decoration: const InputDecoration(
              labelText: 'Giao việc cho agent',
              hintText: 'Nêu dữ liệu, nguồn và kết quả cần kiểm tra',
            ),
          ),
          ExpansionTile(
            title: const Text('Tiêu chí số liệu (tùy chọn)'),
            children: [
              TextField(
                controller: metric,
                decoration: const InputDecoration(
                  labelText: 'Chỉ tiêu, ví dụ S_m',
                ),
              ),
              DropdownButtonFormField<String>(
                initialValue: comparison,
                items: const [
                  DropdownMenuItem(value: 'le', child: Text('Không vượt quá')),
                  DropdownMenuItem(value: 'ge', child: Text('Không nhỏ hơn')),
                ],
                onChanged: (v) => changed(() => comparison = v!),
              ),
              TextField(
                controller: target,
                keyboardType: const TextInputType.numberWithOptions(
                  decimal: true,
                  signed: true,
                ),
                decoration: const InputDecoration(labelText: 'Giới hạn'),
              ),
              TextField(
                controller: unit,
                decoration: const InputDecoration(labelText: 'Đơn vị, ví dụ m'),
              ),
            ],
          ),
          FilledButton.icon(
            onPressed: ready && !busy && !running && !uncertain ? send : null,
            icon: const Icon(Icons.send),
            label: const Text('Gửi việc'),
          ),
          if (jobId != null) ...[
            const SizedBox(height: 16),
            Text(
              statusName(job?['status']),
              style: Theme.of(context).textTheme.titleMedium,
            ),
            Text('Mã tác vụ: $jobId'),
            if (error != null)
              TextButton(
                onPressed: busy ? null : clearUncertain,
                child: const Text('Đã kiểm tra PC · bỏ theo dõi tác vụ'),
              ),
            Wrap(
              spacing: 8,
              children: [
                TextButton(
                  onPressed: ready && !busy ? () => action(readJob) : null,
                  child: const Text('Làm mới'),
                ),
                if (running)
                  TextButton(
                    onPressed: ready && !busy ? stop : null,
                    child: const Text('Dừng công việc'),
                  ),
              ],
            ),
            if (running)
              const Text(
                'AI đang xử lý trên PC. Dừng có hiệu lực trước bước tiếp theo; không hủy thao tác PLAXIS đang chạy.',
              ),
            for (final event in events)
              ListTile(
                dense: true,
                leading: Icon(
                  event['result']?['ok'] == true
                      ? Icons.check_circle_outline
                      : Icons.error_outline,
                ),
                title: Text('Bước ${event['step']}: ${event['tool']}'),
                subtitle: Text(
                  event['result']?['error']?.toString() ??
                      'Đã nhận kết quả công cụ',
                ),
              ),
            if (result != null) ...[
              MarkdownBody(
                data:
                    result['answer']?.toString() ??
                    result['error']?.toString() ??
                    '',
                selectable: true,
                inlineSyntaxes: [MathSyntax()],
                builders: {
                  'math-inline': MathBuilder(),
                  'math-block': MathBuilder(display: true),
                },
              ),
              if (review != null &&
                  (review['checks'] as List<dynamic>? ?? []).isNotEmpty)
                Text(
                  review['passed'] == true
                      ? 'Tiêu chí số liệu đã đạt.'
                      : 'Tiêu chí số liệu chưa đạt.',
                ),
              for (final check in review?['checks'] as List<dynamic>? ?? [])
                Text(
                  '${check["metric"]}: ${check["value"] ?? "chưa có số liệu"} ${check["unit"]} · giới hạn ${check["target"]} · ${check["passed"] == true ? "đạt" : "chưa đạt"}',
                ),
              Text(
                result['model_completion_verified'] == true
                    ? 'Mô hình đã được kiểm chứng.'
                    : 'Chưa kiểm chứng hoàn tất cả bài PLAXIS.',
              ),
              if (result['note'] != null) Text(result['note'].toString()),
            ],
          ],
        ],
      ),
    );
  }
}
