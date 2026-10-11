import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:flutter_math_fork/flutter_math.dart';
import 'package:markdown/markdown.dart' as md;

class MathSyntax extends md.InlineSyntax {
  MathSyntax() : super(r'\$\$([\s\S]+?)\$\$|\\\[([\s\S]+?)\\\]|\\\(([\s\S]+?)\\\)|(?<!\\)\$([^\$\n]+?)\$');
  @override
  bool onMatch(md.InlineParser parser, Match match) {
    final block = match.group(1) != null || match.group(2) != null;
    final tex = match.group(1) ?? match.group(2) ?? match.group(3) ?? match.group(4)!;
    parser.addNode(md.Element.text(block ? 'math-block' : 'math-inline', tex));
    return true;
  }
}

class MathBuilder extends MarkdownElementBuilder {
  final bool display;
  MathBuilder({this.display = false});
  @override
  Widget? visitElementAfter(md.Element element, TextStyle? preferredStyle) {
    final formula = Math.tex(element.textContent,
      mathStyle: display ? MathStyle.display : MathStyle.text,
      textStyle: preferredStyle,
      onErrorFallback: (_) => SelectableText(element.textContent, style: preferredStyle));
    return SingleChildScrollView(scrollDirection: Axis.horizontal,
      child: Padding(padding: EdgeInsets.symmetric(vertical: display ? 12 : 2), child: formula));
  }
}
