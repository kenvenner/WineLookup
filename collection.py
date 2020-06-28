'''
@author:   Ken Venner
@contact:  ken@venerllc.com
@version:  1.21

All collection apps consolidated into this one app.

To run various apps - you need to specify the "runtype" on the command line
   runtype = rpt - create the collection.csv file used in generating daily reports
   runtype = updt - take the updated collection.csv file and put updates into collection_xref.csv
   runtype = xref - does the same thing as "updt"

 
Read in the recently updated collection.csv
Read in the existing mapping - collection2wine_xref.csv
Generate new entries from collection.csv into collection2wine_xref.csv
Save out the updated collection2wine_xref.csv

'''

import kvutil
import kvxls
import kvcsv

import datetime
import re
import sys

# application variables
optiondictconfig = {
    'AppVersion' : {
        'value' : '1.02',
        'description' : 'defines the version number for the app',
    },
    'debug' : {
        'value' : False,
        'type'  : 'bool',
        'description' : 'defines if we are running in test mode',
    },
    'verbose' : {
        'value' : 1,
        'type'  : 'int',
        'description' : 'defines the display level for print messages',
    },
    'runtype' : {
        'value' : 'rpt',
        'type'  : 'inlist',
        'valid' : ['rpt','updt','xref'],
        'description' : 'defines how we are processing this run',
    },

    
    'wine_glob' : {
        'value' : 'C:/Users/Public/Documents/Doc/Wine/Wine Collection *.xlsm',
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
        'value' : ['Wine Collection', 'Consumed On', 'Villa-Collection', 'Villa-Collection-Consumed', 'Liquor'],
        'type' : 'liststr',
        'description' : 'defines the list of work sheets to be updated',
    },
    'wine_sheets_active' : {
        'value' : ['Wine Collection', 'Villa-Collection', 'Liquor'],
        'type' : 'liststr',
        'description' : 'defines the list of work sheets to be updated',
    },

    'wine_xref_file' : {
        'value' : 'wine_xref.csv',
        'description' : 'defines the filename of wine name to winedescr',
    },

    'collection_xref_file' : {
        'value' : 'collection2wine_xref.csv',
        'description' : 'defines the filename of the cross reference collection to wine_xref',
    },

    'collection_file' : {
        'value' : 'collection.csv',
        'description' : 'defines the ouput filename of the collection',
    },
    'collection_out_file' : {
        'value' : None,
        'description' : 'overrides the ouput filename of the collection file in rpt mode',
    },
}

# ----------------- COMMON ----------------------------

def loadCollectionXrefDict( collection_xref_file, skipIgnore=False, debug=False ):
    # read in the file
    collection_xref_dict = kvcsv.readcsv2dict( collection_xref_file, ['name'] )

    # debugging
    if debug:  print('loadCollectionXrefDict:collection_xref_dict:', len(collection_xref_dict))

    # step through and cleanup the dictionary
    for wine, wineDict in collection_xref_dict.items():
        # skip this record if blank or is set to zzIgnore
        if skipIgnore and (wineDict['wine_xref'] or wineDict['wine_xref'] == 'zzIgnore'):
            if debug:  print('skipped wine:', wine)
            continue

        # check to see if first char is * - and remove it
        if wineDict['wine_xref'][:1] == '*':
            if debug: print('wine_xref - destarred:', wine)
            collection_xref_dict[wine]['wine_xref'] = wineDict['wine_xref'][1:]

    # return the results
    return collection_xref_dict



# -------------- COLLECTION XREF GENERATE ------------------------

def updateCollectionXrefDict( optiondict, debug=False ):

    # message what we are running
    if optiondict['verbose']:
        print('updateCollectionXrefDict')
        
    ### COLLECTION_XREF ###
    collection_xref = loadCollectionXrefDict( optiondict['collection_xref_file'], debug=debug )

    # messaging
    if optiondict['verbose']:  print('updateCollectionXrefDict:collection_xref:', len(collection_xref))


    ### COLLECTION ####
    collection = kvcsv.readcsv2dict( optiondict['collection_file'], ['name'] )
    for wine,value in collection.items():
        if value['wine_xref'][:1] == '*':
            if debug: print('collection - destarred:', wine)
            collection[wine]['wine_xref'] = value['wine_xref'][1:]
            
    # messaging
    if optiondict['verbose']:  print('updateCollectionXrefDict:collection:', len(collection))

    ### UPDATE  ###
    updates = updateCollectionXref( collection_xref, collection, debug=debug )

    ### OUTPUT ###
    fldlist = ['name','wine_xref']
    kvcsv.writedict2csv( optiondict['collection_xref_file'], collection_xref, fldlist )
    if optiondict['verbose']:
        print('updateCollectionXrefDict:Records updated:', updates)
        print('updateCollectionXrefDict:File created:', optiondict['collection_xref_file'])

    


def updateCollectionXref( collection_xref, collection, debug=False ):
    updates=0
    for wine in collection:
        if wine not in collection_xref:
            print('adding:', wine)
            collection_xref[wine] = {
                'name' :  collection[wine]['name'],
                'wine_xref' : collection[wine]['wine_xref'],
            }
            updates += 1
        elif collection_xref[wine]['wine_xref'] != collection[wine]['wine_xref']:
            print('updating:', wine)
            collection_xref[wine]['wine_xref'] = collection[wine]['wine_xref']
            updates += 1

    return updates


# ------------------ COLLECTION REPORT -----------------------

def genCollectionRpt( optiondict, debug=False ):

    # message what we are running
    if optiondict['verbose']:
        print('genCollectionRpt')
        
    ### WINE COLLECTION ###
    winecollection = loadWineCollection( optiondict, debug=debug )

    # messaging
    if optiondict['verbose']:  print('genCollectionRpt:winecollection:', len(winecollection))

    ### COLLECTION_XREF ###
    collection_xref = loadCollectionXrefDict( optiondict['collection_xref_file'], skipIgnore=True, debug=debug )

    # messaging
    if optiondict['verbose']:  print('genCollectionRpt:collection_xref:', len(collection_xref))

    ### WINE_XREF ###
    # wine_xref = kvcsv.readcsv2dict( optiondict['wine_xref_file'], ['winedescr'] )

    ### WINE_INV ###
    wine_inv = calcWineSummary( winecollection, collection_xref, optiondict, debug=debug )

    # set filename if not set
    if not optiondict['collection_out_file']:
        optiondict['collection_out_file'] =  optiondict['collection_file']
    # save this data out
    fldlist = ['name', 'cnt', 'price_min', 'price_avg', 'value', 'consumed', 'in_inv', 'wine_xref', 'total_spend', 'wine_type']
    kvcsv.writedict2csv( optiondict['collection_out_file'], wine_inv, fldlist )
    if optiondict['verbose']:
        print('genCollectionRpt:File created:', optiondict['collection_out_file'])

    

def loadWineCollection( optiondict, debug=False ):

    # determine what the winecolletion filename is
    if optiondict['wine_file']:
        # user specfied specific wine collection file to process
        wc_xls_filename = optiondict['wine_file']
    else:
        # get the largest file - as the wine collection to be loaded
        wc_xls_filename = kvutil.filename_maxmin( optiondict['wine_glob'], reverse=True )


    # define the sheets that we are processing
    worksheets=[]
    if optiondict['wine_sheetname']:
        worksheets=[optiondict['wine_sheetname']]
    elif optiondict['wine_sheets']:
        worksheets=optiondict['wine_sheets']
    else:
        print('wine_sheetname and wine_sheets not defined - program termination')
        sys.exit(1)

    # messaging
    if optiondict['verbose']:
        print('loadWineCollection:wc_xls_filename:', wc_xls_filename)
        print('loadWineCollection:worksheets:', worksheets)
        
    # load up all the records from this xls
    winecollection = []
    for worksheet in worksheets:
        if debug:  print('loadwineCollection:worksheet being loaded:', worksheet)
        data = kvxls.readxls2list_findheader( wc_xls_filename, [], optiondict={'col_header' : True, 'sheetname' : worksheet} )
        if debug:  print('loadwineCollection:records loaded:', len(data))
        for line in data:
            line['worksheet'] = worksheet
        winecollection.extend(data)

    # return the data
    return winecollection


def calcWineSummary( winecollection, collection_dict, optiondict, debug=False ):
    if debug:  print('calcWineSummary:winecollection:', len(winecollection))

    # Step through wines and create stats
    wine_inv = {}
    for wine in winecollection:
        # set the winename
        winename = ' '.join([wine['Winery'], wine['Wine']])

        if winename not in wine_inv:
            wine_inv[winename] = { 'name' : winename }

        if winename in collection_dict:
            wine_inv[winename]['wine_xref'] = collection_dict[winename]['wine_xref']
        else:
            wine_inv[winename]['wine_xref'] = ''

        wine_inv[winename]['wine_type'] = wine['Wine Type']

        if wine['Amount']:
            if not 'price_min' in wine_inv[winename]:
                wine_inv[winename]['price_min'] = wine['Amount']
            elif wine_inv[winename]['price_min'] > wine['Amount']:
                wine_inv[winename]['price_min'] = wine['Amount']
                
        if wine['worksheet'] in optiondict['wine_sheets_active']:
            sum2dict( wine_inv[winename], 'cnt', 1 )
            sum2dict( wine_inv[winename], 'value', wine['Amount'])
            wine_inv[winename]['in_inv'] = True
            if 'cnt' in wine_inv[winename] and 'value' in wine_inv[winename]:
                try:
                    wine_inv[winename]['price_avg'] = wine_inv[winename]['value']/wine_inv[winename]['cnt']
                except:
                    print('calcWineSummary:value:',  wine_inv[winename]['value'])
                    print('calcWineSummary:cnt:',  wine_inv[winename]['cnt'])

        else:
            sum2dict( wine_inv[winename], 'consumed', 1 )
            
        sum2dict( wine_inv[winename],'total_spend', wine['Amount'])

    return wine_inv



def sum2dict( updtdict, fld, amount ):
    if not amount:
        return
    if fld in updtdict:
        updtdict[fld] += amount
    else:
        updtdict[fld] = amount
        
        

if __name__ == '__main__':
    # capture the command line
    optiondict = kvutil.kv_parse_command_line( optiondictconfig, debug=False )

    debug = optiondict['debug']

    if optiondict['runtype'] in ('xref', 'updt'):
        updateCollectionXrefDict( optiondict, debug=debug )        
    elif optiondict['runtype'] in ('rpt'):
        genCollectionRpt( optiondict, debug=debug )
    else:
        print('unknown runtype:', optiondict['runtype'])
        
# eof
