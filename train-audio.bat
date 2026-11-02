@echo off
REM Train the audio signal (YAMNet laughter/applause/crowd cues) on YouTube's own "Most replayed" data.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run start-windows.bat once first.
  pause
  exit /b 1
)
if not exist calibration mkdir calibration
if not exist calibration\videos.txt (
  echo # Paste YouTube links that HAVE the "Most replayed" graph, one per line. 15 or more works best.> calibration\videos.txt
  echo Add some video links to the file that just opened, save it, then run train-audio.bat again.
  notepad calibration\videos.txt
  pause
  exit /b 0
)
set PATH=%~dp0.tools;%~dp0.tools\ffmpeg\bin;%PATH%
".venv\Scripts\python.exe" -m pip install -q "onnxruntime>=1.17"
".venv\Scripts\python.exe" -m scripts.train_audio --file calibration\videos.txt
echo.
echo Restart the server (or sign out and back in for background mode) to use the trained audio model.
pause
