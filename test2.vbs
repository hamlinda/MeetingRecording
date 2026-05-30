Function StartHiddenProcess(cmdLine, workDir)
Dim objWMIService, objStartup, objConfig, intProcessID
Set objWMIService = GetObject("winmgmts:\\.\root\cimv2")
Set objStartup = objWMIService.Get("Win32_ProcessStartup")
Set objConfig = objStartup.SpawnInstance_
objConfig.ShowWindow = 0
Dim objProcess
Set objProcess = GetObject("winmgmts:root\cimv2:Win32_Process")
Dim errReturn
errReturn = objProcess.Create(cmdLine, workDir, objConfig, intProcessID)
WScript.Echo "Result: " & errReturn & " PID: " & intProcessID
End Function
StartHiddenProcess ""C:\Dev\MeetingRecording\backend\venv\Scripts\pythonw.exe" "C:\Dev\MeetingRecording\backend\main.py"", "C:\Dev\MeetingRecording\backend"
