'''
@author:   Ken Venner
@contact:  ken@venerllc.com
@version:  1.21

Library of tools used in general by KV
'''

import glob
import os
import datetime
import sys
import errno
from distutils.util import strtobool

# setup the logger
import logging
logger = logging.getLogger(__name__)

# set the module version number
AppVersion = '1.21'


# import ast
#   and call bool(ast.literal_eval(value)) 

# ken's command line processor (UT)
#   expects options defined as key=value pair strings on the command line
# input:
#   optiondictconfig - key = variable, value = dict with keys ( value, type, descr, required )
# return:
#   optiondict - dictionary of values from config and command line
#
# example:
# optiondictconfig = {
#     'AppVersion' : {
#         'value' : '1.01',
#     },
#     
#     'debug' : {
#         'value' : False,
#         'type' : 'bool',
#     },
#     'workingdir' : {
#         'required' : True,
#     }
# }
#
# optiondict = kv_parse_command_line( optiondictconfig )
#
#
def kv_parse_command_line( optiondictconfig, debug=False ):
    # debug
    if debug:  print('kv_parse_command_line:sys.argv:', sys.argv)
    if debug:  print('kv_parse_command_line:optiondictconfig:', optiondictconfig)
    
    # create the dictionary - and populate values
    optiondict = {}
    for key in optiondictconfig:
        if 'value' in optiondictconfig[key]:
            # the user specified a value value
            optiondict[key] = optiondictconfig[key]['value']
        else:
            # no value option - set to None
            optiondict[key] = None

    # possibly add in here some logging attributes that we can pass in
    # loglevel
    # logfile
    
    # read in the command line options that we care about
    for argpos in range(1,len(sys.argv)):
        # get the argument and split it into key and value
        (key,value) = sys.argv[argpos].split('=')

        # debug
        if debug:  print('kv_parse_command_line:sys.argv[',argpos,']:',sys.argv[argpos])

        # skip this if the key is not populated
        if not key:
            if debug:  print('kv_parse_command_line:key-not-populated-skipping-arg')
            continue
        
        # action on this command line
        if key in optiondict:
            if 'type' not in optiondictconfig[key]:
                # user did not specify the type of this option
                optiondict[key] = value
                if debug: print('type not in optiondictconfig[key]')
            elif optiondictconfig[key]['type'] == 'bool':
                optiondict[key] = bool(strtobool(value))
                if debug: print('type bool')
            elif optiondictconfig[key]['type'] == 'int':
                optiondict[key] = int(value)
                if debug: print('type int')
            elif optiondictconfig[key]['type'] == 'float':
                optiondict[key] = float(value)
                if debug: print('type float')
            elif optiondictconfig[key]['type'] == 'dir':
                optiondict[key] = os.path.normpath(value)
                if debug: print('type dir')
            elif optiondictconfig[key]['type'] == 'liststr':
                optiondict[key] = value.split(',')
                if debug: print('type liststr')
            elif optiondictconfig[key]['type'] == 'date':
                optiondict[key] = datetime_from_str( value )
                if debug: print('type date')
            else:
                # user set a type but we don't know what to do with this type
                optiondict[key] = value
                if debug: print('type not known')
        elif key == 'help':
            # user asked for help - display help and then exit
            kv_parse_command_line_display( optiondictconfig, debug=False )
            sys.exit()
        elif debug:
            print('kv_parse_command_line:unknown-option:', key)

    # test for required fields being populated
    missingoption = []
    for key in optiondictconfig:
        if 'required' in optiondictconfig[key]:
            if optiondictconfig[key]['required'] and optiondict[key] == None:
                # required field but is populated with None
                missingoption.append('%s:required field not populated' % key)
                optiondictconfig[key]['error'] = 'required value not populated'
    
    # raise error if we should
    if missingoption:
        kv_parse_command_line_display( optiondictconfig, debug=False )
        errmsg = 'System exitted - missing required option(s):\n    ' + '\n    '.join(missingoption)
        # print('\n'.join(missingoption))
        print('-'*80)
        print(errmsg)
        print('')
        raise Exception(errmsg)
        # sys.exit(1)
    
    # debug when we are done
    if debug:  print('kv_parse_command_line:optiondict:', optiondict)

    # return what we created
    return optiondict

# update the value of a two level deep key if it is not already set
def set_when_not_set( dict, key1, key2, value ):
    if key1 in dict:
        if key2 not in dict[key1]:
            dict[key1][key2] = value
            return True
    return False

# display the optiondictconfig information in human readable format
def kv_parse_command_line_display( optiondictconfig, optiondict={}, debug=False ):
    set_when_not_set( optiondictconfig, 'AppVersion', 'sortorder', 1 )
    set_when_not_set( optiondictconfig, 'debug', 'sortorder', 9999 )

    # predefined number ranges by type
    nextcounter = {
        'None' : 2,
        'dir' : 100,
        'int'  : 200,
        'float' : 300, 
        'bool' : 400,
        'date' : 500,
    }        

    opt2sort = []
    
    # step through the optional keys
    for opt in sorted( optiondictconfig.keys() ):
        if 'type' in optiondictconfig[opt]:
            # type set - use it
            typeupdate = optiondictconfig[opt]['type']
        else:
            # type not set - make it 'None'
            typeupdate = 'None'
        
        if set_when_not_set( optiondictconfig, opt, 'sortorder', nextcounter[typeupdate] ):
            # we updated the sort order for this record - so we must update the counter
            nextcounter[typeupdate] += 1

        # now build sort string
        opt2sort.append([optiondictconfig[opt]['sortorder'], opt])

    # step through the sorted list and display things
    for row in sorted(opt2sort):
        opt = row[1]
        if opt in optiondict:
            optiondictconfig[opt]['value'] = optiondict[opt]
        if 'type' in optiondictconfig[opt]:
            print('option.:', opt, ' (type:',optiondictconfig[opt]['type'], ')' )
        else:
            print('option.:', opt)

        for fld in ('value','required','description', 'error'):
            if fld in optiondictconfig[opt]:
                print('  ' + fld + '.'*(12-len(fld)) + ':', optiondictconfig[opt][fld])
        


# return the filename that is max or min for a given query (UT)
def filename_maxmin( file_glob, reverse=False ):
    # pull the list of files
    filelist = glob.glob( file_glob )
    # debugging
    logger.debug('filelist:%s', filelist)
    # if we got no files - return none
    if not filelist:
        logger.debug('return none')
        return None
    logger.debug('file:%s', sorted(filelist, reverse=reverse )[0])
    # sort this list - and return the desired value
    return sorted(filelist, reverse=reverse )[0]

# create a filename from part of a filename
def filename_create( filename=None, filepath=None, filename_base=None, filename_ext=None ):
    return True

# split up a filename into parts (path, basename, extension) (UT)
def filename_split( filename ):
    filename2, file_ext = os.path.splitext(filename)
    base_filename = os.path.basename(filename2)
    file_path     = os.path.normpath(os.path.dirname(filename2))
    return (file_path, base_filename, file_ext)


# create a full filename and optionally validate directory exists and is writeabile (UT)
def filename_proper( filename_full, dir=None, create_dir=False, write_check=False ):
    filename = os.path.basename( filename_full )
    if not dir:
        dir = os.path.dirname( filename_full )

    # if there is no directory then make it the current directory
    if not dir:
        dir = './'

    # wondering if we need to extract directory and compare if set (future feature) - and if they are different - what action should we take?

    # check the directory and determine if we need it to be created
    if not os.path.exists( dir ):
        # directory needs to be created
        if create_dir:
            # needs to be created and we have enabled this option
            try:
                os.makedirs( dir )
            except Exception as e:
                print('kvutil:filename_proper:makedirs:%s' % e)
                raise Exception('kvutil:filename_proper:makedirs:%s' % e)
        else:
            # needs to be created - option not enabled - raise an error
            print('kvutil:filename_proper:directory does not exist:%s' % dir )
            raise Exception('kvutil:filename_proper:directory does not exist:%s' % dir )

    # check to see if the directory is writeable if the flag is set
    if write_check:
        if not os.access( dir, os.W_OK ):
            print('kvutil:filename_proper:directory is not writeable:%s' % dir )
            raise('kvutil:filename_proper:directory is not writeable:%s' % dir )
    
    # build a full filename
    full_filename = os.path.join( dir, filename )
    
    # return the calculated filename
    return os.path.normpath(full_filename)



# create a unique filename
def filename_unique( filename=None, filename_href={} ):
    # check input
    if isinstance( filename, dict):
        filename_href = filename
        filename = None
        
    # default options for the filename_href
    default_options = {
	'file_ext'          : '.html',         # file extension
	'full_filename'     : '',
	'file_path'         : './',            # path to where to put the file
	'filename'          : '',
	'tmp_file_path'     : '',
	'base_filename'     : 'tmpfile',       # basefilename
	'ov_ext'            : '.bak',          # overwritten saved file extension
	'uniqtype'          : 'cnt',           # defines how we make this filename uniq
	'cntfmt'            : 'v%02d',         # format string for converting count
	'datefmt'           : '-%Y%m%d',       # format string for converting date
	'maxcnt'            : 100,             # maximum count to search for unique filename
	'forceuniq'         : False,           # do not force unique filename creation
	'overwrite'         : False,           # 1=overwrite an existing file
        'create_dir'        : False,           # if true - we will create the directory specified if it does not exist
        'write_check'       : True,            # validate we can write in the specified directory
	'verbose_uf'        : 0,
    }
    # list of required fields to be populated
    required_values = ['file_ext', 'file_path', 'base_filename', 'uniqtype']
    
    # list of valid values for inputs
    validate_values = {
        'uniqtype' : ['cnt', 'datecnt']
    }
    # force the value of this field if the value is blank
    force_if_blank = {
        'file_path' : './',
    }
                    

    # bring in the values that were passed in
    for key in default_options:
        if key in filename_href:
            default_options[key] = filename_href[key]

    # if filename is provided split it up
    if filename:
        default_options['file_path'], default_options['base_filename'], default_options['file_ext'] = filename_split(filename)
    else:
        # parse up the full_filename if passed in
        if default_options['full_filename']:
            default_options['file_path'], default_options['base_filename'], default_options['file_ext'] = filename_split(default_options['full_filename'])
        elif default_options['filename']:
            default_options['file_path'], default_options['base_filename'], default_options['file_ext'] = filename_split(default_options['filename'])
        else:
            # make sure base_filename is only a filename
            default_options['base_filename'] = os.path.basename(default_options['base_filename'])
            default_options['file_path']     = os.path.dirname(default_options['file_path'])
        

    # force if blank fields
    for key in force_if_blank:
        if not default_options[key]:
            default_options[key] = force_if_blank[key]

    # check that required fields are populated
    field_issues = []
    for key in required_values:
        if not default_options[key]:
            field_issues.append(key)

    # check to see if we have and field issues
    if field_issues:
        print('kvutil:filename_unique:missing values for:', ','.join(field_issues))
        raise Exception('kvutil:filename_unique:missing values for:', ','.join(field_issues))
    
    # check that we have valid values
    for key in validate_values:
        if not default_options[key] in validate_values[key]:
            field_issues.append(key)

    # check to see if we have and field issues
    if field_issues:
        print('kvutil:filename_unique:invalid values for:', ','.join(field_issues))
        raise Exception('kvutil:filename_unique:invalid values for:', ','.join(field_issues))

    # create a filename if it does not exist
    default_options['filename'] = os.path.normpath(os.path.join(default_options['base_filename'] + default_options['file_ext']))

    # check the directory to see if it exists
    default_options['file_path'] = filename_proper( default_options['file_path'], create_dir=default_options['create_dir'], write_check=default_options['write_check'] )

    # if we are NOT doing datecnt - then clear the date_file
    if default_options['uniqtype'] == 'cnt':
        date_file = ''
    else:
        date_file = datetime.datetime.now().strftime(default_options['datefmt'])
        
    # start the counter for file version number
    unique_counter = 1
    
    # set the starting filename
    if default_options['forceuniq']:
        # want a unique filename - create a filename base on the filename options
        filename = default_options['base_filename'] + date_file + (default_options['cntfmt'] % unique_counter) + default_options['file_ext']
    else:
        # not a unique - try the filename passed infirst
        filename = default_options['filename']

    # debugging
    #print('file_unique:filename:', filename)
    #print('file_unique:default_options:', default_options)

    # take action if we are not going to overwrite the filename
    if not default_options['overwrite']:

        # look for the filename that works
        while( os.path.exists( os.path.join( default_options['file_path'], filename ) ) and unique_counter < default_options['maxcnt'] ):
            # create a new filename
            filename = default_options['base_filename'] + date_file + (default_options['cntfmt'] % unique_counter) + default_options['file_ext']
            # increment the counter
            unique_counter += 1

        # test to see if we exceeded the max count and if so error out.
        if unique_counter >= default_options['maxcnt']:
          print('kvutil:filename_unique:reached maximum count and not unique filename:', filename)
          raise Exception('kvutil:filename_unique:reached maximum count and not unique filename:', filename)

    # debugging
    #print('file_unique:filename:final:', filename)

    # return the final filename
    return filename_proper( filename, dir=default_options['file_path'])
#, \
#           filename_proper( filename +  default_options['ov_ext'], dir=default_options['file_path'])
                                                                                          
  

# read a text file into a string (UT)
def slurp( filename ):
    with open( filename, 'r') as t:
        return t.read()

# read in a file and create a list of each populated line (UT)
def read_list_from_file_lines( filename, stripblank=False ):
    # read in the file as a list of strings
    with open( filename, 'r') as t:
        filelist = t.readlines()

    # strip the trailing \n
    filelist = [line.strip('\n') for line in filelist]
    
    # if they want to strip blank lines
    if stripblank:
        filelist = [line for line in filelist if line]
        
    # return the list of lines
    return filelist


# utility used to remove a filename - in windows sometimes we have a delay
# in releasing the filehandle - this routine will loop a few times giving
# time for the OS to release the blocking issue and then delete
#
# optional input:
#    callfrom - string used to display - usually the name of module.function()
#    debug - bool defines if we display duggging print statements
#    maxretry - int - number of times we try to delete and then give up (default: 20)
#
def remove_filename(filename,callfrom='',debug=False,maxretry=20):
    cnt=0
    if callfrom:  callfrom += ':'
    while os.path.exists(filename):
        cnt += 1
        if debug: print(callfrom, filename, ':exists:try to remove:cnt:', cnt)
        try:
            os.remove(filename) # try to remove it directly
#        except OSError as e: # originally just checked for OSError - we now check for all exceptions`
        except Exception as e:
            if debug: print(callfrom, 'errno:', e.errno, ':ENOENT:', errno.ENOENT)
            if e.errno == errno.ENOENT: # file doesn't exist
                return
            if debug: print(callfrom, filename,':', str(e))
            if cnt > maxretry:
                print(callfrom, filename, ':raise error - exceed maxretry attempts:', maxretry)
                raise e
        except WinError as f:
            print('catch WinError:', str(f))

# utility used to remove a folder - in windows sometimes we have a delay
# in releasing the filehandle - this routine will loop a few times giving
# time for the OS to release the blocking issue and then delete
#
# optional input:
#    callfrom - string used to display - usually the name of module.function()
#    debug - bool defines if we display duggging print statements
#    maxretry - int - number of times we try to delete and then give up (default: 20)
#
def remove_dir(dirname,callfrom='',debug=False,maxretry=20):
    cnt=0
    if callfrom:  callfrom += ':'
    while os.path.exists(dirname):
        cnt += 1
        if debug: print(callfrom, dirname, ':exists:try to remove:cnt:', cnt)
        try:
            os.rmdir(dirname) # try to remove it directly
#        except OSError as e: # originally just checked for OSError - we now check for all exceptions`
        except Exception as e:
            if debug: print(callfrom, 'errno:', e.errno, ':ENOENT:', errno.ENOENT)
            if e.errno == errno.ENOENT: # file doesn't exist
                return
            if debug: print(callfrom, dirname,':', str(e))
            if cnt > maxretry:
                print(callfrom, dirname, ':raise error - exceed maxretry attempts:', maxretry)
                raise e
        except WinError as f:
            print('catch WinError:', str(f))


# extract out a datetime value from a string if possible
# formats currently supported:
#  m/d/y
#  m-d-y
#  YYYY-MM-DD
#  YYYYMMDD
#
def datetime_from_str( value ):
    import re
    datefmts = (
        ( re.compile('\d{1,2}\/\d{1,2}\/\d\d$'), '%m/%d/%y' ),
        ( re.compile('\d{1,2}\/\d{1,2}\/\d\d\d\d$'), '%m/%d/%Y' ),
        ( re.compile('\d{1,2}-\d{1,2}-\d\d$'), '%m-%d-%y' ),
        ( re.compile('\d{1,2}-\d{1,2}-\d\d\d\d$'), '%m-%d-%Y' ),
        ( re.compile('\d{4}-\d{1,2}-\d{1,2}$'), '%Y-%m-%d' ),
        ( re.compile('^\d{8}$'), '%Y%m%d' ),
    )

    for (redate, datefmt) in datefmts:
        if redate.match(value):
            return datetime.datetime.strptime(value, datefmt)

    raise



# create the starting logger header that we want to show the separation
# between runs - this utility is just to enable logging standardization.
#
# In your program put:  kvutil.loggingAppStart( logger, optiondict, kvutil.scriptinfo()['name'] )
#
def loggingAppStart(logger,optiondict,pgm=None):
    logger.info('-----------------------------------------------------')
    if pgm:
        logger.info('%s:AppVersion:v%s', pgm, optiondict['AppVersion'])
    else:
        logger.info('AppVersion:v%s', optiondict['AppVersion'])


def scriptinfo():
    '''
    Returns a dictionary with information about the running top level Python
    script:
    ---------------------------------------------------------------------------
    dir:    directory containing script or compiled executable
    name:   name of script or executable
    source: name of source code file
    ---------------------------------------------------------------------------
    "name" and "source" are identical if and only if running interpreted code.
    When running code compiled by py2exe or cx_freeze, "source" contains
    the name of the originating Python script.
    If compiled by PyInstaller, "source" contains no meaningful information.
    '''

    import os, sys, inspect
    #---------------------------------------------------------------------------
    # scan through call stack for caller information
    #---------------------------------------------------------------------------
    trc=''
    for teil in inspect.stack():
        # skip system calls
        if teil[1].startswith("<"):
            continue
        if teil[1].upper().startswith(sys.exec_prefix.upper()):
            continue
        trc = teil[1]
        
    # trc contains highest level calling script name
    # check if we have been compiled
    if getattr(sys, 'frozen', False):
        scriptdir, scriptname = os.path.split(sys.executable)
        return {"dir": scriptdir,
                "name": scriptname,
                "source": trc}

    # from here on, we are in the interpreted case
    scriptdir, trc = os.path.split(trc)
    # if trc did not contain directory information,
    # the current working directory is what we need
    if not scriptdir:
        scriptdir = os.getcwd()

    scr_dict ={"name": trc,
               "source": trc,
               "dir": scriptdir}
    return scr_dict

# eof
