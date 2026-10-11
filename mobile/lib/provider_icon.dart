import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';

class ProviderIcon extends StatelessWidget {
  final String? provider;
  final double size;
  const ProviderIcon({super.key, required this.provider, this.size = 24});
  @override
  Widget build(BuildContext context) {
    final name = provider?.startsWith('deepseek') == true ? 'deepseek' : provider;
    const colors = {'nvidia': Color(0xff76b900), 'deepseek': Color(0xff4d6bfe),
      'cloudflare': Color(0xfff48120), 'gemini': Color(0xff4285f4), 'groq': Color(0xfff55036)};
    if (!colors.containsKey(name)) return Image.asset('assets/chat_ai.png', width: size, height: size);
    return SvgPicture.asset('assets/providers/$name.svg', width: size, height: size,
      semanticsLabel: 'Biểu tượng $name', colorFilter: ColorFilter.mode(colors[name]!, BlendMode.srcIn));
  }
}
class ProviderOption extends StatelessWidget {
  final String provider, label;
  const ProviderOption({super.key, required this.provider, required this.label});
  @override
  Widget build(BuildContext context) => Row(children: [ProviderIcon(provider: provider, size: 20),
    const SizedBox(width: 8), Expanded(child: Text(label, overflow: TextOverflow.ellipsis))]);
}
