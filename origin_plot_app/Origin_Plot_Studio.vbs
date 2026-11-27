' Origin Plot Studio - starts the app without any black window.
' Double-click this file, or drag data files onto it.
' The first time (or when a Python package is missing) it opens Run_Origin_Plot_App.bat instead, which tells you to run Setup (packages are installed only by Setup, from the tested list).
Option Explicit
Dim sh, fso, folder, args, i, rc
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
folder = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = folder
args = ""
For i = 0 To WScript.Arguments.Count - 1
  args = args & " """ & WScript.Arguments(i) & """"
Next
On Error Resume Next
rc = sh.Run("py -3 -c ""import importlib.util as u,sys; sys.exit(any(u.find_spec(m) is None for m in ('win32com','pandas','openpyxl','numpy','matplotlib','xlrd','PySide6')))""", 0, True)
If Err.Number <> 0 Then rc = 1
Err.Clear
If rc = 0 Then rc = sh.Run("pyw -3 start.pyw" & args, 0, False)
If Err.Number <> 0 Or rc <> 0 Then
  Err.Clear
  sh.Run """" & folder & "\Run_Origin_Plot_App.bat""" & args, 1, False
End If
