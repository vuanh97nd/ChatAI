import 'dart:convert';
import 'dart:typed_data';
import 'package:archive/archive.dart';
import 'package:xml/xml.dart';

class ChatAttachment {
  final String name, text;
  final String? imageUrl;
  const ChatAttachment(this.name, this.text, [this.imageUrl]);
}

ChatAttachment decodeAttachment(Map<String, dynamic> data) => readAttachment(data['name'] as String, data['bytes'] as Uint8List);

const attachmentExtensions = ['txt', 'md', 'csv', 'json', 'docx', 'xlsx', 'png', 'jpg', 'jpeg'];

ChatAttachment readAttachment(String name, Uint8List bytes) {
  if (bytes.isEmpty || bytes.length > 8 * 1024 * 1024) {
    throw const FormatException('File phải có nội dung và không quá 8 MB.');
  }
  final ext = name.split('.').last.toLowerCase();
  if (!attachmentExtensions.contains(ext)) throw const FormatException('Định dạng chưa được hỗ trợ.');
  if (['png', 'jpg', 'jpeg'].contains(ext)) {
    final valid = ext == 'png' ? bytes.length > 8 && [137, 80, 78, 71, 13, 10, 26, 10].asMap().entries.every((e) => bytes[e.key] == e.value)
      : bytes.length > 8 && bytes[0] == 255 && bytes[1] == 216 && bytes[2] == 255;
    if (!valid) throw const FormatException('Nội dung file không khớp định dạng ảnh.');
    return ChatAttachment(name, '', 'data:image/${ext == 'jpg' ? 'jpeg' : ext};base64,${base64Encode(bytes)}');
  }
  String text;
  if (ext == 'docx' || ext == 'xlsx') {
    final zip = ZipDecoder().decodeBytes(bytes);
    if (zip.files.fold<int>(0, (sum, file) => sum + file.size) > 32 * 1024 * 1024) {
      throw const FormatException('File nén giải nén quá lớn.');
    }
    XmlDocument? xml(String path) {
      final matches = zip.files.where((f) => f.name == path);
      return matches.isEmpty ? null : XmlDocument.parse(utf8.decode(matches.first.content));
    }
    if (ext == 'docx') {
      final doc = xml('word/document.xml');
      if (doc == null) throw const FormatException('DOCX thiếu nội dung tài liệu.');
      text = doc.descendants.whereType<XmlElement>().where((e) => e.name.local == 'p')
        .map((p) => p.descendants.whereType<XmlElement>().where((e) => e.name.local == 't').map((e) => e.innerText).join()).join('\n');
    } else {
      final shared = xml('xl/sharedStrings.xml')?.descendants.whereType<XmlElement>().where((e) => e.name.local == 'si')
        .map((e) => e.descendants.whereType<XmlElement>().where((t) => t.name.local == 't').map((t) => t.innerText).join()).toList() ?? <String>[];
      final workbook = xml('xl/workbook.xml');
      final relations = xml('xl/_rels/workbook.xml.rels');
      final sheets = workbook?.descendants.whereType<XmlElement>().where((e) => e.name.local == 'sheet') ?? <XmlElement>[];
      final chunks = <String>[];
      for (final sheet in sheets) {
        final id = sheet.attributes.where((a) => a.name.local == 'id').first.value;
        final rel = relations?.descendants.whereType<XmlElement>().where((e) => e.getAttribute('Id') == id).first;
        final target = rel?.getAttribute('Target');
        if (target == null) throw const FormatException('XLSX thiếu liên kết sheet.');
        final path = target.startsWith('/') ? target.substring(1) : 'xl/$target';
        final doc = xml(path);
        if (doc == null) throw const FormatException('XLSX thiếu sheet.');
        chunks.add('Sheet: ${sheet.getAttribute('name')}');
        for (final cell in doc.descendants.whereType<XmlElement>().where((e) => e.name.local == 'c')) {
          final values = cell.childElements.where((e) => e.name.local == 'v');
          var value = values.isEmpty ? '' : values.first.innerText;
          if (cell.getAttribute('t') == 's') value = shared[int.parse(value)];
          if (cell.getAttribute('t') == 'inlineStr') value = cell.descendants.whereType<XmlElement>().where((e) => e.name.local == 't').map((e) => e.innerText).join();
          final formula = cell.childElements.where((e) => e.name.local == 'f');
          if (formula.isNotEmpty) value += ' [công thức: ${formula.first.innerText}; giá trị cache, chưa tính lại]';
          chunks.add('${cell.getAttribute('r')}: $value');
        }
      }
      text = chunks.join('\n');
    }
  } else {
    text = utf8.decode(bytes);
  }
  if (text.trim().isEmpty || text.length > 35000) throw const FormatException('File trống hoặc vượt 35.000 ký tự; hãy chia nhỏ.');
  return ChatAttachment(name, text);
}
