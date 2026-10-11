import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'api.dart';

/// Separate credentials: never send the ChatAI account session to the PC agent.
class PlaxisAgentApi {
  final Uri endpoint;
  final String token;
  final http.Client client;
  PlaxisAgentApi(String address, this.token, {http.Client? client})
    : endpoint = Uri.parse(address.trim()),
      client = client ?? http.Client() {
    if (endpoint.scheme != 'https' ||
        endpoint.host.isEmpty ||
        endpoint.userInfo.isNotEmpty ||
        endpoint.hasQuery ||
        endpoint.hasFragment ||
        !['', '/'].contains(endpoint.path) ||
        token.trim().isEmpty ||
        token.contains('\n') ||
        token.contains('\r')) {
      throw ArgumentError(
        'Nhập URL gốc HTTPS và mã kết nối của agent trên PC.',
      );
    }
  }

  Future<Map<String, dynamic>> request(
    String method,
    String path, [
    Map<String, dynamic>? body,
  ]) async {
    try {
      final request = http.Request(method, endpoint.resolve(path));
      request.followRedirects = false;
      request.headers.addAll({
        'Authorization': 'Bearer $token',
        'Accept': 'application/json',
      });
      if (body != null) {
        request.headers['Content-Type'] = 'application/json; charset=utf-8';
        request.body = jsonEncode(body);
      }
      final streamed = await client
          .send(request)
          .timeout(const Duration(seconds: 15));
      final response = await http.Response.fromStream(
        streamed,
      ).timeout(const Duration(seconds: 15));
      if (response.statusCode >= 300) {
        // Do not display arbitrary upstream text containing credentials or HTML.
        throw ApiException(
          response.statusCode == 401
              ? 'Mã kết nối agent không hợp lệ.'
              : response.statusCode == 404
              ? 'Không tìm thấy tác vụ. PC có thể đã khởi động lại; không tự chạy lại.'
              : 'Agent từ chối yêu cầu (HTTP ${response.statusCode}).',
          response.statusCode,
        );
      }
      final value = jsonDecode(utf8.decode(response.bodyBytes));
      if (value is! Map<String, dynamic>) throw const FormatException();
      return value;
    } on TimeoutException {
      throw ApiException(
        'Chưa nhận được phản hồi từ PC. Nếu vừa gửi việc, chưa rõ việc đã được nhận; không gửi lại để tránh chạy trùng.',
      );
    } on http.ClientException {
      throw ApiException('Không kết nối được agent trên PC.');
    } on FormatException {
      throw ApiException('Agent trả dữ liệu không hợp lệ.');
    }
  }

  Future<Map<String, dynamic>> connect() => request('GET', '/health');
  Future<Map<String, dynamic>> submit(
    String prompt,
    String version,
    String project, {
    List<Map<String, dynamic>> criteria = const [],
  }) => request('POST', '/plaxis/jobs', {
    'prompt': prompt,
    'version': version,
    'project_id': project,
    'criteria': criteria,
    'max_steps': 12,
    'max_reviews': 2,
  });
  Future<Map<String, dynamic>> inspect(String id) =>
      request('GET', '/plaxis/jobs/${Uri.encodeComponent(id)}');
  Future<Map<String, dynamic>> stop(String id) =>
      request('POST', '/plaxis/jobs/${Uri.encodeComponent(id)}/stop');
  void close() => client.close();
}
