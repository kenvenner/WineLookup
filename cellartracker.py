'''
@author:   Ken Venner
@contact:  ken@venerllc.com
@version:  1.01

Update wine collection data with information from cellartracker

'''

import kvutil
import kvxls

import datetime
import re
import sys

# application variables
optiondictconfig = {
    'AppVersion' : {
        'value' : '1.01',
        'description' : 'defines the version number for the app',
    },
    'test' : {
        'value' : False,
        'type'  : 'bool',
        'description' : 'defines if we are running in test mode',
    },
    'verbose' : {
        'value' : 1,
        'type'  : 'int',
        'description' : 'defines the display level for print messages',
    },
    'wine_glob' : {
        'value' : 'Wine Collection *.xlsm',
        'description' : 'defines the file glob for the wine collection excel files',
    },
    'wine_file' : {
        'value' : None,
        'description' : 'defines the file name of the specific wine collection excel file to load',
    },
    'wine_sheetname' : {
        'value' : None,
        'description' : 'defines the work sheet to be updated',
    },
    'wine_sheets' : {
        'value' : ['Wine Collection', 'Villa-Collection'],
        'type' : 'liststr',
        'description' : 'defines the list of work sheets to be updated',
    },
    'wine_outfile_calc' : {
        'value' : True,
        'type' : 'bool',
        'description' : 'flag controlling if we generate a new output filename to save the output to',
    },
    'wine_outfile' : {
        'value' : None,
        'description' : 'defines the file name we will save output to if set',
    },
    'wine_outfile_none' : {
        'value' : False,
        'type' : 'bool',
        'description' : 'flag controlling if we exclude the generation of output file',
    },
    'ct_file' : {
        'value' : 'CellarTracker.xls',
        'description' : 'defines the filename of the cellar tracker file',
    },
    'ct_refresh' : {
        'value' : False,
        'type'  : 'bool',
        'description' : 'flag controlling if we refresh the data in the cellar tracker xls',
    },
    'chg_out' : {
        'value' : 'ct_change.csv',
        'description' : 'defines the filename of the file showing rows changed',
    },
    'pblm_out' : {
        'value' : 'ct_problem.csv',
        'description' : 'defines the filename of the file showing problem rows',
    },
}



# define how we are doing this
joinfields = {
    'ct_rating'    : {
        'delimiter' : ' ',
	'use_col'   : 1,
        'join_flds' : ['WA','WS','IWC','BH','AG','WE','JR','RH','JG','GV','JK','LD','CW','WFW','PR','SJ','WD','RR','JH','MFW','WWR','IWR','CHG','TT','TWF','DR','FP','JM','PG','WAL','CT'],
        'updt_fld'  : 'Rating',
    },
    'ct_range'     : {
        'delimiter' : '-',
        'join_flds' : ['End','Begin'],
        'fmt_flds'  : {'End':'{:.0f}','Begin':'{:.0f}','Vintage':'{:.0f}'},
        'sub_flds'  : {'Begin':'Vintage', 'End':'End'},
        'comp_blnk' : 'N/A',
        'updt_fld'  : 'DrinkRange',
    },
    'ct_winenew'     : {
        'delimiter' : ' ',
        'fmt_flds'  : {'Vintage':'{:.0f}'},
        'join_flds' : ['Wine','Vintage'],
    },
    'ct_reason'      : {
        'manual_gen': True,
        'updt_fld'  :  'Drink_Reason',
        'copy_over' : ['Cheap','Experiment','DrinkNow'],
    },
}


# load in the CellarTracker xls data
# pull out the winelist page
# add additional values to each record
# pass this dictionary keyed by CellarTracker # (iWine) back
#
def loadCTandHydrate( ct_xls_filename, joinfields, debug=False ):

    # load xls into a dictionary
    ct = kvxls.readxls2dict_findheader(ct_xls_filename,'iWine', optiondict={'col_header' : True, 'sheetname' : 'Wine List'}, debug=False)

    # step through these records and upate them with calced fiels
    for key in ct:
        addCTcalcFields( ct[key], joinfields, debug=debug )

    # return the dictionary we create
    return ct

# add additional attributes to the cellartracker data
# controlled mainly by the passed in dictionary
# key = new-field-to-add
# dictionary tied to key:
#    manual_gen - this is a calculated field - but is controlled in code
#    join_flds - list of field to concatenate from cellartracker to create the new field
#                if not set, then no new field is created in Cellartracker.
#    delimiter - string used to delimit the fields in join_flds
#    use_col - bool - says that the concatentation is the column name and value when populated
#    sub_flds - dictionary of field and its substitute field to use if there is no value in field.
#                 example - Begin is the field of interest, but if not populated, use the value
#                           in the vintage field as the value.
#    comp_blnk - string that the new field is set to if there were NO values from join_flds
#
#    updt_fld - field in the WineCollection field that this newly calculated value replaces
#    copy_over - when performing the hydration of wineColletion - if winecolletion field defined by
#                updt_fld has any of these values, do NOT change that setting, otherwise pull over
#                the cellar tracker value into winecollection
#    comp_fld - in the comparison phase - take these fields and validate they are the same and report
#               when they are not.
# 
def addCTcalcFields( rec, joinfields, debug=False ):
    # Create new fields by joining others
    for newfld, jf in joinfields.items():

        # if this field is not create by joining things  skip it
        if not 'join_flds' in jf:
            continue

        # calculate the new field value and capture it
        if 'use_col' in jf:
            rec[newfld] = jf['delimiter'].join([col+str(rec[col]) for col in jf['join_flds'] if rec[col]])
        elif 'fmt_flds' in jf:
            if debug:
                print('rec:',rec)
                print('jf:', jf)
            try:
                # here also - we are going to try to format but if we have a problem - we will just stringify it and deal with it later
                rec[newfld] = jf['delimiter'].join([str(rec[col]) if col not in jf['fmt_flds'] else rec[col] if not rec[col] else jf['fmt_flds'][col].format(rec[col]) for col in jf['join_flds'] if rec[col]])
            except:
                # failed to convert a float
                rec[newfld] = jf['delimiter'].join([str(rec[col]) for col in jf['join_flds'] if rec[col]])
        else:
            rec[newfld] = jf['delimiter'].join([str(rec[col]) for col in jf['join_flds'] if rec[col]])
                
        # if we got a value with out substitute
        # and we have enabled substituon for this field
        # we should recalculate this field with substitutes enabled
        if 'sub_flds' in jf and rec[newfld]:
            if debug:
                print('rec[newfld]:', rec[newfld])
            if 'fmt_flds' in jf:
                # cheating for now - going to force that if you have sub_flds you have to have fmt_flds also - which we do
                if debug:
                    print('col:', [col for col in jf['join_flds']])
                    print('fmt_flds:', [jf['fmt_flds'][col] for col in jf['join_flds']])
                    print('sub_flds:', [jf['sub_flds'][col] for col in jf['join_flds']])
                    print('fmt_flds-sub_flds:', [jf['fmt_flds'][jf['sub_flds'][col]] for col in jf['join_flds']])
                    print('rec[col]:', [rec[col] for col in jf['join_flds']])
                    print('rec[col] w subs:', [rec[col] if rec[col] else jf['sub_flds'][col] for col in jf['join_flds']])
                    print('rec[col]subs:', [rec[col] if rec[col] else rec[jf['sub_flds'][col]] for col in jf['join_flds']])
                # but we should really handle all cases - TODO
                try:
                    # we are going to try to do this all properly - but if we fail - we are going to just string it and live with what we get
                    rec[newfld] = jf['delimiter'].join([jf['fmt_flds'][col].format(rec[col]) if rec[col] else jf['fmt_flds'][jf['sub_flds'][col]].format(rec[jf['sub_flds'][col]]) for col in jf['join_flds']])
                except:
                    # it failed - one of the fields was not a float - so string it all to keep on moving.
                    rec[newfld] = jf['delimiter'].join([str(rec[col]) if rec[col] else str(rec[jf['sub_flds'][col]]) for col in jf['join_flds']])
                    
            else:
                rec[newfld] = jf['delimiter'].join([str(rec[col]) if rec[col] else str(rec[jf['sub_flds'][col]]) for col in jf['join_flds']])

        # if the fields were not populated and we want to set value when blank - set it
        if not rec[newfld] and 'comp_blnk' in jf:
            rec[newfld] = jf['comp_blnk']


    # hard coded field we added
    rec['ct_reason'] = ''

    # if this wine has an end date - we can caculate the dirnk reason
    if rec['End']:
        currentYear = datetime.datetime.now().year
        if rec['End'] < currentYear:
            rec['ct_reason'] = 'Expired'
        elif rec['End'] == currentYear:
            rec['ct_reason'] = 'Expiring'
        elif rec['End'] == currentYear+1:
            rec['ct_reason'] = 'Soon'
        elif rec['End'] == currentYear+2:
            rec['ct_reason'] = 'VerySoon'

# routine step through the winecollection and updates cells with values from cellartracker
def copyCTtoWineCollection(wcExcelDict, cellartracker, joinfields, debug=False):
    changedrows={}
    rowcnt=wcExcelDict['row_header']+1
    for row in range(wcExcelDict['start_row']+1, wcExcelDict['sheetmaxrow']):
        rowcnt += 1
        # extract out the lookup field - but make sure we get it as a string
        if debug:  print('row:', row)
        iWine = str(kvxls.getExcelCellValue(wcExcelDict, row, 'CellarTracker'))
        iWine2 = iWine + '.0'
        if debug:  print('iWine:', iWine)
        if debug:  print('iWine2:', iWine2)
        if iWine2 in cellartracker:
            iWine = iWine2
        if iWine in cellartracker:
            if debug:  print('in cellartracker')
            for ctFld, ctDict in joinfields.items():
                if debug:  print('ctFld:ctDict:', ctFld, ':', ctDict)
                if 'updt_fld' in ctDict:
                    curValue = kvxls.getExcelCellValue(wcExcelDict, row, ctDict['updt_fld'])
                    if 'copy_over' in ctDict and curValue in ctDict['copy_over']:
                        pass
                    else:
                        # capture the fields that have been changed
                        if curValue != cellartracker[iWine][ctFld]:
                            if rowcnt in changedrows:
                                changedrows[rowcnt].append(ctDict['updt_fld'])
                            else:
                                changedrows[rowcnt] = [ctDict['updt_fld']]
                        if debug:
                            print('updating wc fld:', ctDict['updt_fld'])
                            print('from ct fld:', ctFld)
                            print('new wine value:', cellartracker[iWine][ctFld])
                            if curValue != cellartracker[iWine][ctFld]:
                                print('values differ:current:', curValue)
                        kvxls.setExcelCellValue(wcExcelDict, row, ctDict['updt_fld'], cellartracker[iWine][ctFld])

    return changedrows


# routine step through the winecollection and updates cells with values from cellartracker
def inspectWineCollection(wcExcelDict, cellartracker, joinfields, debug=False):
    problemrows={}
    locationseen = {}
    locationdup = {}
    rowcnt=wcExcelDict['row_header']+1
    for row in range(wcExcelDict['start_row']+1, wcExcelDict['sheetmaxrow']):
        rowcnt += 1
        # extract out the lookup field - but make sure we get it as a string
        if debug:  print('row:', row)

        # do location tracking
        curLocation = kvxls.getExcelCellValue(wcExcelDict, row, 'Location')
        if curLocation in locationseen:
            if curLocation in locationdup:
                locationdup[curLocation].append(rowcnt)
            else:
                locationdup[curLocation] = [locationseen[curLocation], rowcnt]
        else:
            locationseen[curLocation] = rowcnt
            
        # determine the cellartracker key
        iWine = str(kvxls.getExcelCellValue(wcExcelDict, row, 'CellarTracker'))
        iWine2 = iWine + '.0'
        if debug:  print('iWine:', iWine)
        if debug:  print('iWine2:', iWine2)
        if iWine2 in cellartracker:
            iWine = iWine2
        # pull year from collection
        curValueYear = kvxls.getExcelCellValue(wcExcelDict, row, 'Year')
        if isinstance(curValueYear, float): curValueYear = int(curValueYear)
        # compare wine-collectino to cellartracker
        if iWine in cellartracker:
            if debug:  print('in cellartracker')
            
            # 1) Winery and Producer
            curValue = kvxls.getExcelCellValue(wcExcelDict, row, 'Winery')
            if curValue != cellartracker[iWine]['Producer']:
                # in test vs direct match
                if curValue not in cellartracker[iWine]['Producer']:
                    msg = 'Winery-Producer-Mismatch:wc:{}:ct:{}'.format(curValue, cellartracker[iWine]['Producer'])
                
                    if rowcnt in problemrows:
                        problemrows[rowcnt].append(msg)
                    else:
                        problemrows[rowcnt] = [msg]

            # 2) compare wc year to ct vintage
            ctValue = cellartracker[iWine]['Vintage']
            if isinstance(ctValue, float): ctValue = int(ctValue)
            # capture the fields that have been changed
            if curValueYear != ctValue:
                msg = 'Vintage-Mismatch:wc:{}:ct:{}'.format(curValueYear, ctValue)
                if rowcnt in problemrows:
                    problemrows[rowcnt].append(msg)
                else:
                    problemrows[rowcnt] = [msg]

        # compare wine-collection to itself

        # 1) Wine (year) to year
        curValueWine = str(kvxls.getExcelCellValue(wcExcelDict, row, 'Wine'))        
        x = re.search('\s(\d\d\d\d)', curValueWine)
        msg = None
        if x:
            if int(x.group(1)) != curValueYear:
                msg = 'Wine-Year-Mismatch:wine:{}:year:{}'.format(curValueWine, curValueYear)
        else:
            if not (isinstance(curValueYear,str) and curValueYear in ('N.V.')):
                msg = 'Wine-Year-Year:wine:{}:year:{}'.format(curValueWine, curValueYear)

        if msg:
            if rowcnt in problemrows:
                problemrows[rowcnt].append(msg)
            else:
                problemrows[rowcnt] = [msg]

    # ran through the complete page see if we have any locationdup
    if locationdup:
        highlightDups( wcExcelDict, locationdup, problemrows, debug=debug )
        
    return problemrows


# change the highlighting on cells - clear for not dupe, yellow for dups
#   Note:  we are modifying the content of the passed in array problemrows
def highlightDups( wcExcelDict, locationdup, problemrows, debug=False ):
    yellowFill = 'FFFFFF00'
    clearFill  = 'FFFFFFFF'
    
    if debug:  print('highlightDups:locationdup:', locationdup)

    # generate list of rows that are duplicates
    duprows = []
    rowlookup = {}
    for location, rows in locationdup.items():
        duprows.extend(rows)
        if not location:  location=''
        for row in rows:
            rowlookup[row] = ':'.join([location, *[str(row1) for row1 in rows]])

    # now step through all rows and set the patternfill
    rowcnt=wcExcelDict['row_header']+1
    for row in range(wcExcelDict['start_row']+1, wcExcelDict['sheetmaxrow']):
        rowcnt += 1
        # extract out the lookup field - but make sure we get it as a string
        if debug:  print('row:', row)

        if rowcnt in duprows:
            # highlight these cells
            kvxls.setExcelCellPatternFill(wcExcelDict, row, 'Location', yellowFill)
            msg = 'DUPS:{}'.format(rowlookup[rowcnt])
            if rowcnt in problemrows:
                problemrows[rowcnt].append(msg)
            else:
                problemrows[rowcnt] = [msg]
        else:
            # clear out any patternfill
            kvxls.setExcelCellPatternFill(wcExcelDict, row, 'Location', clearFill, fill_type=None)

# pass back the output filename to be used
def defineOutputFilename( in_file, out_file, new_file_flag ):
    if out_file:
        return out_file
    if new_file_flag:
        # increment the version number in the file
        # first pull out the current version number
        x = re.search('v(\d+)', in_file)
        if x:
            curver = x.group(1)
            fmtstring='{:0' + str(len(curver)) + 'd}'
            nextver = fmtstring.format(int(curver)+1)
            return re.sub(x.group(), 'v'+nextver, in_file)
        else:
            ext_idx = in_file.index('.')
            return in_file[:ext_idx] + '-v01' + in_file[ext_idx:]
    return out_file


def saveUpdates2File( worksheetupdates, chg_out, pblm_out, wc_file, ct_file ):
    # change file for all sheets
    with open( chg_out, 'w' ) as f:
        f.write( ','.join( ['row','worksheet','update_type','wc_file_input', 'ct_file', 'fields'] ) + '\n' )
        for (worksheet, chgdict, pblmdict) in worksheetupdates:
            for row in sorted(chgdict):
                f.write( ','.join([str(row),worksheet,'changes',wc_file,ct_file,*chgdict[row]]) + '\n' )
            
    # problem file for all sheets
    with open( pblm_out, 'w' ) as f:
        f.write( ','.join( ['row','worksheet','update_type','wc_file_input', 'ct_file', 'fields'] ) + '\n' )
        for (worksheet, chgdict, pblmdict) in worksheetupdates:
            for row in sorted(pblmdict):
                f.write( ','.join([str(row),worksheet,'problems',wc_file,ct_file,*pblmdict[row]]) + '\n' )
            

if __name__ == '__main__':
    # capture the command line
    optiondict = kvutil.kv_parse_command_line( optiondictconfig, debug=False )

    # determine what the winecolletion filename is
    if optiondict['wine_file']:
        # user specfied specific wine collection file to process
        wc_xls_filename = optiondict['wine_file']
    else:
        # get the largest file - as the wine collection to be loaded
        wc_xls_filename = kvutil.filename_maxmin( optiondict['wine_glob'], reverse=True )

    # define the output XLS/WineCollection filename
    wc_outfile = defineOutputFilename( wc_xls_filename, optiondict['wine_outfile'], optiondict['wine_outfile_calc'] )
    
    # define the sheets that we are processing
    worksheets=[]
    if optiondict['wine_sheetname']:
        worksheets=[optiondict['wine_sheetname']]
    elif optiondict['wine_sheets']:
        worksheets=optiondict['wine_sheets']
    else:
        print('wine_sheetname and wine_sheets not defined - program termination')
        sys.exit(1)
        

    # refresh cellartracker file if flag is set
    if optiondict['ct_refresh']:
        if optiondict['verbose']:  print('refreshing content in cellartracker file:', optiondict['ct_file'])
        import kvxlswin32
        kvxlswin32.refreshExcel( optiondict['ct_file'] )

    # Load up the data - 1) cellartracker
    ct_dict = loadCTandHydrate( optiondict['ct_file'], joinfields )

    # Load up the data - 2) wine collection
    wcExcelDict = kvxls.readxls_findheader( wc_xls_filename, [], optiondict={'col_header' : True, 'sheetname' : worksheets[0]}, data_only=False )

    worksheetupdates=[]
    
    # step through the defined set of sheets
    for worksheet in worksheets:
        # change to the sheet of interest and read the header
        wcExcelDict = kvxls.chgsheet_findheader( wcExcelDict,  [], optiondict={'col_header' : True, 'sheetname' : worksheet}, data_only=False )


        # map cellartracker to winecollection
        changedrows = copyCTtoWineCollection(wcExcelDict, ct_dict, joinfields )
    
        # capture problem rows
        problemrows = inspectWineCollection(wcExcelDict, ct_dict, joinfields )

        # capture data from this sheet
        worksheetupdates.append([worksheet,changedrows,problemrows])

    # save the output from this run - creating two files
    saveUpdates2File(worksheetupdates, optiondict['chg_out'], optiondict['pblm_out'], wc_xls_filename, optiondict['ct_file'])
    if optiondict['verbose']:
        print('Change log file:', optiondict['chg_out'])
        print('Problem log file:', optiondict['pblm_out'])
    
    # create output WineCollection unless flag is set to not create this file
    if not optiondict['wine_outfile_none']:
        kvxls.writexls( wcExcelDict, wc_outfile )
        if optiondict['verbose']:  print('Generated outputfile:', wc_outfile)
            
# eof
