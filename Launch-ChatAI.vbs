Option Explicit
Dim fs, shell, root, python, script, candidates, candidate, execResult, lines, line, i
Dim venvCfg, cfgFile, cfgLine, venvHome, venvPython
Set fs = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
root = fs.GetParentFolderName(WScript.ScriptFullName)
python = fs.BuildPath(root, "runtime\python\pythonw.exe")
If Not fs.FileExists(python) Then
    ' A venv launcher can exist while its base Python has moved. Validate
    ' pyvenv.cfg first so it cannot raise the stale Python312 dialog.
    venvPython = fs.BuildPath(root, ".venv\Scripts\pythonw.exe")
    venvCfg = fs.BuildPath(root, ".venv\pyvenv.cfg")
    If fs.FileExists(venvPython) And fs.FileExists(venvCfg) Then
        venvHome = ""
        Set cfgFile = fs.OpenTextFile(venvCfg, 1, False, -1)
        Do Until cfgFile.AtEndOfStream
            cfgLine = Trim(cfgFile.ReadLine)
            If LCase(Left(cfgLine, 5)) = "home=" Then
                venvHome = Trim(Mid(cfgLine, 6))
                Exit Do
            ElseIf LCase(Left(cfgLine, 5)) = "home " Then
                If InStr(cfgLine, "=") > 0 Then venvHome = Trim(Mid(cfgLine, InStr(cfgLine, "=") + 1))
                If venvHome <> "" Then Exit Do
            End If
        Loop
        cfgFile.Close
        If venvHome <> "" Then
            If fs.FileExists(fs.BuildPath(venvHome, "python.exe")) And _
               fs.FileExists(fs.BuildPath(venvHome, "pythonw.exe")) Then
                python = venvPython
            End If
        End If
    End If
End If
If Not fs.FileExists(python) Then
    ' Source mode: tìm Python trực tiếp, không gọi py.exe/Python Launcher
    ' vì launcher có thể đang lưu đường dẫn Python312 cũ.
    candidates = Array( _
        shell.ExpandEnvironmentStrings("%LOCALAPPDATA%\Programs\Python\Python314\pythonw.exe"), _
        shell.ExpandEnvironmentStrings("%LOCALAPPDATA%\Programs\Python\Python313\pythonw.exe"), _
        shell.ExpandEnvironmentStrings("%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe"), _
        shell.ExpandEnvironmentStrings("%LOCALAPPDATA%\Programs\Python\Python311\pythonw.exe"), _
        shell.ExpandEnvironmentStrings("%ProgramFiles%\Python314\pythonw.exe"), _
        shell.ExpandEnvironmentStrings("%ProgramFiles%\Python313\pythonw.exe"), _
        shell.ExpandEnvironmentStrings("%ProgramFiles%\Python312\pythonw.exe"), _
        shell.ExpandEnvironmentStrings("%ProgramFiles%\Python311\pythonw.exe"), _
        shell.ExpandEnvironmentStrings("%ProgramFiles(x86)%\Python314\pythonw.exe"), _
        shell.ExpandEnvironmentStrings("%ProgramFiles(x86)%\Python313\pythonw.exe"), _
        shell.ExpandEnvironmentStrings("%ProgramFiles(x86)%\Python312\pythonw.exe"), _
        shell.ExpandEnvironmentStrings("%ProgramFiles(x86)%\Python311\pythonw.exe"))
    For Each candidate In candidates
        If fs.FileExists(candidate) Then
            python = candidate
            Exit For
        End If
    Next
End If
If Not fs.FileExists(python) Then
    ' Nếu Python được cài trong thư mục tùy chỉnh và có trong PATH,
    ' lấy vị trí python.exe rồi đổi sang pythonw.exe cùng thư mục.
    On Error Resume Next
    Set execResult = shell.Exec("where.exe python.exe")
    If Err.Number = 0 Then
        lines = Split(execResult.StdOut.ReadAll, vbCrLf)
        For i = 0 To UBound(lines)
            line = Trim(lines(i))
            If LCase(Right(line, 10)) = "python.exe" And InStr(LCase(line), "\windowsapps\") = 0 Then
                candidate = Left(line, Len(line) - 10) & "pythonw.exe"
                If fs.FileExists(candidate) Then
                    python = candidate
                    Exit For
                End If
            End If
        Next
    End If
    Err.Clear
    On Error GoTo 0
End If
If Not fs.FileExists(python) Then
    MsgBox "Khong tim thay Python 3.11 tro len trong runtime, .venv hoac PATH. " & _
           "Chat AI khong goi Python Launcher nen se khong dung duong dan Python312 cu. " & _
           "Hay dung bo cai Chat AI day du hoac dat Python vao PATH.", 16, "Chat AI"
    WScript.Quit 1
End If
script = fs.BuildPath(root, "desktop_launcher.py")
If Not fs.FileExists(script) Then
    MsgBox "Chat AI thieu desktop_launcher.py. Hay doi dong bo du tep.", 16, "Chat AI"
    WScript.Quit 1
End If
shell.CurrentDirectory = root
shell.Environment("Process").Remove "PYTHONHOME"
shell.Environment("Process").Remove "PYTHONPATH"
shell.Environment("Process")("PYTHONUTF8") = "1"
shell.Environment("Process")("PYTHONUNBUFFERED") = "1"
shell.Run """" & python & """ """ & script & """", 0, False
