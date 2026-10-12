using System;
using System.Collections.Generic;
using System.IO;
using System.Security.Cryptography;
using System.Text;

namespace ChatAI.AutoCAD2023 {
    internal static class SessionStore {
        private static readonly string FilePath = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "ChatAI", "AutoCAD2023", "session.dat");
        private static readonly byte[] Entropy = Encoding.UTF8.GetBytes("ChatAI.AutoCAD2023.Session.v1");
        internal static void Save(Dictionary<string, string> session) {
            var plain = Encoding.UTF8.GetBytes(ChatClient.Json.Serialize(session));
            var encrypted = ProtectedData.Protect(plain, Entropy, DataProtectionScope.CurrentUser);
            Directory.CreateDirectory(Path.GetDirectoryName(FilePath));
            var temp = FilePath + "." + Guid.NewGuid().ToString("N") + ".tmp";
            try {
                File.WriteAllBytes(temp, encrypted);
                if (File.Exists(FilePath)) File.Replace(temp, FilePath, null);
                else File.Move(temp, FilePath);
            } finally { if (File.Exists(temp)) File.Delete(temp); }
        }
        internal static Dictionary<string, string> Load() {
            if (!File.Exists(FilePath)) return null;
            if (new FileInfo(FilePath).Length > 65536) throw new InvalidDataException("Session file too large.");
            var plain = ProtectedData.Unprotect(File.ReadAllBytes(FilePath), Entropy, DataProtectionScope.CurrentUser);
            return ChatClient.Json.Deserialize<Dictionary<string, string>>(Encoding.UTF8.GetString(plain));
        }
        internal static void Delete() { if (File.Exists(FilePath)) File.Delete(FilePath); }
    }
}
