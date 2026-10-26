@echo off
echo ===================================================
echo Installing pgvector into PostgreSQL 18
echo ===================================================

:: Ensure Administrator privileges
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] Please right-click this file and select "Run as administrator"!
    pause
    exit /b 1
)

set "SRC=d:\Satyavani AI\scratch\pgvector"
set "PG=C:\Program Files\PostgreSQL\18"

echo Copying vector.dll to %PG%\lib...
copy /Y "%SRC%\lib\vector.dll" "%PG%\lib\"

echo Copying extension files to %PG%\share\extension...
copy /Y "%SRC%\share\extension\*" "%PG%\share\extension\"

echo Copying header files to %PG%\include\server\extension\vector...
if not exist "%PG%\include\server\extension\vector" mkdir "%PG%\include\server\extension\vector"
copy /Y "%SRC%\include\server\extension\vector\*" "%PG%\include\server\extension\vector\"

echo ===================================================
echo [SUCCESS] pgvector files copied successfully!
echo Restarting PostgreSQL service...
net stop postgresql-x64-18
net start postgresql-x64-18
echo Done! You can now run: python scripts/init_db.py
echo ===================================================
pause
