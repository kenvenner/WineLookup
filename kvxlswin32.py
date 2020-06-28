'''
@author:   Ken Venner
@contact:  ken@venerllc.com
@version:  1.02

Library of tools used on WINDOWS machines to automate working with XLS/XLSX files
'''

# library used to automate refreshing an excel spreadsheet
import win32com.client
import os


# logging
import logging
logger = logging.getLogger(__name__)

# global variables
AppVersion = '1.02'

# -------- REFRESH DATA IN EXCEL AUTOMATION -------------------------

# this routine used com to open xls and cause it to refresh
# the path must be the full path - so we are going to code in that
# conversion so you can pass relative paths
def refreshExcel( xlsfile, debug=False ):
    xlsfileabs = os.path.abspath(xlsfile)
    if debug:
        print('kvxls:refreshExcel:xlsfile:', xlsfile)
        print('kvxls:refreshExcel:xlsfileabs:', xlsfileabs)
    logger.debug('xlsfile:', xlsfile)
    logger.debug('xlsfileabs:', xlsfileabs)
        
    Xlsx = win32com.client.DispatchEx('Excel.Application')
    Xlsx.DisplayAlerts = False
    Xlsx.Visible = True
    book = Xlsx.Workbooks.Open( xlsfileabs )
    # Refresh my two sheets
    book.RefreshAll()
    # this will actually wait for the excel workbook to finish updating
    Xlsx.CalculateUntilAsyncQueriesDone()
    book.Save()
    book.Close()
    Xlsx.Quit()
    del book
    del Xlsx    

if __name__ == '__main__':

    # put some quick test code here
    pass

#eof
