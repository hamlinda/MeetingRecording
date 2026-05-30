Set shell = CreateObject("WScript.Shell")
Set exec = shell.Exec("C:\Dev\MeetingRecording\backend\venv\Scripts\pythonw.exe C:\Dev\MeetingRecording\backend\main.py")
WScript.Sleep 5000
exec.Terminate
