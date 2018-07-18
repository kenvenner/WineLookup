REM run the Selenium based tool that pulls new data down from websites
REM
REM Message that we are past this point in an email
sendgmail subject_adder=" - wineselenium STARTED"
REM
REM
REM Messaging
echo %date% %time% wine.py use selenium to read in new data >> winechk.log
REM
python wine.py >> wineselenium.log 2>>wineselenium-err.log
REM 
REM check to see if we error'd out
if errorlevel 1 (
   echo %date% %time% wine.py run again to do failure 1 >> winechk.log
   TASKKILL /IM chrome.exe /F
   sendgmail subject_adder=" - wineselenium RESTARTED 1" 
  python wine.py >> wineselenium.log 2>>wineselenium-err.log
)
if errorlevel 1 (
   echo %date% %time% wine.py run again to do failure 2 >> winechk.log
   TASKKILL /IM chrome.exe /F
   sendgmail subject_adder=" - wineselenium RESTARTED 2"
   python wine.py >> wineselenium.log 2>>wineselenium-err.log
)
if errorlevel 1 (
   echo %date% %time% wine.py run again to do failure 3 >> winechk.log
   TASKKILL /IM chrome.exe /F
   sendgmail subject_adder=" - wineselenium RESTARTED 3"
   python wine.py >> wineselenium.log 2>>wineselenium-err.log
)
if errorlevel 1 (
   echo %date% %time% wine.py not run again to do failure 4 >> winechk.log
   sendgmail subject_adder=" - wineselenium FAILED and not restarted"
)
REM
REM Messaging
echo %date% %time% wine_dedup.pl deduplicate records just created >> winechk.log
REM
REM Dedupe these results - append to the winesrch.csv file and rename the input
perl wine_dedup.pl file_input=wineselenium.csv file_output=winesrch.csv file_append=1 del_flag=1 rename_flag=1 >> wineselenium.log 2>wineselenium-err.log
REM
REM eof
