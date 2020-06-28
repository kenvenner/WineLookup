'''
@author:   Ken Venner
@contact:  ken@venerllc.com
@version:  1.05

Read the CSV file output from a wine search
Remove records tagged as "delete"
Dedup records - based on process_date, wine_store and wine_name
Create/append remaining records to the defined output file

'''

import kvutil
import kvcsv

import time
import re
import datetime
import sys
import os


# application variables
optiondictconfig = {
    'AppVersion' : {
        'value' : '1.05',
        'description' : 'defines the version number for the app',
    },
    'test' : {
        'value' : False,
        'type'  : 'bool',
        'description' : 'defines if we are running in test mode',
    },
    'debug' : {
        'value' : False,
        'type'  : 'bool',
        'description' : 'defines if we are running in debug mode',
    },
    'verbose' : {
        'value' : 1,
        'type'  : 'int',
        'description' : 'defines the logging/messaging level  we are running at',
    },
    'file_input' : {
        'value' : 'wineselenium.csv',  ##'winesrch.csv',
        'description' : 'defines the name of the wine file we are reading in',
    },
    'file_output' : {
        'value' : 'wineselenium-new.csv', ## winesrch.new',
        'description' : 'defines the name of the wine file we output to',
    },
    'rename_flag' : {
        'value' : False,
        'type'  : 'bool',
        'description' : 'defines if we rename the input file after we are doing procesing',
    },
    'rename_ext' : {
        'value' : '.bak',
        'description' : 'defines the file extension we rename to',
    },
    'rename_file' : {
        'value' : None,
        'description' : 'defines the full filename we rename to',
    },
    'append_flag' : {
        'value' : False,
        'type'  : 'bool',
        'description' : 'defines if we are appending to the output file',
    },
    'file_append' : {
        'value' : None,
        'type'  : 'bool',
        'description' : 'legacy value - remapped to append_flag',
    },
    'file_del' : {
        'value' : 'winedel.csv',
        'description' : 'defines the name of the wine file defining what to delete',
    },
    'del_flag' : {
        'value' : True,
        'type'  : 'bool',
        'description' : 'defines if we are filtering based on definition in file_del',
    },
    'delreckey' : {
        'value' : ['wine_store','wine_name'],
        'type'  : 'liststr',
        'description' : 'defines the column names used to create a unique record in file_del',
    },
    'delencoding' : {
        'value' : 'LATIN-1',
        'description' : 'defines the file encoding to read the del file with',
    },
    'inputencoding' : {
        'value' : 'LATIN-1',
        'description' : 'defines the file encoding to read the del file with',
    },
    'inputreckey' : {
        'value' : ['process_date','wine_store','wine_name'],
        'type'  : 'liststr',
        'description' : 'defines the column names used to create a unique record in file_input',
    },
    'inputheader' : {
        'value' : ['process_date','search','wine_store','wine_name','wine_price'],
        'type'  : 'liststr',
        'description' : 'defines the column names for the input file when no header exists',
    },
    'dellastseenfld' : {
        'value' : 'last_seen',
        'description' : 'defines the column name defining last seen in the file_del',
    },
    'inputdatefld' : {
        'value' : 'process_date',
        'description' : 'defines the column name defining the process_date field in the file_input',
    },
    'headerlc' : {
        'value' : True,
        'type'  : 'bool',
        'description' : 'defines if we should force headers to lower case',
    },
}


def rename_file( orig_filename, rename_ext='bak', rename_filename=None, debug=False ):
    if not rename_ext:
        rename_ext = 'bak'
    if not rename_filename:
        # filename with no extension
        rename_filename = os.path.splitext(orig_filename)[0]

        # Add the extension
        if not rename_ext.startswith('.'):
            rename_file += '.'
        rename_filename += rename_ext

    if os.path.exists(rename_filename):
        # remove file
        kvutil.remove_filename(rename_filename)

    # move the file to the rename filename
    os.rename(orig_filename, rename_filename)
    

def load_and_process_files( file_input, file_del, del_flag, delreckey, delencoding, inputreckey, inputencoding, dellastseenfld, inputdatefld, inputheader=None, headerlc=False, debug=False ):

    if debug:
        print('file_del:', file_del)
        print('delreckey:', delreckey)
        

    # first read in the file_del - into a dictionary that is wine_store+wine_name keyed
    delRecs, delDictKeys, delDupCount = kvcsv.readcsv2dict_with_header( file_del, delreckey, headerlc=headerlc, encoding=delencoding, debug=debug)

    if debug:
        #print('delRecs:', delRecs)
        print('delDictKeys:', delDictKeys)
        print('delDupCount:', delDupCount)
        
    if debug:
        print('file_input:', file_input)
        print('inputreckey:', inputreckey)
        print('inputheader:', inputheader)
        
    # load the input file keyed by the process_date, wine_store, wine_name
    if inputheader:
        inputRecs, inputDictKeys, inputDupCount  = kvcsv.readcsv2dict_with_noheader( file_input, inputreckey, header=inputheader, encoding=inputencoding, debug=debug)
    else:
        inputRecs, inputDictKeys, inputDupCount  = kvcsv.readcsv2dict_with_header( file_input, inputreckey, headerlc=headerlc, encoding=inputencoding, debug=debug)

    # calc the number of input records we processed
    inputRecCount = len(inputRecs) + inputDupCount
    
    if debug:
        # print('inputRecs:', inputRecs)
        print('inputDictKeys:', inputDictKeys)
        print('inputDupCount:', inputDupCount)

    # set the variables
    delRecCount = 0
    
    # step through input records and see if the match a delete entry
    for inputkey in list(inputRecs.keys()):
        # built up the store + name key from the process_date + store + name key
        storename = '|'.join(inputkey.split('|')[1:])
        # debugging
        if 0 and debug:
            print('storename:', storename, ':inputkey:', inputkey)
        # if this is a match
        if storename in delRecs:
            if 0 and debug:
                print('match to be deleted:', storename, ':', inputkey)
                
            # update the last seen field in delRecs
            delRecs[storename][dellastseenfld] = inputRecs[inputkey][inputdatefld]
            # count this delete
            delRecCount += 1
            # remove the record
            del inputRecs[inputkey]

    # if we deleted records - then we updated file_del and we need to save it
    if delRecCount:
        if 0 and debug:
            print('saving updates into:', file_del)
        kvcsv.writedict2csv( file_del, delRecs, delDictKeys, encoding=delencoding, debug=debug )

    ### TODO - replace dict returned with a list of values - not sure why i had to return it this way
    # return what we just extracted
    return {'inputRecs' : inputRecs, 'inputDictKeys' : inputDictKeys, 'inputDupCount' : inputDupCount, 'delRecCount' : delRecCount, 'inputRecCount' : inputRecCount }

# ---------------------------------------------------------------------------
if __name__ == '__main__':

    # capture the command line
    optiondict = kvutil.kv_parse_command_line( optiondictconfig, debug=False )

    # extract the values and put into variables
    test    = optiondict['test']
    AppVersion = optiondict['AppVersion']

    # dump out what we have done here
    if test:
        print ('---------------TEST FLAG ENABLED---------------------------')


    # check to see if we passed in srchlist instead of srchstring
    if optiondict['file_append']:
        print('file_append was passed in INSTEAD of append_flag - substituting')
        optiondict['append_flag'] = optiondict['file_append']
    

    # load and process the files
    results = load_and_process_files( optiondict['file_input'], optiondict['file_del'], optiondict['del_flag'], optiondict['delreckey'], optiondict['delencoding'], optiondict['inputreckey'], optiondict['inputencoding'], optiondict['dellastseenfld'], optiondict['inputdatefld'], inputheader=optiondict['inputheader'], headerlc=optiondict['headerlc'], debug=False )

    # output what we just got in
    if optiondict['append_flag']:
        kvcsv.writedict2csv( optiondict['file_output'], results['inputRecs'], results['inputDictKeys'], mode='a', header=False, encoding=optiondict['inputencoding'], debug=False )
    else:
        kvcsv.writedict2csv( optiondict['file_output'], results['inputRecs'], results['inputDictKeys'], encoding=optiondict['inputencoding'], debug=False )

    if optiondict['rename_flag']:
        rename_file(optiondict['file_input'], optiondict['rename_ext'], optiondict['rename_file'])

    # final summary
    print('wine_dedupe.py: Results--------------------------')
    print('Input file....:', optiondict['file_input'])
    print('Del file......:', optiondict['file_del'])
    print('Output file...:', optiondict['file_output'])
    print('Append flag...:', optiondict['append_flag'])
    print('Input records.:', results['inputRecCount'])
    print('Dup records...:', results['inputDupCount'])
    print('Del records...:', results['delRecCount'])
    print('Output records:', len(results['inputRecs']))
    
