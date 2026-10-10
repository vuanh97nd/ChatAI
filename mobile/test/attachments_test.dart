import 'dart:convert';
import 'dart:typed_data';
import 'package:archive/archive.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:chatai_mobile/attachments.dart';

Uint8List zip(Map<String, String> files) {
  final archive = Archive();
  for (final entry in files.entries) {
    final bytes = utf8.encode(entry.value);
    archive.addFile(ArchiveFile(entry.key, bytes.length, bytes));
  }
  return Uint8List.fromList(ZipEncoder().encode(archive));
}

void main() {
  test('text keeps Vietnamese intact and unsupported files are rejected', () {
    expect(readAttachment('input.csv', Uint8List.fromList(utf8.encode('Lớp đất,Su\nSét,25'))).text, contains('Sét,25'));
    expect(() => readAttachment('scan.pdf', Uint8List.fromList([1])), throwsFormatException);
    expect(() => readAttachment('fake.png', Uint8List.fromList([1, 2, 3])), throwsFormatException);
    expect(() => readAttachment('huge.txt', Uint8List.fromList(utf8.encode('x' * 35001))), throwsFormatException);
  });
  test('DOCX reads paragraphs, not XML markup', () {
    final data = zip({'word/document.xml': '<w:document xmlns:w="urn:word"><w:p><w:r><w:t>Địa tầng</w:t></w:r></w:p><w:p><w:r><w:t>Lớp 1</w:t></w:r></w:p></w:document>'});
    expect(readAttachment('report.docx', data).text, 'Địa tầng\nLớp 1');
  });
  test('XLSX keeps sheet and cell references, shared strings and cached formula warning', () {
    final data = zip({
      'xl/workbook.xml': '<workbook xmlns:r="urn:rel"><sheets><sheet name="SLTT" r:id="r1"/></sheets></workbook>',
      'xl/_rels/workbook.xml.rels': '<Relationships><Relationship Id="r1" Target="worksheets/sheet1.xml"/></Relationships>',
      'xl/sharedStrings.xml': '<sst><si><t>Su</t></si></sst>',
      'xl/worksheets/sheet1.xml': '<worksheet><sheetData><row><c r="A1" t="s"><v>0</v></c><c r="B1"><f>10+15</f><v>25</v></c></row></sheetData></worksheet>',
    });
    final text = readAttachment('input.xlsx', data).text;
    expect(text, contains('Sheet: SLTT'));
    expect(text, contains('A1: Su'));
    expect(text, contains('B1: 25'));
    expect(text, contains('chưa tính lại'));
  });
}
