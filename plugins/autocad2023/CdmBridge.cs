using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Threading.Tasks;

namespace ChatAI.AutoCAD2023 {
    internal static class CdmBridge {
        internal static async Task<Dictionary<string, object>> Render(string root, string plan, string output) {
            root = Path.GetFullPath(root.Trim());
            var python = Path.Combine(root, ".venv", "Scripts", "python.exe");
            if (!File.Exists(python) || !File.Exists(Path.Combine(root, "assistant", "autocad_cdm.py")))
                throw new InvalidOperationException("Chọn thư mục mã nguồn ChatAI và chạy setup-cdm.ps1 trước.");
            var parsed = ChatClient.Json.Deserialize<Dictionary<string, object>>(plan);
            var request = ChatClient.Json.Serialize(new { plan = parsed, output });
            if (Encoding.UTF8.GetByteCount(request) > 262144) throw new ArgumentException("Yêu cầu vượt 256 KiB.");
            var info = new ProcessStartInfo(python, "-m assistant.autocad_cdm") {
                WorkingDirectory = root, UseShellExecute = false, CreateNoWindow = true,
                RedirectStandardInput = true, RedirectStandardOutput = true, RedirectStandardError = true,
                StandardOutputEncoding = Encoding.UTF8, StandardErrorEncoding = Encoding.UTF8
            };
            info.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8";
            using (var process = Process.Start(info)) {
                var stdout = process.StandardOutput.ReadToEndAsync();
                var stderr = process.StandardError.ReadToEndAsync();
                // Write UTF-8 bytes explicitly; Windows console code pages must not corrupt Vietnamese.
                var bytes = Encoding.UTF8.GetBytes(request);
                await process.StandardInput.BaseStream.WriteAsync(bytes, 0, bytes.Length);
                process.StandardInput.Close();
                var exited = await Task.Run(() => process.WaitForExit(60000));
                if (!exited) {
                    try { process.Kill(); } catch (InvalidOperationException) { }
                    throw new TimeoutException("Quá 60 giây tạo DXF. Kiểm tra file trước khi thử lại.");
                }
                var raw = await stdout; await stderr;
                if (process.ExitCode != 0 || raw.Length > 1048576)
                    throw new InvalidOperationException("Bộ tạo DXF lỗi. Kiểm tra .venv và ezdxf.");
                var result = ChatClient.Json.Deserialize<Dictionary<string, object>>(raw);
                if (!result.ContainsKey("ok") || !Equals(result["ok"], true))
                    throw new InvalidOperationException(result.ContainsKey("error") ? Convert.ToString(result["error"]) : "Chưa tạo được DXF.");
                if (!File.Exists(output) || !String.Equals(Path.GetFullPath(output), Convert.ToString(result["path"]), StringComparison.OrdinalIgnoreCase))
                    throw new InvalidOperationException("Không xác minh được file kết quả.");
                return result;
            }
        }
    }
}
