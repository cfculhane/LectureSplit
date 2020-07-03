pyinstaller build.spec --noconfirm
mkdir .\dist\LectureSplit\input
mkdir .\dist\LectureSplit\output
robocopy .\tests\testdata .\dist\LectureSplit\input lecture_trimmed.mp4
powershell "Compress-Archive .\dist\LectureSplit\ .\dist\LectureSplit.zip -Force"
