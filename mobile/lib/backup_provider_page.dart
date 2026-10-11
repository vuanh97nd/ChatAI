import 'package:flutter/material.dart';
import 'api.dart';

/// Always addresses the authenticated backup directly; never the failover router.
class BackupProviderPage extends StatefulWidget {
  final ChatApi api;
  const BackupProviderPage({super.key, required this.api});
  @override
  State<BackupProviderPage> createState() => _BackupProviderPageState();
}
class _BackupProviderPageState extends State<BackupProviderPage> {
  final keyInput = TextEditingController(), modelInput = TextEditingController();
  final models = <String, String>{
    'nvidia': 'nvidia/nemotron-3-nano-omni-30b-a3b-reasoning',
    'deepseek': 'deepseek-flash', 'gemini': 'gemini-2.5-flash',
    'groq': 'openai/gpt-oss-120b', 'openai': 'gpt-4.1-mini', 'cloudflare': '',
  };
  static const names = {'nvidia':'NVIDIA', 'deepseek':'DeepSeek', 'gemini':'Gemini',
    'groq':'Groq', 'openai':'OpenAI', 'cloudflare':'Cloudflare AI'};
  String provider = 'nvidia', message = 'Chưa kiểm tra AI.';
  bool busy = false;
  @override
  void initState() { super.initState(); modelInput.text = models[provider]!; }
  @override
  void dispose() { keyInput.dispose(); modelInput.dispose(); super.dispose(); }
  Future<void> perform(String action) async {
    if (busy) return;
    final selected = provider, secret = keyInput.text.trim(), model = modelInput.text.trim();
    if (action == 'save' && selected == 'cloudflare') {
      setState(() => message = 'Cloudflare dùng binding AI, không cần khóa API.'); return;
    }
    if (action == 'save' && secret.isEmpty && model.isEmpty) {
      setState(() => message = 'Nhập khóa API hoặc model để lưu.'); return;
    }
    setState(() { busy = true; message = action == 'test' ? 'Đang kiểm tra AI (có thể tính phí API)…' : 'Đang kết nối server dự phòng…'; });
    try {
      Map<String, dynamic> result;
      if (action == 'save') {
        result = await widget.api.post('/api/admin/providers/save', {
          'providers': {if (secret.isNotEmpty) selected: secret},
          'models': {if (model.isNotEmpty) selected: model},
        });
      } else if (action == 'test' && selected == 'cloudflare') {
        result = await widget.api.post('/api/provider/model', {'provider': selected,
          'messages': [{'role':'user', 'content':'Chỉ trả lời OK.'}], 'max_tokens':64, 'temperature':0});
      } else if (action == 'test') {
        result = await widget.api.post('/api/admin/providers/test', {'provider':selected, 'api_key':secret, 'model':model});
      } else {
        result = await widget.api.post('/api/admin/providers/status', {});
      }
      if (!mounted) return;
      setState(() {
        if (action == 'status') {
          final states = result['providers'] as Map<String, dynamic>? ?? {};
          for (final entry in states.entries) {
            final item = entry.value as Map<String, dynamic>;
            if (models.containsKey(entry.key) && (item['model'] as String? ?? '').isNotEmpty) {
              models[entry.key] = item['model'] as String;
            }
          }
          modelInput.text = models[selected]!;
          message = 'Khóa trên server dự phòng: ${states[selected]?['configured'] == true ? 'đã có' : 'chưa có'}. Chưa kiểm tra phản hồi AI.';
        } else if (action == 'save') {
          keyInput.clear(); models[selected] = model;
          message = 'Đã lưu API trên server dự phòng. Bấm Kiểm tra AI để xác minh.';
        } else if ((result['answer'] as String? ?? '').trim().isEmpty) {
          message = result['message'] as String? ?? 'API phản hồi nhưng chưa có nội dung AI. Chưa xác nhận dự phòng hoạt động.';
        } else {
          message = 'AI dự phòng đã trả lời thành công tại ${widget.api.server.origin}. Nếu vừa thay đổi khóa/model, bấm Lưu API để áp dụng.';
        }
      });
    } catch (error) {
      if (mounted) setState(() => message = 'Chưa thành công: ${secret.isEmpty ? '$error' : '$error'.replaceAll(secret, '[ẨN]')}');
    } finally { if (mounted) setState(() => busy = false); }
  }
  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Cấu hình API dự phòng')),
    body: ListView(padding: const EdgeInsets.all(20), children: [
      Text('Server đích: ${widget.api.server.origin}'),
      const SizedBox(height:12),
      const Text('Lưu khóa cần tài khoản Admin của server dự phòng. Để trống để giữ khóa đã lưu.'),
      DropdownButtonFormField<String>(initialValue:provider, decoration:const InputDecoration(labelText:'Nhà cung cấp'),
        items: [for (final entry in names.entries) DropdownMenuItem(value:entry.key, child:Text(entry.value))],
        onChanged: busy ? null : (value) { if (value != null) setState(() { provider=value; keyInput.clear(); modelInput.text=models[value]!; }); }),
      if (provider == 'cloudflare') const Padding(padding:EdgeInsets.symmetric(vertical:12),
        child:Text('Cloudflare dùng binding AI, không nhập khóa. Model theo cấu hình Worker.')),
      TextField(controller:keyInput, obscureText:true, autocorrect:false, enableSuggestions:false,
        enabled:!busy && provider!='cloudflare', maxLength:4096, decoration:const InputDecoration(labelText:'Khóa API dự phòng')),
      TextField(controller:modelInput, enabled:!busy && provider!='cloudflare', maxLength:160,
        decoration:const InputDecoration(labelText:'Model')),
      Text(message),
      TextButton(onPressed:busy ? null : () => perform('status'), child:const Text('Xem trạng thái')),
      FilledButton(onPressed:busy || provider=='cloudflare' ? null : () => perform('save'), child:const Text('Lưu API dự phòng')),
      OutlinedButton(onPressed:busy ? null : () => perform('test'), child:const Text('Kiểm tra AI')),
    ]));
}
