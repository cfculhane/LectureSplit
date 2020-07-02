pyinstaller build_dir.spec --noconfirm
REM pyinstaller build_onefile.spec --noconfirm
mkdir .\dist\LectureSplit\input
mkdir .\dist\LectureSplit\output
robocopy .\tests\testdata .\dist\LectureSplit\input lecture_trimmed.mp4
powershell "Compress-Archive .\dist\LectureSplit\ .\dist\LectureSplit.zip"
