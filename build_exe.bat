@echo off
echo Building ASM Export executable...
env\Scripts\pyinstaller asm_export.spec
echo.
echo Build complete!
echo.
echo Executable location: dist\asm_export.exe
echo.
echo To run: dist\asm_export.exe
echo.
pause
