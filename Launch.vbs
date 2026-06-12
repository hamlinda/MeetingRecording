Option Explicit


Dim fso, shell, currentDir, backendDir, pythonwPath, edgePath

Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

currentDir = fso.GetParentFolderName(WScript.ScriptFullName)
backendDir = fso.BuildPath(currentDir, "backend")
pythonwPath = fso.BuildPath(backendDir, "venv\Scripts\pythonw.exe")

If Not fso.FileExists(pythonwPath) Then
    MsgBox "Backend virtual environment not found in backend\venv. Please ensure the project is correctly set up.", 16, "Error"
    WScript.Quit 1
End If

If Not fso.FileExists(fso.BuildPath(currentDir, "frontend\dist\index.html")) Then
    MsgBox "Frontend production build missing! Please run 'build_native.bat' before launching if you plan to use production mode.", 48, "Warning"
End If

' 1. Cleanup: Ensure port 8083 is free (if old backend got stuck)
shell.Run "taskkill /F /IM pythonw.exe /T", 0, True
WScript.Sleep 1000

' 2. Start backend hidden
Dim backendEnv
Set backendEnv = shell.Environment("PROCESS")
backendEnv("PRODUCTION") = "1"

Dim backendCmd
backendCmd = """" & pythonwPath & """ """ & fso.BuildPath(backendDir, "main.py") & """"
shell.CurrentDirectory = backendDir
shell.Run backendCmd, 0, False

' 3. Wait for backend to be ready via active HTTP polling
Dim ready, i, http
ready = False
Set http = CreateObject("MSXML2.ServerXMLHTTP")
For i = 1 To 15
    On Error Resume Next
    http.Open "GET", "http://127.0.0.1:8083/api/config", False
    http.Send
    If Err.Number = 0 And http.Status = 200 Then
        ready = True
    End If
    On Error GoTo 0
    If ready Then Exit For
    WScript.Sleep 1000
Next

If Not ready Then
    MsgBox "WARNING: Backend did not respond on 127.0.0.1:8083. Application may not load correctly.", 48, "Warning"
End If

' 4. Start Edge in app mode (emulates native window)
Dim edgePaths(1)
edgePaths(0) = shell.ExpandEnvironmentStrings("%ProgramFiles(x86)%") & "\Microsoft\Edge\Application\msedge.exe"
edgePaths(1) = shell.ExpandEnvironmentStrings("%ProgramFiles%") & "\Microsoft\Edge\Application\msedge.exe"

edgePath = "msedge.exe"
If fso.FileExists(edgePaths(0)) Then
    edgePath = """" & edgePaths(0) & """"
ElseIf fso.FileExists(edgePaths(1)) Then
    edgePath = """" & edgePaths(1) & """"
End If

Dim appCmd
appCmd = edgePath & " --app=http://127.0.0.1:8083"
shell.CurrentDirectory = currentDir

' Block until Edge closes
shell.Run appCmd, 1, True

' 5. End of script
WScript.Quit 0
