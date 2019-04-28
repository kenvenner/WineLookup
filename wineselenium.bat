REM run the Selenium based tool that pulls new data down from websites
REM 
REM clear the log file
del wineselenium.log
del wineselenium-err.log
REM
REM Message that we are past this point in an email
sendgmail subject_adder=" - wineselenium STARTED"
REM
REM
REM Messaging
echo %date% %time% wineselenium.py use selenium to read in new data >> wineselenium.log
REM
python wineselenium.py >> wineselenium.log 2>>wineselenium-err.log
REM 
REM check to see if we error'd out
if errorlevel 1 (
   TASKKILL /IM chrome.exe /F
   TASKKILL /IM chromedriver.exe /f
   echo %date% %time% wineselenium.py run again to do failure 1 >> wineselenium.log
   sendgmail subject_adder=" - wineselenium RESTARTED 1" 
   python wineselenium.py >> wineselenium.log 2>>wineselenium-err.log
)
if errorlevel 1 (
   TASKKILL /IM chrome.exe /F
   TASKKILL /IM chromedriver.exe /f
   echo %date% %time% wineselenium.py run again to do failure 2 >> wineselenium.log
   sendgmail subject_adder=" - wineselenium RESTARTED 2"
   python wineselenium.py >> wineselenium.log 2>>wineselenium-err.log
)
if errorlevel 1 (
   TASKKILL /IM chrome.exe /F
   TASKKILL /IM chromedriver.exe /f
   echo %date% %time% wineselenium.py run again to do failure 3 >> wineselenium.log
   sendgmail subject_adder=" - wineselenium RESTARTED 3"
   python wineselenium.py >> wineselenium.log 2>>wineselenium-err.log
)
if errorlevel 1 (
   TASKKILL /IM chrome.exe /F
   TASKKILL /IM chromedriver.exe /f
   echo %date% %time% wineselenium.py not run again to do failure 4 >> wineselenium.log
   sendgmail subject_adder=" - wineselenium FAILED and not restarted"
   echo %date% %time% wineselenium.py TERMINATE this program >> wineselenium.log
   exit 1
)
REM notify if there is issue processing
IF EXIST fail*.html (
   echo %date% %time% wineselenium.py errors in HTML files >> wineselenium.log
   sendgmail subject_adder=" - wineselenium had ERRORS please review log file and HTML files"
)
REM
REM Messaging
echo %date% %time% wine_dedup.pl deduplicate records just created >> wineselenium.log
REM
REM Dedupe these results - append to the winesrch.csv file and rename the input
perl wine_dedup.pl file_input=wineselenium.csv file_output=winesrch.csv file_append=1 del_flag=1 rename_flag=1 >> wineselenium.log 2>>wineselenium-err.log
REM
REM eof
