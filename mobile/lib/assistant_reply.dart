import 'package:flutter/material.dart';
import 'provider_icon.dart';
import 'package:flutter/services.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:url_launcher/url_launcher.dart';

String providerLabel(String? provider) => const {
  'nvidia': 'NVIDIA', 'deepseek_flash': 'DeepSeek', 'cloudflare': 'Cloudflare AI',
  'gemini': 'Gemini', 'groq': 'Groq',
}[provider] ?? '';

class AssistantReply extends StatefulWidget {
  final String text;
  final String? provider;
  final bool reading;
  final VoidCallback onRead;
  const AssistantReply({super.key, required this.text, this.provider,
    required this.reading, required this.onRead});
  @override
  State<AssistantReply> createState() => _AssistantReplyState();
}
class _AssistantReplyState extends State<AssistantReply> {
  int vote = 0;
  Future<void> copy() async {
    await Clipboard.setData(ClipboardData(text: widget.text));
    if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Đã sao chép')));
  }
  Future<void> openLink(String? href) async {
    final uri = Uri.tryParse(href ?? '');
    if (uri == null || !['https', 'http'].contains(uri.scheme) || uri.host.isEmpty) return;
    try {
      if (!await launchUrl(uri, mode: LaunchMode.externalApplication)) throw Exception('Không mở được liên kết.');
    } catch (_) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Không mở được liên kết.')));
    }
  }
  @override
  Widget build(BuildContext context) {
    final name = providerLabel(widget.provider);
    return Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [ProviderIcon(provider: widget.provider, size: 28),
        const SizedBox(width: 8), Expanded(child: Text(name.isEmpty ? 'Chat AI' : 'Chat AI · $name',
          style: Theme.of(context).textTheme.labelLarge))]),
      const SizedBox(height: 12),
      MarkdownBody(data: widget.text, selectable: true,
        onTapLink: (_, href, _) => openLink(href)),
      const SizedBox(height: 8),
      Wrap(spacing: 4, children: [
        IconButton(tooltip: 'Sao chép', onPressed: copy, icon: const Icon(Icons.copy_outlined, size: 20)),
        IconButton(tooltip: widget.reading ? 'Dừng đọc' : 'Đọc câu trả lời', onPressed: widget.onRead,
          icon: Icon(widget.reading ? Icons.stop : Icons.volume_up_outlined, size: 20)),
        IconButton(tooltip: 'Thích', isSelected: vote == 1, onPressed: () => setState(() => vote = vote == 1 ? 0 : 1),
          icon: const Icon(Icons.thumb_up_outlined, size: 20), selectedIcon: const Icon(Icons.thumb_up, size: 20)),
        IconButton(tooltip: 'Không thích', isSelected: vote == -1, onPressed: () => setState(() => vote = vote == -1 ? 0 : -1),
          icon: const Icon(Icons.thumb_down_outlined, size: 20), selectedIcon: const Icon(Icons.thumb_down, size: 20)),
      ]),
    ]);
  }
}
