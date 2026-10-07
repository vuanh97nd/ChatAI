// Small Windows GUI launcher. Python and libraries are bundled beside the app.
using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

internal static class Launcher
{
    [STAThread]
    private static void Main()
    {
        string root = AppDomain.CurrentDomain.BaseDirectory;
        string python = Path.Combine(root, @"runtime\python\pythonw.exe");
        string script = Path.Combine(root, "desktop_launcher.py");
        try
        {
            if (!File.Exists(python) || !File.Exists(script))
                throw new FileNotFoundException("Chat AI thieu runtime. Hay cai lai bang bo cai moi.");
            ProcessStartInfo info = new ProcessStartInfo();
            info.FileName = python;
            info.Arguments = "\"" + script + "\"";
            info.WorkingDirectory = root;
            info.UseShellExecute = false;
            info.CreateNoWindow = true;
            info.EnvironmentVariables.Remove("PYTHONHOME");
            info.EnvironmentVariables.Remove("PYTHONPATH");
            info.EnvironmentVariables["PYTHONUTF8"] = "1";
            info.EnvironmentVariables["PYTHONUNBUFFERED"] = "1";
            Process.Start(info);
        }
        catch (Exception error)
        {
            MessageBox.Show(error.Message, "Chat AI", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }
}
