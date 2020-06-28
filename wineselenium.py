'''
@author:   Ken Venner
@contact:  ken@venerllc.com
@version:  1.157

Using Selenium and Chrome/Firefox - screen scrape wine websites to draw
down wine pricing and availiability information

'''

from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException

import requests

import kvutil
import kvgmailsend

import time
import re
import datetime
import sys


# logging - 
import kvlogger
config=kvlogger.get_config(kvutil.filename_log_day_of_month(__file__, ext_override='log'), 'logging.FileHandler')
kvlogger.dictConfig(config)
logger=kvlogger.getLogger(__name__)

# added logging feature to capture and log unhandled exceptions
def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

sys.excepthook = handle_exception


# application variables
optiondictconfig = {
    'AppVersion' : {
        'value' : '1.157',
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
        'description' : 'defines the display level for print messages',
    },
    'srchstring' : {
        'value' : None,
        'description' : 'defines the name of the wine to search for when in test mode',
    },
    'srchstring_list' : {
        'value' : None,
        'type'  : 'liststr',
        'description' : 'defines the list of wine to search for when in test mode',
    },
    'srchlist' : {
        'value' : None,
        'description' : 'mistaken command line for srchstring',
    },
    'storelist' : {
        'value' : None,
        'description' : 'defines the name of the store we are querying - only when testing',
    },
    'store_list' : {
        'value' : None,
        'description' : 'mistaken command line for storelist',
    },
    'wineoutfile' : {
        'value' : 'wineselenium.csv',
        'description' : 'defines the name of the output file created',
    },
    'wineinputfile' : {
        'value' : 'getwines.bat',
        'description' : 'defines the name of the input file defining wines to lookup',
    },
    'winexlatfile' : {
        'value' : 'wine_xlat.csv',
        'description' : 'defines the name of the input file for translating wine names',
    },

    # Email notifications built into the application
    'EmailFromAddr' : {
        'value' : 'wines@vennerllc.com',
        'description' : 'defines the email account used to send out notifications',
    },
    'EmailFromPassword' : {
        'value' : '',
        'description' : 'defines the password used to log into the EmailFromAddr account',
    },
    'EmailToAddr' : {
        'value' : 'ken@vennerllc.com',
        'description' : 'defines the list of email addresses we are notifying',
    },
    'EmailSubject' : {
        'value' : 'Wine Processing Update - Total Wines Robot Interaction Required',
        'description' : 'defines the subject line of the email',
    },
    'EmailBody' : {
        'value' : 'Please RDP into the machine and interact with TotalWines web page to get past robot detection',
        'description' : 'defines the body of the email',
    },

    # control the type of browser we are using to do the automation
    'browser' : {
        'value' : 'chrome',
        'description' : 'defines which browser we are using to automate with',
    },

}

# define if we are running in test mode
test=False

# global variable - rundate set at strat
datefmt       = '%m/%d/%Y'
rundate       = datetime.datetime.now().strftime(datefmt)
AppVersion    = 'NotSet'
wineoutfile   = 'wineselenium.csv'
wineinputfile = 'getwines.bat'  #overwritten later
winexlatfile  = 'wine_xlat.csv' #overwritten later
verbose       = 1

rtnrecfmt     = '%s:returned records:%s'

# cause print statements that are not debugging statements to print out
pmsg          = False

store_wine_lookup = {}


# global variable as we need to figure out at run time which to use
pavillions_search_xpath = ''

# define the brower to use (chrome or firefox)
browser = 'chrome'

# --- FILE ROUTINES --------------------

# -- read in the list of wines
def get_winelist_from_file( getwines_file, debug=False ):
    # get the results
    searchlist = []

    # debugging
    if pmsg: print('wineselenium.py:get_winelist_from_file:', getwines_file)
    logger.info('getwines_file:%s', getwines_file)

    # open file and process
    with open(getwines_file, 'r') as fp:
        # for each line in the file see if it matches a regex of interest
        for line in fp:
            # debugging
            if debug:  print('wineselenium.py:get_winelist_from_file:line:',line)
            logger.debug('line:%s', line)
            # regex #1 match
            m=re.match('perl\s+findwine.pl\s+search="([^"]*)"\s', line)
            # if that did not match - try regex #2 match
            if not m:
                m=re.match('perl\s+findwine.pl\s+search=([^\s]*)\s', line)
               
            # test to see if we got a match on any regext
            if m:
                # extract out the match which is the wine
                searchlist.append(m.group(1))
                # debugging
                if debug:  print('wineselenium.py:get_winelist_from_file:added to wine list:',m.group(1))
                logger.debug('added to wine list:%s', m.group(1))
                

    # return the list we found
    return searchlist

# take from the list of wines we need to process - remove those already processed
def remove_already_processed_wines( winefile, searchlist, debug=False):
    global verbose

    # create the hash that captures what we have seen and not seen already
    seen_wines = []

    # messaging
    if pmsg: print('wineselenium.py:remove_already_processed_wines:winefile:', winefile)
    logger.info('winefile:%s',winefile)
    logger.debug('rundate:%s', rundate)
    logger.debug('srchlist:%s', searchlist)
    
    # debugging
    if debug:
        if pmsg: print('wineselenium.py:remove_already_processed_wines:rundate:', rundate)
        if pmsg: print('wineselenium.py:remove_already_processed_wines:srchlist:', searchlist)

    # put try loop in to deal with case when file does not exist
    try:
        # open the file and process it
        with open(winefile, 'r') as fp:
            for line in fp:
                # split up this csv
                elem = line.split(',')
                # check to see if this record is for todays run
                if elem[0] == rundate:
                    # check to see if we have seen this wine
                    if not elem[1] in seen_wines:
                        # has not been seen
                        # check to see if this wine is in the list we are processing and if so remove it
                        if elem[1] in searchlist:
                            # remove it from the search list
                            searchlist.remove(elem[1])
                            # now add this to the list of seen wines
                            seen_wines.append(elem[1])
    except:
        # just move on
        if verbose:
            if pmsg: print('wineselenium.py:remove_already_processed_wines:', winefile, ':does not exist-no wines removed from processing list')
        logger.warning('winefile does not exist:%s', winefile)
        
    # log informaton
    if pmsg: print('wineselenium.py:remove_already_processed_wines:wines_removed_already_processed:', seen_wines)
    if pmsg: print('wineselenium.py:remove_already_processed_wines:remaining_wines_to_search:', searchlist)
    logger.info('wines_removed_already_processed:%s', seen_wines)
    logger.info('remaining_wines_to_search:%s', searchlist)
    
    # return the pruned list
    return searchlist

# read in the translation file from store/wine to store/wine with vintage
def read_wine_xlat_file( getwines_file, debug=False ):
    # we are populating the module level variable that will be used by other functions in this module
    #
    # Module level variable:
    # store_wine_lookup = {}
    
    # open file and process
    with open(getwines_file, 'r') as fp:
        # for each line in the file see if it matches a regex of interest
        for line in fp:
            elem = line.split(',')
            if elem[0] not in store_wine_lookup.keys():
                # never seen store = build the entity in entirity
                store_wine_lookup[elem[0]] = { elem[1] : elem[2] }
            else:
                # seen the store check next level down
                if elem[1] in store_wine_lookup[elem[0]].keys():
                    # debugging
                    if debug:
                        if pmsg: print('read_wine_xlat_file:',elem[0],':',elem[1],' mapping changed from (', store_wine_lookup[elem[0]][elem[1]], ') to (', elem[2], ')')
                    logger.debug('%s:%s:mapping changed from:%s:to:%s',elem[0],elem[1], store_wine_lookup[elem[0]][elem[1]], elem[2])
                # set the value no matter what
                store_wine_lookup[elem[0]][elem[1]] = elem[2]
            
    # return
    return store_wine_lookup


# now convert a wine name to appropriate translatoin
def xlat_wine_name( store_wine_lookup, store, wine ):
    global verbose
    
    # check for a match based on the passed in name
    if store in store_wine_lookup.keys():
        # debugging
        logger.debug('store matched:%s', store)
        logger.debug('store list of wines:%s', store_wine_lookup[store])
        if wine in store_wine_lookup[store].keys():
            # debugging
            logger.debug('wine matched:%s', wine)
            return store_wine_lookup[store][wine]

    # did not find a match based on the wine name passed in
    # regex the name field to remove any commas
    # and try again
    if re.search(',', wine):
        # debugging
        logger.debug('comma in wine:%s',wine)
        wine = re.sub(',',' ',wine)
        # debugging
        logger.debug('comma stripped wine:%s',wine)
    
    # pass back the wine passed in (cleaned up)
    return wine



# -- output file
def save_wines_to_file(file, srchstring, winelist, debug=False):
    global verbose
    
    # module level variables used:
    #   store_wine_lookup - created by call to read_wine_xlat_file


    # debugging
    if debug:
        if pmsg: print('wineselenium.py:save_wines_to_file:file:', file)
        if pmsg: print('wineselenium.py:save_wines_to_file:srchstring:', srchstring)
        if pmsg: print('wineselenium.py:save_wines_to_file:len(winelist):', len(winelist))
    logger.debug('file:%s', file)
    logger.debug('srchstring:%s', srchstring)
    logger.debug('len(winelist):%d', len(winelist))


#    # column headings
#    column_headings = [
#        'rundate','srchstring',
#        'wine_store',      'wine_name',   'wine_price', 'wine_year',
#        'wine_type',       'wine_region', 'wine_size',  'wine_score',
#        'wine_case_price', 'wine_avail',  'wine_descr'
#    ]

    # open the file
    with open( file, 'a' ) as winecsv:
        # move through each row
        for rec in winelist:
            # check to see this was not no results
            if (rec['wine_price'] != 0):
                # make sure the wine price has no comma's in it
                # regex the name field to remove any commas
                if re.search(',', rec['wine_price']):
                    # debugging
                    logger.debug('comma in price:%s',rec['wine_price'])
                    # strip out the comma in price if it exists (might wnat to get rid of this)
                    rec['wine_price'] = re.sub(',','',rec['wine_price'])
                    # debugging
                    logger.debug('comma stripped price:%s',rec['wine_price'])
                
                # save - but also convert the wine name if there is a translation
                winecsv.write(','.join([rundate,srchstring,rec['wine_store'],xlat_wine_name(store_wine_lookup,rec['wine_store'],rec['wine_name']),rec['wine_price']])+"\n")
            else:
                # debugging
                logger.info('no wine price for:%s:%s', rec['wine_store'], rec['wine_name'])

    # debugging
    logger.info('saved records for:%s:%d', srchstring, len(winelist))
                
# routine that saves the current browser content to a file
def saveBrowserContent( driver, filenametemplate, function ):
    # save the page content in HTML file
    filename = kvutil.filename_unique( 'fail' + filenametemplate + '.html', {'uniqtype': 'datecnt', 'forceuniq' : True } )
    with open( filename, 'wb' ) as p:
        p.write( driver.page_source.encode('utf-8') )
    logger.info('%s:saved html page content to:%s', function, filename)

    # save the page picture in a PNG file
    filename = kvutil.filename_unique( 'fail' + filenametemplate + '.png', {'uniqtype': 'datecnt', 'forceuniq' : True } )
    driver.save_screenshot(filename)
    logger.info('%s:saved page screen shot to:%s', function, filename)


# except print 
def exceptionPrint ( e, msg, msg2, saveBrowser=False, driver=None, filename=None, msg3=None, exitPgm=False, debug=False):
        if pmsg: print(msg + ':' + msg2)
        if pmsg: print(msg + ':type:', type(e))
        if pmsg: print(msg + ':args:', e.args)
        logger.error('%s:%s', msg, msg2)
        logger.error('%s:type:%s', msg, type(e))
        logger.error('%s:args:%s', msg, e.args)
        
        if saveBrowser:
            if not driver:
                if pmsg: print(msg + ':exceptionPrint:saveBrowser:no-driver-passed-in:'+msg2)
                logger.error('%s:saveBrowser:no-driver-passed-in:', msg, msg2)
                return
            elif not filename:
                if pmsg: print(msg + ':exceptionPrint:saveBrowser:no-filename-passed-in:'+msg2)
                logger.error('%s:saveBrowser:no-filename-passed-in:', msg, msg2)
                return
            if not msg3:
                msg3 = msg + ':' + msg2
            saveBrowserContent( driver, filename, msg3)
        if exitPgm:
            if pmsg: print(msg + ':exiting program due to error')
            logger.error('%s:exiting program due to error', msg)
            exitWithError()


# get the requested URL - allow loopcnt number of tries
def get_url_looped( driver, url, msg, loopcnt=4, waitsecs=1, displayFailure=True, debug=False ):
    while loopcnt:
        try:
            driver.get(url)
            return True
        except Exception as e:
            if displayFailure:
                if pmsg: print(msg+':loopcnt:', loopcnt)
                if pmsg: print(msg+':unable to get:'+url)
                if pmsg: print(msg+':str:', str(e))
                if pmsg: print(msg+':type:', type(e))
                if pmsg: print(msg+':args:', e.args)

                logger.info('%s:loopcnt:%s', loopcnt)
                logger.info('%s:unable to get:%s', url)
                logger.info('%s:str:%s', str(e))
                logger.info('%s:type:%s', type(e))
                logger.info('%s:args:%s', e.args)
            loopcnt -= 1
            time.sleep(waitsecs)

# attempt to find a set of elements in a page
def find_elements_looped(driver, name, byType, msg, msg2, loopcnt=4, waitsecs=3, displayFailure=True, debug=False ):
    if byType in ('by_class_name', 'byClassName', 'class_name', 'className'):
        results = driver.find_elements_by_class_name( name )
    elif byType in ('by_name', 'byName', 'name'):
        results = driver.find_elements_by_name( name )
    elif byType in ('by_xpath', 'byXpath', 'xpath'):
        results = driver.find_elements_by_xpath( name )
    elif byType in ('by_id', 'byID', 'id'):
        results = driver.find_elements_by_id( name )

    while not results and loopcnt:
        if displayFailure:
            logger.info('%s:%s:%s:%d',msg,msg2,name,loopcnt)
        loopcnt -= 1
        time.sleep(waitsecs)

        if byType in ('by_class_name', 'byClassName', 'class_name', 'className'):
            results = driver.find_elements_by_class_name( name )
        elif byType in ('by_name', 'byName', 'name'):
            results = driver.find_elements_by_name( name )
        elif byType in ('by_xpath', 'byXpath', 'xpath'):
            results = driver.find_elements_by_xpath( name )
        elif byType in ('by_id', 'byID', 'id'):
            results = driver.find_elements_by_id( name )

    return results


# ---------------------------------------------------------------------------

# dump out an HTML element additional data
def print_html_elem( msg, index, elem):
    if pmsg: print('-----------------------------------------')
    if pmsg: print('index:', index)
    if pmsg: print(msg, ' class:', elem.get_attribute('class'))
    if pmsg: print(msg, ' type:', elem.get_attribute('type'))
    if pmsg: print(msg, ' id:', elem.get_attribute('id'))
    if pmsg: print(msg, ' parentElement:', elem.get_attribute('parentElement'))
    if pmsg: print(msg, ' outerHTML:', elem.get_attribute('outerHTML'))
    if pmsg: print(msg, ' text:', elem.get_attribute('text'))
    if pmsg: print(msg, ' displayed:', elem.is_displayed())
    if pmsg: print(msg, ' location:', elem.location)
    if pmsg: print(msg, ' size:', elem.size)
    if pmsg: print('-----------------------------------------')

# exit application with error code
def exitWithError( msg='' ):
    # display optional message
    if msg:
        if pmsg: print(msg)
        logger.error(smg)
        
    # display that we terminated and then terminate
    if pmsg: print('TERMINATE')
    logger.error('TERMINATE')
    sys.exit(1)

# -----------------------------------------------------------------------

# CHROME SPECIFIC FEATURES #

# created this because upgrade to ChromeDriver 75 broke this script
def create_webdriver_from_global_var( message ):
    global browser
    if message:
        if pmsg: print(message + ':start:---------------------------------------------------')
        if pmsg: print(message + ':Start up webdriver.' + browser)
        logger.info('%s:start up webdriver:%s', message, browser)

    if browser == 'chrome':
        # turn off w3c - implemented 20190623;kv
        opt = webdriver.ChromeOptions()
        opt.add_experimental_option('w3c', False)
        driver = webdriver.Chrome(chrome_options=opt)
    else:
        driver = webdriver.Firefox()

    return driver

# -----------------------------------------------------------------------

# routine can be called to create a blank record - no wine found - because we want to know that we looked and did not find anything
def returnNoWineFound( store ):
    # no wine found record - update and pass this along
    return [{ 'wine_store' : store, 'wine_name' : 'Sorry no matches were found', 'wine_price' : '1', 'wine_year' : '', 'label' : store }]


# -----------------------------------------------------------------------

#### BEVMO ####

# function used to extract the data from the DOM that was returned
def bevmo_extract_wine_from_DOM(winestore,index,winelist):
    global verbose

    # set the variable
    FiveCentSale = False

    # Step thorugh this list and extract out the data of interest - we are doing one example
    #
    # extract out the single element that is the product name
    winename = winelist[index].find_elements_by_class_name('fp-item-name')[0].text

    # out of stock check
    outofstock = winelist[index].find_elements_by_class_name('fp-is-item-no-movement')

    # stop processing this index if we are out of stock
    if outofstock:
        return None

    # get the wine size
    # winesize = winelist[index].find_elements_by_class_name('fp-item-size')[0].text

    # adjust the name if hte size is not 750
    #if winesize != '750 ml':
    #    winename += winesize

    #
    # step through the prices until we find one that works
    # this price types are ordered in preference of use
    # we will stop looking once we find a price
    pricetypes = ['fp-item-sale-price','fp-promo-price','fp-item-base-price']
    for pricetype in pricetypes:
        # search for this element
        priceelement = winelist[index].find_elements_by_class_name(pricetype)
        # if we got back any values (the len > 0)
        if len(priceelement):
            # test for 5 cent sale
            if priceelement[0].text.encode('utf-8') == b'5\xc2\xa2 Sale CLUBBEV!':
                # set the value and get the next price
                FiveCentSale = True
                if pmsg: print(winename, ':5 cent sale')
                logger.info('5 cent sale wine:%s', winename)
            else:
                # this is the price we are going with
                wineprice = priceelement[0].text
                # now strip the unwanted text
                wineprice = re.sub('\s+.*', '', wineprice)
                # now strip the dollar sign
                wineprice = re.sub('\$', '', wineprice)
                # now clean up $ and ,
                wineprice = wineprice.replace('$','').replace(',','')
                # finally - if the five cent sale is on - change the price
                if FiveCentSale:
                    # add 5 cents then divde by 2, make sure this stays unrounded dollars
                    wineprice = '%.2f' % ((float(wineprice)+ 0.05)/2)

                # debugging
                if verbose > 1:
                    if pmsg: print(winestore , ":", winename, ":", pricetype, ":", wineprice)
                logger.debug('store:wine:pricetype:price:%s:%s:%s:%s', winestore,winename,pricetype,wineprice)
                # stop looking
                break
    #
    # final extracted wine data
    return { 'wine_store' : winestore, 'wine_name' : winename, 'wine_price' : wineprice, 'wine_year' : '', 'label' : winestore }

def bevmo_search_box_find( bevmo_driver ):

    # define what we are looking for
    results = bevmo_driver.find_elements_by_name('fp-input-search')
    page_refresh_count_down = 4
    while not results and page_refresh_count_down:
        # debugging
        if pmsg: print('bevmo_search_box_find:get the main url for the website fresh counter:', page_refresh_count_down)
        logger.info('get the main url for the website fresh counter:%d', page_refresh_count_down)

        page_refresh_count_down -= 1
        
        # refresh page and find search box
        bevmo_driver.get('https://www.bevmo.com')

        # loop while we have not found the search box and 
        results = bevmo_driver.find_elements_by_name('fp-input-search')
        loopcnt = 4
        while not results and loopcnt:
        
            # wait time for page to refres
            if pmsg: print('bevmo_search_box_find:waiting for search box to appear:', loopcnt)
            logger.info('waiting for search box to appear:loopcnt:%d', loopcnt)
            loopcnt -= 1
            time.sleep(3)
            results = bevmo_driver.find_elements_by_name('fp-input-search')


    # debugging
    if not results:
        logger.warning('never found the search box for:%s', srchstring)
        if pmsg: print('bevmo_search_box_find:ERROR:never found the search box:', srchstring)
        if pmsg: print('bevmo_search_box_find:exiting program due to error:no search boxes after many tries')
        # fail and leave the browser up so we can take a look at it
        saveBrowserContent( bevmo_driver, 'bevmo', 'bevmo_search_box_find' )
        exitWithError()

    # debugging
    if pmsg: print('bevmo_search_box_find:locate the visible search box')
    logger.info('located the visible search box')

    # search the returned boxes to see if any are visible
    index=0
    for search_box in results:
        # wrap this in a try/catch to capture errors
        try:
            # check to see if this check box is displayed
            if search_box.is_displayed():
                # visible - so we are done
                # debugging
                if pmsg: print('bevmo_search_box_find:search box index:', index, ':is visible - search_box set to this value')
                logger.info('search box index that is visbile:%d', index)
                return search_box
        except:
            if pmsg: print('bevmo_search_box_find:search_boxes[index].is_displayed():errored out')
            log.warning('bevmo_search_box_find:search_boxes[index].is_displayed():errored out')

        # increment the index
        index += 1

        
    # did not find a displayed search box - click the search button if visible and try again
    if pmsg: print('bevmo_search_box_find:no visible search boxes - click the search icon')
    logger.info('no visible search boxes - click the search icon')
    classname = 'glyphicon-search'
    searchbtns = bevmo_driver.find_elements_by_class_name(classname)
    if pmsg: print('bevmo_search_box_find:find search button icon count:', len(searchbtns))
    logger.info('find search button icon count:%d', len(searchbtns))
    if len(searchbtns):
        searchbtn = searchbtns[0]
        if searchbtn.is_displayed():
            if pmsg: print('bevmo_search_box_find:click search icon')
            logger.info('click search icon')
            searchbtn.click()
            # pause for a second
            time.sleep(1)
        else:
            if pmsg: print('bevmo_search_box_find:search button NOT visible - NOT pressed')
            logger.info('search button NOT visible - NOT pressed')
    else:
        if pmsg: print('bevmo_search_box_find:search button not found:', classname)
        logger.info('search button not found:%s', classname)

    # find the search box
    if pmsg: print('bevmo_search_box_find:find the search boxes:again')
    logger.info('find the search boxes:again')
    search_boxes = bevmo_driver.find_elements_by_name('fp-input-search')
    if pmsg: print('bevmo_search_box_find:boxes_found again:', len(search_boxes))
    logger.info('boxes_found again:%d', len(search_boxes))

    # debugging
    if pmsg: print('bevmo_search_box_find:locate the visible search box:again')
    logger.info('locate the visible search box:again')

    # search the returned boxes to see if any are visible
    for index in range(len(search_boxes)):
        search_box = search_boxes[index]
        # check to see if this check box is displayed
        if search_boxes[index].is_displayed():
            # visible - so we are done
            # debugging
            if pmsg: print('bevmo_search_box_find:search boxes:again:', index, 'is visible - search_box set to this value')
            logger.info('search boxes:again:visible box:%s', index)
            return search_boxes[index]

    if pmsg: print('bevmo_search_box_find:no visible search boxes:again:TERMINATE program')
    logger.error('bevmo_search_box_find:no visible search boxes:again:TERMINATE program')
    sys.exit()


# create a search on the web
def bevmo_search( srchstring, bevmo_driver ):
    global verbose

    winestore = 'BevMo'

    # get the search box we are working with
    search_box = bevmo_search_box_find( bevmo_driver )
    loopcnt = 4

    while not search_box and loopcnt:
        # Open the website
        if pmsg: print('bevmo_search:call bevmo_search_box_find again:', loopcnt)
        logger.info('call bevmo_search_box_find again:%d', loopcnt)
        loopcnt -= 1
        search_box = bevmo_search_box_find( bevmo_driver )


    # if no search box found - big problems
    if not search_box:
        if pmsg: print('bevmo_search:ERROR:never found the displayed search box')
        logger.info('bevmo_search:ERROR:never found the displayed search box')

        # fail and leave the browser up so we can take a look at it
        saveBrowserContent( bevmo_driver, 'bevmo', 'bevmo_search:search_box' )
        exitWithError()

    # debugging
    if pmsg: print('bevmo_search:search for:', srchstring)
    logger.info('search for:%s', srchstring)

    # send in the string to this box and press RETURN
    try:
        search_box.clear()
        search_box.send_keys(srchstring)
        search_box.send_keys(Keys.RETURN)
    except  Exception as e:
        exceptionPrint( e, 'bevmo_search', 'ERROR:entering search string:'+srchstring, True, bevmo_driver, 'bevmo', 'bevmo_search' )
        return []
    
    # create the array that we will add to
    found_wines = []

    # we are looking for results page
    results=find_elements_looped( bevmo_driver, 'department-breadcrumb', 'by_class_name', 'bevmo_search', 'waiting on search response')
    # if we don't have results - we have problme
    if not results:
        if pmsg: print('bevmo_search:ERROR:did not receive results - return noWine:', srchstring)
        logger.info('ERROR:did not receive results - return noWine:%s', srchstring)
        # update the website we are pointing at
        bevmo_driver.get('https://www.bevmo.com')
        if pmsg: print('bevmo_search:page refreshed to:www.bevmo.com')
        if pmsg: print('bevmo_search:', srchstring, ':returned records: 0')
        logger.info('page refreshed to:www.bevmo.com')
        logger.info(rtnrecfmt, srchstring, 0)
        # return a record that says we could not find the record
        return returnNoWineFound( winestore )
        
    
    # now look for no result or result
    noresults =  bevmo_driver.find_elements_by_class_name('fp-product-not-found')
    results =  bevmo_driver.find_elements_by_class_name('fp-item-content')
    loopcnt = 4
    while not noresults and not results and loopcnt:
        if pmsg: print('bevmo_search:waiting for results post breadcrumbs to show up:', loopcnt)
        logger.info('waiting for results post breadcrumbs to show up:%d', loopcnt)
        time.sleep(2)
        loopcnt -= 1
        noresults =  bevmo_driver.find_elements_by_class_name('fp-product-not-found')
        results =  bevmo_driver.find_elements_by_class_name('fp-item-content')


    # if no results
    if noresults:
        if pmsg: print('bevmo_search:', srchstring, ':no results returned - refresh the page we are looking at')
        logger.info('no results returned - refresh the page we are looking at:%s', srchstring)
        # saveBrowserContent( bevmo_driver, 'bevmo', 'bevmo_search')
        # update the website we are pointing at
        bevmo_driver.get('https://www.bevmo.com')
        logger.info('page refreshed to:www.bevmo.com')
        logger.info(rtnrecfmt, srchstring, 0)
        # return a record that says we could not find the record
        return returnNoWineFound( winestore )

    
    # debugging
    if pmsg: print('bevmo_search:', srchstring, ':returned records:',  len(results))
    logger.info(rtnrecfmt, srchstring, 0)

    # now loop through the wines we found
    for index in range(len(results)):
        try:
            # get the values of interest from this section of the page
            rec =  bevmo_extract_wine_from_DOM(winestore,index,results)
        except Exception as e:
            # we expect this to fail here so lets just deal with it
            if pmsg: print('bevmo_search:ERROR:bevmo_extract_wine_from_DOM:', srchstring)
            logger.warning('bevmo_extract_wine_from_DOM:%s', srchstring)
            saveBrowserContent( driver, 'bevmo', 'bevmo_search:bevmo_extract_wine_from_DOM' )
            rec = None
            break
        
        # if we were not out of stock, save teh record
        if rec:
            found_wines.append( rec )
        # debugging
        logger.debug('rec:%s', rec)

    # debugging
    if pmsg: print('bevmo_search:found_wines:',len(found_wines))
    logger.info(rtnrecfmt, srchstring, len(found_wines))

    # if we did not find any wines - send back that we did not find any wines
    if not found_wines:
        logger.info('no results returned - refresh the page we are looking at:%s', srchstring)
        # saveBrowserContent( bevmo_driver, 'bevmo', 'bevmo_search')
        # update the website we are pointing at
        bevmo_driver.get('https://www.bevmo.com')
        logger.info('page refreshed to:www.bevmo.com')
        logger.info(rtnrecfmt, srchstring, 0)
        return returnNoWineFound( winestore )

    # update the website we are pointing at
    if pmsg: print('bevmo_search:refresh the page we are looking at')
    logger.info('bevmo_search:refresh the page we are looking at')
    bevmo_driver.get('https://www.bevmo.com')

    # return the wines we found
    return found_wines

# if we don't get the age dialogue - get the select store dialogue
def set_bevmo_store_nopopup(driver):
    try:
        if pmsg: print('set_bevmo_store_nonpopup:no-21:click-select-store')
        logger.info('no-21:click-select-store')
        selectStoreBtns = driver.find_elements_by_class_name('fp-store-label')
        for selectStoreBtn in selectStoreBtns:
            if selectStoreBtn.is_displayed():
                selectStoreBtn.click()
                return True
    except:
        if pmsg: print('set_bevmo_store_nopopup:did not find classname:fp-store-label')
        logger.error('did not find classname:fp-store-label')
        # did not find what we were looking for
        exitWithError()
        return None

# function to create a selenium driver for bevmo and get past the store selector
def create_bevmo_selenium_driver(defaultstore, defaultstoreid, retrycount=0):
    loopcnt = retrycount + 1
    while(loopcnt):
        try:
            return create_bevmo_selenium_driver_worker(defaultstore, defaultstoreid)
        except  Exception as e:
            exceptionPrint( e, 'create_bevmo_selenium_driver', ':loopcnt:'+str(loopcnt) )
            loopcnt -= 1

    # all loops failed - give up on bevmo
    if pmsg: print('create_bevmo_selenium_driver:failed-all-attempts:skip-bevmo')
    logger.info('failed-all-attempts:skip-bevmo')
    return None
    

def bevmo_find_selected_store( driver ):        
    selectedstores = driver.find_elements_by_class_name('fp-store-label')
    storetext=''
    for stores in selectedstores:
        if stores.text: 
            storetext=stores.text
    loopcnt=4
    while not storetext and loopcnt:
        if pmsg: print('bevmo_driver:waiting for selected store to be shown:', loopcnt)
        logger.info('waiting for selected store to be shown:%d', loopcnt)
        time.sleep(3)
        loopcnt -= 1
        selectedstores = driver.find_elements_by_class_name('fp-store-label')
        for stores in selectedstores:
            if stores.text: 
                storetext=stores.text
                return storetext

    return storetext
    
# function to create a selenium driver for bevmo and get past the store selector
def create_bevmo_selenium_driver_worker(defaultstore, defaultstoreid):
    global verbose

    # Using Chrome to access web
    driver=create_webdriver_from_global_var('bevmo_driver')

    # debugging
    if pmsg: print('bevmo_driver:Go to www.bevmo.com web page')
    logger.info('bevmo_driver:Go to www.bevmo.com web page')
    
    # Open the website
    driver.get('https://www.bevmo.com')

    # loop waiting for the modal dialogue to appear
    modal_found = driver.find_elements_by_class_name('fp-modal-content')
    modal_count_down = 4
    while not modal_found and modal_count_down:
        if pmsg: print('create_bevmo_selenium_driver_worker:waiting for web page to render:', modal_count_down)
        logger.info('waiting for web page to render:%d', modal_count_down)
        time.sleep(3)
        # decrement the modal count down
        modal_count_down -= 1
        # search for this again
        modal_found = driver.find_elements_by_class_name('fp-modal-content')
        
    # did not find it - return none
    if not modal_found:
        if pmsg: print('create_bevmo_selenium_driver_worker:never found model - return None')
        logger.warning('never found model - return None')
        return None

    
    # find the checkbox and click it
    try:
        # i am 21 checkbox - find check box and fill it in
        if pmsg: print('bevmo_driver:find i am 21 check box and click')
        logger.info('bevmo_driver:find i am 21 check box and click')
        checkboxes = driver.find_elements_by_class_name('fp-checkbox')
        for checkbox in checkboxes:
            if checkbox.is_displayed():
                if pmsg: print('bevmo_driver:wait 2 seconds for screen to make box clickable')
                logger.info('bevmo_driver:wait 2 seconds for screen to make box clickable')
                time.sleep(2)
                checkbox.click()
                break
        else:
            if pmsg: print('bevmo_driver:21 checkbox cnt:', len(checkboxes), ':none were displayed')
            logger.warning('no 21 checkbox is_displayed - box cnt:%d', len(checkboxes))
            return None

    except  Exception as e:
        exceptionPrint( e, 'bevmo_driver', 'failed i am 21 checkbox click', True, bevmo_driver, 'bevmo', 'bevmo_driver' )
        if pmsg: print('bevmo_driver:calling:set_bevmo_store_nopopup')
        logger.warning('exception-now calling:set_bevmo_store_nopopup')
        set_bevmo_store_nopopup(driver)


    # now we need to web page to update so loop until we see it
    errorsent = driver.find_elements_by_class_name('fp-error')
    if errorsent and errorsent[0].text != '':
        if pmsg: print('bevmo_driver:got an error:', errorsent[0].text)
        logger.warning('bevmo_driver:got an error:%s', errorsent[0].text)
        return None
    
    # sleep for 1 second to allow page to respond
    if pmsg: print('bevmo_driver:wait for 1 second')
    logger.info('bevmo_driver:wait for 1 second')
    time.sleep(1)

    # select the store we want to work with
    try:
        # pick up at the store
        if pmsg: print('bevmo_driver:find and click pickup at store')
        logger.info('find and click pickup at store')
        buttons=driver.find_elements_by_class_name('btn-primary')
        if pmsg: print('bevmo_driver:number of buttons:', len(buttons))
        logger.info('number of buttons:%d', len(buttons))
        for button in buttons:
            if button.get_attribute('data-action') == 'change-pickup':
                if pmsg: print('bevmo_driver:clicking button with text:', button.text)
                if pmsg: print('is button displayed:%s', button.is_displayed())
                logger.info('bevmo_driver:clicking button with text:%s', button.text)
                logger.info('is button displayed:%s', button.is_displayed())
                # print('bevmo_driver:before-clicking-button:saving-browser-for-debugging')
                # saveBrowserContent( driver, 'bevmobtn', 'bevmo_driver:click-button' )
                time.sleep(1)
                button.click()
                if pmsg: print('bevmo_driver:button successfully clicked-break out of loop')
                logger.info('button successfully clicked-break out of loop')
                break
            
    except  Exception as e:
        # we expect this to fail here so lets just deal with it
        if pmsg: print('bevmo_driver:failed and expected - sleep 20 seconds')
        logger.info('failed and expected - sleep 20 seconds')
        time.sleep(20)
        saveBrowserContent( driver, 'bevmo', 'bevmo_driver:btn-primary-failed' )

    # now we need to web page to update so loop until we see it
    errorsent = driver.find_elements_by_class_name('fp-error')
    if errorsent and errorsent[0].text != '':
        if pmsg: print('bevmo_driver:got an error:', errorsent[0].text)
        logger.warning('got an error:%s', errorsent[0].text)
        return None


    if pmsg: print('bevmo_driver:now looking to select our preferred store')
    logger.info('now looking to select our preferred store')
    try:
        # find the input field for zipboxes
        zipboxes = find_elements_looped( driver, 'fp-input-q', 'by_name', 'bevmo_driver', 'waiting for webpage to display input field', loopcnt=6)
        if not zipboxes:
            if pmsg: print('bevmo_driver:never found the input field - returning None')
            logger.warning('never found the input field - returning None')
            return None
        
        # now find the displayed version of this input
        for zipbox in zipboxes:
            if zipbox.is_displayed():
                break

        # check that we found a displayed zipbox
        if zipbox and not zipbox.is_displayed():
            if pmsg: print('bevmo_driver:no zip boxes where displayed - return none - count of zipboxes:', len(zipboxes))
            logger.warning('no zip boxes where displayed - return none - count of zipboxes:%d', len(zipboxes))
            return None
        
        # enter the default store
        if pmsg: print('bevmo_driver:ready to enter store information')
        logger.info('ready to enter store information')
        zipbox.clear()
        if pmsg: print('bevmo_driver:enter store-cleared')
        logger.info('enter store-cleared')
        zipbox.send_keys(defaultstore)
        if pmsg: print('bevmo_driver:enter store-value')
        logger.info('enter store-value')
        zipbox.send_keys(Keys.RETURN)
        if pmsg: print('bevmo_driver:pressed return')
        logger.info('pressed return')

        # wait 
        if pmsg: print('bevmo_driver:wait 5 sec for stores to display')
        logger.info('wait 5 sec for stores to display')
        time.sleep(5)

        # select the cotinue button of the first one returned
        if pmsg: print('bevmo_driver:find the store of interest - and click that button')
        logger.info('find the store of interest - and click that button')
        buttons=driver.find_elements_by_class_name('fp-btn-mystore')
        for button in buttons:
            if button.get_attribute('data-store-id') == defaultstoreid:
                if pmsg: print( 'bevmo_driver:clicking button on store:', defaultstoreid )
                logger.info('clicking button on store:%s', defaultstoreid )
                button.click()

    except  Exception as e:
        exceptionPrint( e, 'bevmo_driver', 'failed selecting store', True, driver, 'bevmo', 'bevmo_driver-fp-btn-mystore', exitPgm=True )


    # pause to let screen refresh
    if pmsg: print('bevmo_driver:pause 3 seconds to allow screen to refresh for selected store')
    logger.info('bevmo_driver:pause 3 seconds to allow screen to refresh for selected store')
    time.sleep(3)

    # Test that the store got set correctly
    storetext=''
    if pmsg: print('bevmo_driver:see what store was selected')
    logger.info('see what store was selected')
    try:
        storetext = bevmo_find_selected_store( driver )
    except Exception as e:
        exceptionPrint( e, 'bevmo_driver', 'failed lookup up selected store', True, driver, 'bevmo', 'bevmo_driver-store-lookup' )
        if pmsg: print('bevmo_driver:refresh screen and look for store again')
        logger.info('refresh screen and look for store again')
        driver.get('https://www.bevmo.com')

    if not storetext:
        storetext = bevmo_find_selected_store( driver )
                
    if storetext:
        if pmsg: print('bevmo_driver:selected store name:', storetext)
        logger.info('selected store name:%s', storetext)
    
    # debugging
    if pmsg: print('bevmo_driver:complete:---------------------------------------------------')
    logger.info('complete:---------------------------------------------------')
    
    # return the driver
    return driver


# --------------------------------------------------------------------------

#### TOTALWINE ####

# create email to tell the person to interact
def totalwine_action_email( optiondict={} ):
    if 'EmailFromAddr' not in optiondict:
        if pmsg: print('totalwine_action_email:ERROR:optiondict not populated - no message sent out')
        logger.warning('optiondict not populated - no message sent out')
        return

    if pmsg: print('totalwine_action_email:sending out message')
    m = kvgmailsend.GmailSend( optiondict['EmailFromAddr'], optiondict['EmailFromPassword'] )
    m.addRecipient( optiondict['EmailToAddr'] )
    m.setSubject( optiondict['EmailSubject'] )
    m.setTextBody( optiondict['EmailBody'] )
    m.send()
    if pmsg: print('totalwine_action_email:message sent!')
    logger.info('message sent!')

# check to see if we encountered the robot and if so - then we need to interact with it to get past it
def totalwine_robot_check(driver, calledby, optiondict={}):
    # validate we are not being checked out for being a robot
    totalwine_driver = driver
    robot_check = totalwine_driver.find_elements_by_class_name('page-title')
    
    # return if we did not find the problem
    if not len(robot_check):
        return False

    # we got to the page - send out the amil
    totalwine_action_email( optiondict )

    # bring the brower to front and center
    if pmsg: print(calledby+':maximizing windows')
    logger.info('%s:maximizing windows', calledby)
    driver.maximize_window()

    # display a message
    try:
        if pmsg: print(calledby+':robot_check:', robot_check[0].text)
        if pmsg: print(calledby+':please fill out the robot form and this program will continue')
        logger.info('%s:robot_check:%s', calledby, robot_check[0].text)
        logger.info('%s:please fill out the robot form and this program will continue', calledby)
    except:
        if pmsg: print(calledby+':robot_check:fill it out but we could not display the text')
        logger.info('%s:robot_check:fill it out but we could not display the text',calledby)


    # loop until the user resolves this issue
    loopcnt = 1
    while( len(robot_check) ):
        # then update the display
        if pmsg: print(calledby+':loopcnt:', loopcnt)
        logger.info('%s:loopcnt:%d', calledby, loopcnt)
        loopcnt += 1
        #input()
        # sleep 5 minutes
        if pmsg: print(calledby+':sleep for 3 minutes starts at:', time.ctime())
        logger.info('%s:sleep for 3 minutes starts at:%s', calledby, time.ctime())
        time.sleep(60*3)
        # check again to see it as cleared
        robot_check = totalwine_driver.find_elements_by_class_name('page-title')

    # cleared the issue - return true
    if pmsg: print(calledby+':problem cleared at:', time.ctime())
    logger.info('%s:problem cleared at:%s', calledby, time.ctime())
    # removed the save browser code for robots
    # saveBrowserContent( totalwine_driver, 'totalwine', 'totalwine_robot' )
    return True


# function used to extract the data from the DOM that was returned
def totalwine_extract_wine_from_DOM(winestore,index,titlelist,pricelist,sizelist,fldmatch):
    
    # extract the values
    winename = titlelist[index].text 
    wineprice = pricelist[index].text

    # if pmsg: print('totalwine_extract_wine_from_DOM:',wineprice)

    # size is pulled out based on what fldmatch solution we have
    if fldmatch in ('searchPageContainer', 'resultCount__1rzUJ1mi'):
        # size is in the name field
        try:
            winename,winesize = winename.split('\n')
        except:
            winename = winename.replace('\n',' ')
            winesize = '750ml'
    else:
        winesize = sizelist[index].text
    
    # add size if size is NOT 750ml
    if winesize != '750ml':
        winename += ' (' + winesize + ')'
        
    # regex the price field to match our expections
    match = re.search('\$\s*(.*)$',wineprice)
    if ('\n' in wineprice):
        wineprice = wineprice.split('\n')[0]
        #if pmsg: print('totalwine_extract_wine_from_DOM:split price:',wineprice)
    elif ('bottle' in wineprice):
        wineprice = wineprice.split(' ')[0]
    elif match:
        wineprice = match.group(1)
        #if pmsg: print('totalwine_extract_wine_from_DOM:match on price',wineprice)
    
    # now clean up $ and ,
    wineprice = wineprice.replace('$','').replace(',','')
    
    # return the dictionary
    return { 'wine_store' : winestore, 'wine_name' : winename, 'wine_price' : wineprice, 'wine_year' : '', 'label' : winestore }


# run the code that performs the search
def totalwine_search_lookup( srchstring, totalwine_driver, optiondict ):
    # get to the search page by refreshing the screen
    loopcnt = 4
    while(loopcnt):

        # debugging
        if pmsg: print('totalwine_search_lookup:go to search page:www.totalwine.com')
        logger.info('go to search page:www.totalwine.com')

        # force the page to start at the top of the page
        totalwine_driver.get('https://www.totalwine.com/')

        # validate we are not being checked out for being a robot
        totalwine_robot_check(totalwine_driver,'totalwine_search_lookup', optiondict )

        # debugging
        if pmsg: print('totalwine_search_lookup:find the search_box')
        logger.info('find the search_box')

        
        # Select the search box(es) and find if any are visbile - there can be more than one returned value
        try:
            search_box = totalwine_driver.find_element_by_xpath('//*[@id="at_searchProducts"]')
            if pmsg: print('totalwine_search_lookup:search box found:at_searchProducts')
            logger.info('search box found:at_searchProducts')
            loopcnt = 0
        except Exception as e:
            if pmsg: print('totalwine_search_lookup:ERROR:failed to find:at_searchProducts:loopcnt:', loopcnt)
            logger.warning('failed to find:at_searchProducts:loopcnt:%d', loopcnt)
            # try a different way
            try:
                search_box = totalwine_driver.find_element_by_xpath('//*[@id="header-search-text"]')
                if pmsg: print('totalwine_search_lookup:search box found:header-search-text')
                logger.info('search box found:header-search-text')
                loopcnt = 0
            except Exception as e:
                if pmsg: print('totalwine_search_lookup:failed to find:header-search-text:loopcnt:', loopcnt)
                if pmsg: print('totalwine_search_lookup:ERROR:failed to find:at_searchProducts:loopcnt:', loopcnt)
                logger.info('failed to find:header-search-text:loopcnt:%d', loopcnt)
                logger.info('failed to find:at_searchProducts:loopcnt:%d', loopcnt)
                saveBrowserContent( totalwine_driver, 'totalwine', 'totalwine_search_lookup' )
                if pmsg: print('totalwine_search_lookup:could not find search box after both lookups:loopcnt:', loopcnt)
                logger.info('could not find search box after both lookups:loopcnt:%d', loopcnt)
                loopcnt -= 1

    # check that we got a search box
    if not search_box:
        if pmsg: print('totalwine_search_lookup:failed to find a search box')
        logger.error('totalwine_search_lookup:failed to find a search box')
        exitWithError()
        pass

    
    # first check to see that the search box is displayed - if not visible then click the bottom that makes it visible
    if not search_box.is_displayed():
        # debugging
        if pmsg: print('totalwine_search_lookup:search box is not displayed - we want to click the button that displays it')
        logger.info('search box is not displayed - we want to click the button that displays it')
        # make the search box visible if it is not
        try:
            totalwine_driver.find_element_by_xpath('//*[@id="header-search-mobile"]/span').click()
        except Exception as e:
            exceptionPrint( e, 'totalwine_search_lookup', 'ERROR:could not find earch box afer both lookups', True, totalwine_driver, 'totalwine', 'totalwine_search_lookup', exitPgm=True )

    # debugging
    if pmsg: print('totalwine_search_lookup:search for:', srchstring)
    logger.info('search for:%s', srchstring)

    # send in the string to this box and press RETURN
    try:
        search_box.clear()
        search_box.send_keys(srchstring)
        search_box.send_keys(Keys.RETURN)
    except:
        if pmsg: print('totalwine_search_lookup:ERROR:could not send keys to search box:', srchstring)
        logger.error('could not send keys to search box:', srchstring)
        saveBrowserContent( totalwine_driver, 'totalwine', 'totalwine_search_lookup' )
        exitWithError()
        pass
        


# Search for the wine
def totalwine_search( srchstring, totalwine_driver, optiondict={} ):
    global verbose

    winestore = 'TotalCA'

    # create the array that we will add to
    found_wines = []

    # message
    if pmsg: print('totalwine_search:calling:totalwine_search_lookup')
    logger.info('calling:totalwine_search_lookup')

    # call the search
    totalwine_search_lookup( srchstring, totalwine_driver, optiondict )

    # test to see if we are being checked for a robot again
    if totalwine_robot_check(totalwine_driver,'totalwine_search:send_keys', optiondict ):
        if pmsg: print('totalwine_search:got robot - call search lookup again')
        logger.info('got robot - call search lookup again')
        totalwine_search_lookup( srchstring, totalwine_driver, optiondict )


    # message
    if pmsg: print('totalwine_search:determining if we got results back')
    logger.info('determining if we got results back')

    # test to see the result count we got back
    returned_recs = None
    loopcnt = 0
    while returned_recs == None:
        # sleep to give page time to fill in
        if pmsg: print('totalwine_search:pause 0.5 sec to allow the page to fill in')
        logger.info('pause 0.5 sec to allow the page to fill in')
        time.sleep(0.5)

        
        # check now for <span class="resultCount__1rzUJ1mi"><span>1 - 18 of 18 results</span></span>
        # new as of 2020-04-18 - getting the match count
        if not returned_recs:
            fldmatch="resultCount__1rzUJ1mi"
            resultsfld = totalwine_driver.find_elements_by_class_name(fldmatch)
            if pmsg: print('totalwine_search:check for fldmatch on field:',fldmatch)
            logger.info('check for fldmatch on field:%s',fldmatch)
            if resultsfld:
                if pmsg: print('totalwine_search:count found on fld:', fldmatch)
                if pmsg: print('totalwine_search:count of fld:', len(resultsfld))
                logger.info('count found on fld:%s', fldmatch)
                logger.info('count of fld:%d', len(resultsfld))
                if resultsfld[0].text == '0 results':
                    returned_recs = 0
                    break
                if not resultsfld[0].text:
                    if pmsg: print('totalwine_search:ERROR:no value extracted from resultsfld[0].text:', resultsfld[0].text)
                    logger.error('could not pull split out of this line:%s:', resultsfld[0].text)
                    logger.info('pulling out the titlelist and get a count from it:title__2RoYeYuO')
                    titlelist = totalwine_driver.find_elements_by_class_name('title__2RoYeYuO')
                    returned_recs = len(titlelist)
                    logger.error('taken from title field result cnt is:%d', returned_recs)
                    break
                    
                try:
                    returned_recs = resultsfld[0].text.split()[2]
                except:
                    if pmsg: print('totalwine_search:ERROR:could not pull split out of this line:', resultsfld[0].text)
                    logger.error('could not pull split out of this line:%s:', resultsfld[0].text)
                    # temporary - lets look at the page to see why we could not parse it
                    saveBrowserContent( totalwine_driver, 'totalwine', 'totalwine_search' )

                break

        if not returned_recs:
            fldmatch="resultsTitle__2yxTXNeW"
            resultsfld = totalwine_driver.find_elements_by_class_name(fldmatch)
            if pmsg: print('totalwine_search:check for fldmatch on field:',fldmatch)
            logger.info('check for fldmatch on field:%s',fldmatch)
            if resultsfld:
                if pmsg: print('totalwine_search:count found on fld:', fldmatch)
                if pmsg: print('totalwine_search:count of fld:', len(resultsfld))
                logger.info('count found on fld:%s', fldmatch)
                logger.info('count of fld:%d', len(resultsfld))
                if resultsfld[0].text == 'No results':
                    returned_recs = 0
                    break
                try:
                    returned_recs = resultsfld[0].text.split()[2]
                except:
                    if pmsg: print('totalwine_search:ERROR:could not pull split out of this line:', resultsfld[0].text)
                    logger.error('could not pull split out of this line:%s', resultsfld[0].text)
                break

        # returned records id field: anProdCount, listCount, searchPageContainer
        if not returned_recs:
            for fldmatch in ('anProdCount','listCount'):
                if pmsg: print('totalwine_search:check for fldmatch on field:',fldmatch)
                logger.info('check for fldmatch on field:%s',fldmatch)
                resultsfld = totalwine_driver.find_elements_by_id(fldmatch)
                if resultsfld:
                    if pmsg: print('totalwine_search:count found on fld:', fldmatch)
                    if pmsg: print('totalwine_search:count of fld:', len(resultsfld))
                    logger.info('count found on fld:%s', fldmatch)
                    logger.info('count of fld:%d', len(resultsfld))
                    returned_recs = resultsfld[0].get_attribute('value')
                    break

        # first two fields did not work - see if we are on searchPageContainer
        if not returned_recs:
            fldmatch = 'searchPageContainer'
            resultsfld = totalwine_driver.find_elements_by_id(fldmatch)
            if pmsg: print('totalwine_search:check for fldmatch on field:',fldmatch)
            logger.info('check for fldmatch on field:%s',fldmatch)
            if resultsfld:
                # see if we can get the real results
                try:
                    # see if we can return the total number of records returned in the search
                    result = totalwine_driver.find_element_by_xpath('//*[@id="searchPageContainer"]/div[2]/div[1]/div/div[1]')
                    if pmsg: print('totalwine_search:result:', result.text)
                    logger.info('result:%s', result.text)
                    if result:
                        returned_recs = int(result.text.split(' ')[0]) 
                except:
                    if pmsg: print('totalwine_search:did not find the result')
                    logger.info('did not find the result')
                    returned_recs = 1
                if pmsg: print('totalwine_search:count found on fld:', fldmatch)
                if pmsg: print('totalwine_search:count of fld:', len(resultsfld))
                if pmsg: print('totalwine_search:count of returned records:', returned_recs)
                logger.info('count found on fld:%s', fldmatch)
                logger.info('count of fld:%d', len(resultsfld))
                logger.info('count of returned records:%d', returned_recs)


        # finally check to see if we got a "No results" message back and bail if we did
        if not returned_recs:
            # fldmatch="resultsTitle__drQnygRS" - value worked until 4/18/2020
            fldmatch="resultsTitle__2yxTXNeW"
            resultsfld = totalwine_driver.find_elements_by_class_name(fldmatch)
            if pmsg: print('totalwine_search:check for fldmatch on field:',fldmatch)
            logger.info('check for fldmatch on field:%s',fldmatch)
            if resultsfld:
                if pmsg: print('total_search:', srchstring, ':returned records: 0')
                # return a record that says we could not find the record
                return returnNoWineFound( winestore )
                

        # check to see if we have looped to many times
        if loopcnt > 10:
            if pmsg: print('totalwine_search:ERROR:looped too many times - exiting program')
            logger.error('looped too many times - exiting program')
            saveBrowserContent( totalwine_driver, 'totalwine', 'totalwine_search' )
            exitWithError()
        else:
            loopcnt += 1
            if pmsg: print('totalwine_search:loopcnt:',loopcnt)
            logger.info('loopcnt:%d',loopcnt)

    # check to see if we got no results
    if returned_recs == 0:
        if pmsg: print('totalwine_search:', srchstring, ':no results returned - refresh the page we are looking at')
        logger.info('no results returned for:%s', srchstring)
        # update the website we are pointing at
        totalwine_driver.get('https://www.totalwine.com')
        # return a record that says we could not find a record
        return returnNoWineFound( winestore )


    # debugging
    if pmsg: print('totalwine_search:', srchstring, ':returned records:', returned_recs)
    logger.info(rtnrecfmt, srchstring, returned_recs)
    
    # get results back and look for the thing we are looking for - the list of things we are going to process
    if fldmatch == 'searchPageContainer':
        titlelist = totalwine_driver.find_elements_by_class_name('title__11ZhZ3BZ')
        availlist = totalwine_driver.find_elements_by_class_name('messageHolder__20eUWkhD')
        #mix6list = totalwine_driver.find_elements_by_class_name('')
        sizelist  = []
        pricelist = totalwine_driver.find_elements_by_class_name('pricingHolder__1VkKua4M')
    elif fldmatch == 'resultCount__1rzUJ1mi':
        # <h2 class="title__2RoYeYuO titleDown__BwxDDzkX" id="product-117908175-1-0_Title">
        titlelist = totalwine_driver.find_elements_by_class_name('title__2RoYeYuO')
        # <div class="messageHolder__1LBm8SMH">
        availlist = totalwine_driver.find_elements_by_class_name('messageHolder__1LBm8SMH')
        #mix6list = totalwine_driver.find_elements_by_class_name('')
        sizelist  = []
        #<div class="pricingHolder__1ItgGBnd">
        pricelist = totalwine_driver.find_elements_by_class_name('pricingHolder__1ItgGBnd')
    else:
        titlelist = totalwine_driver.find_elements_by_class_name('plp-product-title')
        availlist = totalwine_driver.find_elements_by_class_name('plp-product-buy-limited')
        #mix6list = totalwine_driver.find_elements_by_class_name('plp-product-buy-mix')
        sizelist  = totalwine_driver.find_elements_by_class_name('plp-product-qty')
        pricelist = totalwine_driver.find_elements_by_class_name('price')
            
    # debugging
    if pmsg: print('totalwine_search:Counts:title,avail,size,price,fldmatch:', len(titlelist),len(availlist),len(sizelist),len(pricelist),fldmatch)
    logger.info('Counts:title,avail,size,price,fldmatch:%d:%d:%d:%d:%s', len(titlelist),len(availlist),len(sizelist),len(pricelist),fldmatch)


    # message we have a problem
    if len(titlelist) != len(pricelist):
        if pmsg: print('totalwine_search:price and name lists different length:',srchstring,':len(wine):',len(titlelist),':len(price):',len(pricelist))
        logger.info('price and name lists different length:%s:len(wine):%d:len(price):%d',srchstring,len(titlelist),len(pricelist))

    
    # now loop through the wines we found
    for index in range(len(pricelist)):
        # get the availability string
        if len(availlist)==0:
            availstring = ''
        elif isinstance( availlist[index], str ):
            availstring = availlist[index]
        else:
            availstring = availlist[index].text

        # debugging
        # if pmsg: print(availstring+':',"Unavailable" not in availstring,'\n')

        # we don't grab records where they are out of stock
        if not titlelist[index].text:
            if pmsg: print('totalwine_search:no wine title for this row:row skipped')
            logger.info('no wine title for this row:row skipped')
        elif availstring and "Pick Up Out of Stock" in availstring:
            # show the out of stock entries to the user/log
            if pmsg: print('totalwine_search:unavailable_wine_skipped:',titlelist[index].text,':unavailable_string:',availstring)
            logger.info('unavailable_wine_skipped:%s:unavailable_string:%s',titlelist[index].text,availstring)
        elif availstring and "Pick Up Unavailable" in availstring:
            # show the out of stock entries to the user/log
            if pmsg: print('totalwine_search:unavailable_wine_skipped:',titlelist[index].text,':unavailable_string:',availstring)
            logger.info('unavailable_wine_skipped:%s:unavailable_string:%s',titlelist[index].text,availstring)
        else:
            # this is not out of stock
            found_wines.append( totalwine_extract_wine_from_DOM(winestore,index,titlelist,pricelist,sizelist,fldmatch) )


    # return the wines we found
    return found_wines

# function to create a selenium driver for totalwine and get past age question
def create_totalwine_selenium_driver(defaultstore, optiondict):
    global verbose

    
    # Using Chrome to access web
    driver=create_webdriver_from_global_var('totalwine_driver')

    # debugging
    if pmsg: print('totalwine_driver:Go to www.totalwine.com web page')
    logger.info('Go to www.totalwine.com web page')
    
    # Open the website
    driver.get('https://www.totalwine.com')

    # sleep to allow the dialogue to come up
    if pmsg: print('totalwine_driver:sleep 1 to allow popup to appear')
    logger.info('sleep 1 to allow popup to appear')
    time.sleep(1)

    # check for robot
    totalwine_robot_check(driver,'totalwine_driver', optiondict)

    # check for the button being visible
    try:
        if driver.find_element_by_xpath('//*[@id="btnYes"]'):
            if pmsg: print('totalwine_driver:found the yes button')
            logger.info('found the yes button')
            if driver.find_element_by_xpath('//*[@id="btnYes"]').is_displayed():
                if pmsg: print('totalwine_driver:button is visible-click to say yes')
                logger.info('button is visible-click to say yes')
                driver.find_element_by_xpath('//*[@id="btnYes"]').click()
    except:
        if pmsg: print('totalwine_driver:no age button displayed - moving along')
        logger.info('no age button displayed - moving along')

    # check to see if we are set to the store of interest (don't pass default - we want a blank if we don't find this)
    store_name = totalwine_driver_get_store(driver)

    # debugging
    if pmsg: print('totalwine_driver:current store_name:', store_name)
    logger.info('current store_name:%s', store_name)
    
    # test to see if store matches current store
    if not re.search(defaultstore, store_name):
        # debugging
        if pmsg: print('totalwine_driver:current store not set to:', defaultstore, ':set the store')
        logger.info('current store not set to:%s', defaultstore)
        store_name = totalwine_driver_set_store(driver, defaultstore)
        logger.info('new store_name:%s', store_name)
    else:
        if pmsg: print('totalwine_driver:store set to default')
        logger.info('store set to default:%s', defaultstore)
            
    # debugging
    if pmsg: print('totalwine_driver:complete:---------------------------------------------------')
    logger.info('complete:---------------------------------------------------')
    
    # return the driver
    return driver

# get the store that the website is configured to search
def totalwine_driver_get_store(driver, defaultstore=''):
    global verbose
    # class checks first
    for classname in ('anGlobalStore', 'header-store-details'):
        try:
            if pmsg: print('totalwine_driver_get_store:check_for_class_name:', classname) 
            logger.info('check_for_class_name:%s', classname) 
            store = driver.find_elements_by_class_name(classname)
            if store:
                if pmsg: print('totalwine_driver_get_store:class_name:', classname, ':type:', type(store))
                logger.info('class_name:%s:type:%s', classname, type(store))
                if not isinstance(store,list):
                    # not a list - just pull the value (and lets us know if that value is displayed)
                    if pmsg: print('totalwine_driver_get_store:class_name:', classname, ':not_list:is_displayed:', store.is_displayed())
                    logger.info('class_name:%s:not_list:is_displayed:%s', classname, store.is_displayed())
                    store_name = store.get_attribute('innerText')
                else:
                    # it is a list - we need to figure out which one we want to use
                    if pmsg: print('totalwine_driver_get_store:class_name:', classname, ':number of matches:', len(store))
                    logger.info('class_name:%s:number of matches:%d', classname, len(store))
                    # set it to the first match even if not displayed and then override that if we find a displayed value
                    store_name = store[0].get_attribute('innerText')
                    # loop through entries looking for one that is displaying
                    for i in range(len(store)):
                        if pmsg: print('totalwine_driver_get_store:class_name:', classname, ':', i, ':is_displayed:', store[i].is_displayed())
                        logger.info('class_name:%s:%d::is_displayed:%s', classname, i, store[i].is_displayed())
                        if store[i].is_displayed():
                            store_name = store[i].get_attribute('innerText')
                            if pmsg: print('totalwine_driver_get_store:class_name:', classname, ':found displayed value:set store_name and break out')
                            logger.info('found displayed value:set store_name and break out:class_name:%s', classname)
                            break
                if pmsg: print('totalwine_driver_get_store:anGlobalStore found-capturing the name:', store_name)
                logger.info('anGlobalStore found-capturing the name:%s', store_name)
                # get the store attribute
                return store_name.replace('\t','')
        except Exception as e:
            if pmsg: print('totalwine_driver_get_store:ERROR:anGlobalStore:', str(e))
            logger.warning('anGlobalStore:', str(e))
    
    # debugging - did not find the store
    if pmsg: print('totalwine_driver_get_store:did not find store using class_name')
    logger.info('did not find store using class_name')

    # now pull the name that is the name of the current store
    for idname in ('globalStoreName_desktop', 'globalStoreName', 'globalStoreName_mobile'):
        try:
            if pmsg: print('totalwine_driver_get_store:check_for_xpath:', idname)
            logger.info('check_for_xpath:%s', idname)
            store = driver.find_element_by_xpath('//*[@id="' + idname + '"]')
            if store:
                if not isinstance(store,list):
                    if pmsg: print('totalwine_driver_get_store:', idname, ':store:is_displayed:', store.is_displayed())
                    logger.info('%s:store:is_displayed:%s', idname, store.is_displayed())
                    store_name = store.get_attribute('innerText')
                else:
                    if pmsg: print('totalwine_driver_get_store:', idname, ':number of matches:', len(store))
                    logger.info('%s:number of matches:%d', idname, len(store))
                    for i in range(len(store)):
                        if pmsg: print(idname, ':', i, ':is_displayed:', store[i].is_displayed())
                        logger.info('%s:%d:is_displayed:%s', idname, i, store[i].is_displayed())
                    store_name = store[0].get_attribute('innerText')
                if pmsg: print('totalwine_driver_get_store:', idname, ':found-capturing name:', store_name)
                logger.info('%s:found-capturing name:%s', idname, store_name)
                # get the store attribute
                return store_name
        except Exception as e:
            if pmsg: print('totalwine_driver_get_store:ERROR:', idname, ':', str(e))
            logger.warning('%s:%s', idname, str(e))
    
    if pmsg: print('totalwine_driver_get_store::did not find the name - setting return value to defaultstore:', defaultstore)
    logger.info('did not find the name - setting return value to defaultstore:%s', defaultstore)
    return defaultstore

# change the store the website is configured to search
def totalwine_driver_set_store(driver, defaultstore):
    global verbose

    # debugging
    if pmsg: print('totalwine_driver_set_store:get:www.totalwine.com/store-finder')
    logger.info('get:www.totalwine.com/store-finder')

    # now change the store we are working with
    driver.get('https://www.totalwine.com/store-finder')

    # search for the field to enter data into
    try:
        store_search_box = driver.find_element_by_xpath('//*[@id="storelocator-query"]')
    except Exception as e:
        exceptionPrint( e, 'totalwine_driver_set_store', 'ERROR:storelocator-query', True, totalwine_driver, 'totalwine', 'totalwine_driver_set_store', exitPgm=True )

    # dislay a message
    if pmsg: print('totalwine_driver_set_store:search for default store:', defaultstore)
    logger.info('search for default store:%s', defaultstore)

    # now send in the keys
    store_search_box.send_keys(defaultstore)
    store_search_box.send_keys(Keys.RETURN)

    # check to see if this now has selected this as our store

    # now we need to select the store that returns
    # original xpath
    # select_store = driver.find_element_by_xpath('//*[@id="shopThisStore"]')
    # 20190503;kv - new xpath to find this thing
    #
    # class = storeFinderLister
    # find the list of stores returned
    #matching_stores = driver.find_elements_by_class_name('storeFinderLister')
    matching_stores = None
    matching_count_down = 4
    while not matching_stores and matching_count_down:
        matching_stores = driver.find_elements_by_class_name('shopThisStore')
        if not matching_stores:
            if pmsg: print('totalwine_driver_set_store:wait to find returned stores 3 secs')
            logger.info('wait to find returned stores 3 secs')
            time.sleep(3)
            matching_count_down -= 1

    # now capture the store we found
    select_store=matching_stores[0]
    #
    # select_store = driver.find_element_by_xpath('//*[@id="bottomLeft"]/ul/div/div[1]/li[1]/div/span[6]/button')
    #if pmsg: print('totalwine_driver_set_store:find and click select this store button:', select_store.get_attribute('name'))
    if pmsg: print('totalwine_driver_set_store:find and click select this store button:', select_store.get_attribute('aria-label'))
    logger.info('find and click select this store button:%s', select_store.get_attribute('aria-label'))
    try:
        select_store.click()
        if pmsg: print('totalwine_driver_set_store:clicked and selected store button')
        logger.info('clicked and selected store button')
    except Exception:
        if pmsg: print('totalwine_driver_set_store:store is not clickable - must already be selected')
        logger.info('store is not clickable - must already be selected')

    # sleep for 1 second to allow page refresh
    if pmsg: print('totalwine_driver_set_store:sleep 1 sec to allow for page refresh')
    logger.info('sleep 1 sec to allow for page refresh')
    time.sleep(1)

    # now pull the name of the store we are currently configured to work from
    return totalwine_driver_get_store(driver, defaultstore)

    # --------------------------------------------------------------------------

#### WINECLUB ####


# function used to extract the data from the DOM that was returned
def wineclub_extract_wine_from_DOM(winestore,index,titlelist,pricelist):
    global verbose

    
    # extract the values
    winename = titlelist[index].text
    wineprice = pricelist[index].text
    
    # regex the price field to match our expections
    match = re.search('\$(.*)$',wineprice)
    if match:
        wineprice = match.group(1)
    
    # now clean up $ and ,
    wineprice = wineprice.replace('$','').replace(',','')

    # return the dictionary
    return { 'wine_store' : winestore, 'wine_name' : winename, 'wine_price' : wineprice, 'wine_year' : '', 'label' : winestore }


# Search for the wine
def wineclub_search( srchstring, wineclub_driver ):
    global verbose

    winestore = 'WineClub'

    # Select the search box(es) and find if any are visbile - there can be more than one returned value
    search_box = wineclub_driver.find_elements_by_xpath('//*[@id="search"]')

    if pmsg: print('wineclub_search:len search box:', len(search_box))
    logger.info('search box count:%d', len(search_box))

    if len(search_box) > 0:
        search_box = search_box[0]
    else:
        # debugging
        if not 'took too long' in wineclub_driver.page_source:
            if pmsg: print('wineclub_driver:Go to theoriginalwineclub.com/wine.html web page')
            logger.info('refresh the page - no search box on first look')
    
            # call routine that finds teh search box and pulls back the search page
            found_search_box, search_box = get_wineclub_url( wineclub_driver )

            # check to see if we found the search box and if not set to none
            if not found_search_box:
                if pmsg: print('create_wineclub_selenium_driver:ERROR:did not find search string - setting driver to none')
                logger.warning('did not find search string - setting driver to none')
                saveBrowserContent( wineclub_driver, 'wineclub', 'wineclub_search:box_find' )
                return None
    
    # first check to see that the search box is displayed - if not visible then click the bottom that makes it visible
    if not search_box.is_displayed():
        # debugging
        if pmsg: print('wineclub_search:search box is not displayed - we want to click the button that displays it')
        logger.info('search box is not displayed - we want to click the button that displays it')
        # make the search box visible if it is not
        wineclub_driver.find_element_by_xpath('//*[@id="header-search-mobile"]/span').click()

    # debugging
    if pmsg: print('wineclub_search:search for:', srchstring)
    logger.info('search for:%s', srchstring)

    # send in the string to this box and press RETURN
    search_box.clear()
    search_box.send_keys(srchstring)
    search_box.send_keys(Keys.RETURN)
    
    # create the array that we will add to
    found_wines = []

    # get results back and look for the thing we are looking for - the list of things we are going to process
    titlelist = wineclub_driver.find_elements_by_class_name('product-name')
    pricelist = wineclub_driver.find_elements_by_class_name('regular-price')

    # message we have a problem
    if len(titlelist) != len(pricelist):
        if pmsg: print('wineclub_search:price and name lists different length:',srchstring,':len(wine):',len(titlelist),':len(price):',len(pricelist))
        logger.warning('price and name lists different length:%s:len(wine):%d:len(price):%d',srchstring,len(titlelist),len(pricelist))


    # now loop through the wines we found
    for index in range(len(pricelist)):
        try:
            found_wines.append( wineclub_extract_wine_from_DOM(winestore,index,titlelist,pricelist) )
        except Exception as e:
            exceptionPrint( e, 'wineclub_extract_wine_from_DOM', 'ERROR:page is stale:'+srchstring, True, wineclub_driver, 'wineclub', 'wineclub_search')
            return []

    # debugging
    if pmsg: print('wineclub_search:', srchstring, ':returned records:', len(found_wines))
    logger.info(rtnrecfmt, srchstring,  len(found_wines))

    # send back - no wine found if we did not find a wine
    if not found_wines:
        found_wines = returnNoWineFound( winestore )

    # return the wines we found
    return found_wines

# functino to get the URL for this wine store
def get_wineclub_url( driver ):
    # create the variable
    search_box = None

    # Open the website
    driver.get('https://theoriginalwineclub.com/wine.html')

    # try to get the search box
    cnt=10
    found_search_box = False
    while(cnt):
        try:
            search_box = driver.find_element_by_xpath('//*[@id="search"]')
            cnt = 0
        except  Exception as e:
            # did not find the search box
            if pmsg: print('wineclub_driver:waiting on search box (wait 1 second):', cnt)
            if pmsg: print('error:', str(e))
            logger.info('waiting on search box (wait 1 second):%d', cnt)
            if pmsg: print('error:%s', str(e))
            if 'took too long' in driver.page_source:
                # did not find a valid page
                if pmsg: print('wineclub_driver:page did not load - took too long - try again')
                logger.warning('page did not load - took too long - try again')
                driver.get('https://theoriginalwineclub.com/wine.html')
            time.sleep(1)
            cnt -= 1
        else:
            if not 'took too long' in driver.page_source:
                # get out of this loop we got what we wanted
                found_search_box = True
                cnt = 0
            else:
                # did not find a valid page
                if pmsg: print('wineclub_driver:page did not load - took too long - try again')
                logger.warning('page did not load - took too long - try again')
                driver.get('https://theoriginalwineclub.com/wine.html')
                cnt -= 1


    return found_search_box,search_box

# function to create a selenium driver for wineclub and get past popup
def create_wineclub_selenium_driver(defaultzip):
    global verbose

    # Using Chrome to access web
    driver=create_webdriver_from_global_var('wineclub_driver')


    # debugging
    if pmsg: print('wineclub_driver:Go to theoriginalwineclub.com/wine.html web page')
    logger.info('Go to theoriginalwineclub.com/wine.html web page')
    
    # call routine that finds teh search box and pulls back the search page
    found_search_box, search_box = get_wineclub_url( driver )

    # check to see if we found the search box and if not set to none
    if not found_search_box:
        if pmsg: print('create_wineclub_selenium_driver:ERROR:did not find search string - setting driver to none')
        logger.warning('did not find search string - setting driver to none')
        saveBrowserContent( driver, 'wineclub', 'create_wineclub_selenium_driver' )
        driver=None

    # debugging
    if pmsg: print('wineclub_driver:complete:---------------------------------------------------')
    logger.info('complete:---------------------------------------------------')
    

    # return the driver
    return driver


# --------------------------------------------------------------------------

#### HITIME ####

# function used to extract the data from the DOM that was returned
# pulling back the price record with the lowest price
def hitime_extract_wine_from_DOM(winestore,index,titlelist,pricelist):
    global verbose

    
    # extract the values for title
    winename = titlelist[index].text.upper()

    # now find the lowest of prices
    winepricemin=100000.00
    for winepricerec in pricelist:
        #if pmsg: print('winepricemin:', winepricemin, ':winepricerec:', winepricerec.text)
        winepriceflt = float(winepricerec.text.replace('$','').replace(',',''))
        if winepricemin > winepriceflt:
            winepricemin = winepriceflt
            # if pmsg: print('min set to:', winepricemin)

    # found the low price convert to string
    wineprice = str(winepricemin)
   
    # return the dictionary
    return { 'wine_store' : winestore, 'wine_name' : winename, 'wine_price' : wineprice,  'wine_year' : '', 'label' : winestore }


# Search for the wine
def hitime_search( srchstring, hitime_driver ):
    global verbose

    winestore = 'HiTimes'

    # if the srchstring is too short - don't do any work
    if len(srchstring) < 3:
        if pmsg: print('hitime_search:srchstring: {} :must be 3 char or greater-length: {} :returned records: None:'.format(srchstring, len(srchstring)))
        logger.info('srchstring: {} :must be 3 char or greater-length: {} :returned records: None:'.format(srchstring, len(srchstring)))
        return []
              
    search_boxes = find_elements_looped( hitime_driver, '//*[@id="search"]', 'by_xpath', 'hitime_search', 'hitime_driver_missing_search_box' )
    if not search_boxes:
        saveBrowserContent( hitime_driver, 'hitime', 'hitime_driver:missing_search_box' )
        # now get the page again - see if this fixes it
        if pmsg: print('hitime_search:get the URL again')
        logger.info('get the URL again')
        hitime_driver.get('https://hitimewine.net')
        search_box = find_elements_looped( hitime_driver, 'by_xpath', '//*[@id="search"]' )
        
    # failed to find the search box
    if not search_boxes:
        if pmsg: print('hitime_search:exiting program due to ERROR')
        logger.error('exiting program due to no search box being found')
        saveBrowserContent( hitime_driver, 'hitime', 'hitime_search' )
        exitWithError()
 

    # get the first displayed search_box
    for search_box in search_boxes:
        if search_box.is_displayed():
            # debugging
            if pmsg: print('hitime_search:search box is displayed:', search_box.is_displayed() )
            logger.info('search box is displayed:%s', search_box.is_displayed() )
            break

    # debugging
    if pmsg: print('hitime_search:search for:', srchstring)
    logger.info('search for:%s', srchstring)

    # send in the string to this box and press RETURN
    search_box.clear()
    search_box.send_keys(srchstring)
    search_box.send_keys(Keys.RETURN)
    
    # create the array that we will add to
    found_wines = []

    # loop until we get a response or until we run out of loop count
    results = find_elements_looped( hitime_driver, 'breadcrumbs', 'by_class_name', 'hitime_search', 'waiting for search response' )
    if not results:
        if pmsg: print('hitime_search:ERROR:no response - we exceed our loop count:', srchstring)
        logger.warning('no response - we exceed our loop count:%s', srchstring)
        saveBrowserContent( hitime_driver, 'hitime', 'hitime_search:not_results' )
        # update the website we are pointing at
        hitime_driver.get('https://hitimewine.net')
        # return no results
        return returnNoWineFound( winestore )

    # check to see that we got a search results page
    # and that our search string is in it
    results = find_elements_looped( hitime_driver, 'page-title-wrapper', 'by_class_name', 'hitime_search', 'waiting for search result string' )
    loopcnt = 4
    try:
        while results and srchstring.upper() not in results[0].text and loopcnt:
            if pmsg: print('htimes_search: srchstring not in srch result string:', loopcnt)
            logger.info('srchstring not in srch result string:%d', loopcnt)
            loopcnt -= 1
            time.sleep(2)
            results = find_elements_looped( hitime_driver, 'page-title-wrapper', 'by_class_name', 'hitime_search', 'waiting for search result string' )
    except:
        results = find_elements_looped( hitime_driver, 'page-title-wrapper', 'by_class_name', 'hitime_search', 'waiting for search result string' )

    # if pmsg: print out what we found
    for pagetitle in results:
        if pmsg: print('hitime_search:pagetitle:', pagetitle.text)
        logger.info('pagetitle:%s', pagetitle.text)


    # we got the page back - now pull out all the data we need from this page
    noresults1 = hitime_driver.find_elements_by_class_name('empty-catalog')
    noresults2 = hitime_driver.find_elements_by_class_name('notice')
    results = hitime_driver.find_elements_by_class_name('toolbar-number')
    entitylist = hitime_driver.find_elements_by_class_name('product-item-info') # list of returned items
    entitylist2 = hitime_driver.find_elements_by_class_name('product-info-main')  # single returned item
        
    if noresults1:
        if pmsg: print('hitime_search:empty-catalog-text:', noresults1[0].text)
        logger.info('empty-catalog-text:%s', noresults1[0].text)
        # debugging
        if pmsg: print('hitime_search:', srchstring, ':noresults1 - refresh the page we are looking at - returned records:  None')
        logger.info ('%s:returned records:NoWineFound - due to nosresults1', srchstring)
        # update the website we are pointing at
        hitime_driver.get('https://hitimewine.net')
        # return no results
        return  returnNoWineFound( winestore )

    if noresults2:
        if pmsg: print('hitime_search:message:', noresults2[0].text)
        logger.info('noresults2-message:%s',noresults2[0].text)
        # debugging
        if pmsg: print('hitime_search:', srchstring, ':noresults2 - refresh the page we are looking at - returned records:  None')
        logger.info ('%s:returned records:NoWineFound - due to nosresults2', srchstring)
        # update the website we are pointing at
        hitime_driver.get('https://hitimewine.net')
        # return no results
        return  returnNoWineFound( winestore )
    
    if results:
        resultcnt = int(results[0].text)
        if pmsg: print('hitime_search:resultcnt:', resultcnt)
        if pmsg: print('hitime_search:results[0].text:', results[0].text)
        logger.info('resultcnt:%d', resultcnt)
        logger.info('results[0].text:%s', results[0].text)
    else:
        resultcnt = 24

    # debugging
    if pmsg: print('hitime_search:lengthof:noresults1:{},noresults2:{},results:{},entitylist:{},entitylist2:{},resultcnt:{}'.format(len(noresults1),len(noresults2), len(results), len(entitylist), len(entitylist2), resultcnt))
    logger.info('lengthof:noresults1:{},noresults2:{},results:{},entitylist:{},entitylist2:{},resultcnt:{}'.format(len(noresults1),len(noresults2), len(results), len(entitylist), len(entitylist2), resultcnt))

    # change what we are looping on
    if entitylist2 and not entitylist:
        if pmsg: print('hitime_search:single wine found - swapping entitylist2 into entitylist')
        logger.info('single wine found - swapping entitylist2 into entitylist')
        entitylist = entitylist2
        
    # step through this list
    entitycount = 0
    for entity in entitylist:
        entitycount += 1
        if entitycount > resultcnt:
            if pmsg: print('hitime_search:entitycount:{} > resultcnt:{} - skipping'.format(entitycount,resultcnt))
            logger.info('entitycount:{} > resultcnt:{} - skipping'.format(entitycount,resultcnt))
            break

        # check entitycount to maxresults per page
        if entitycount > 25:
            if pmsg: print('hitime_search:entitycount:{} > max-items-per-page:{} - skipping'.format(entitycount,25))
            logger.info('entitycount:{} > max-items-per-page:{} - skipping'.format(entitycount,25))
            break

        # extract out for this entry these - we use elements so we don't need to try/catch
        try:
            if entitylist2 == entitylist:
                titlelist = entity.find_elements_by_class_name('page-title')
            else:
                titlelist = entity.find_elements_by_class_name('product-name')
            pricelistraw = entity.find_elements_by_class_name('price')
            pricelistreg = entity.find_elements_by_class_name('regular-price')
            pricelistspecial = entity.find_elements_by_class_name('special-price')
            pricelistwrapper = entity.find_elements_by_class_name('price-wrapper')
            if pricelistspecial:
                pricelistwrapper = pricelistspecial[0].find_elements_by_class_name('price')
        except Exception as e:
            if pmsg: print('hitime_search:entitycount:', entitycount)
            logger.info('entitycount:%d', entitycount)
            exceptionPrint( e, 'hitime_search', 'ERROR:extracting title and price lists:'+srchstring, True, hitime_driver, 'hitime', 'hitime_search' )
            if pmsg: print('hitime_search: {} : returned records:'.format(srchstring), len(found_wines))
            logger.info(rtnrecfmt, srchstring, len(found_wines))
            # capture and process errors if we get them
            try:
                resultidx = 0
                for result in results:
                    if pmsg: print('hitime_search:result[{}].text:{}'.format(resultidx, result.text))
                    logger.info('resultidx:%s:result.text:%s',resultidx, result.text)
                    resultidx += 1
            except Exception as e:
                exceptionPrint( e, 'hitime_search', 'ERROR:post error processing error:'+srchstring, True, hitime_driver, 'hitime', 'hitime_search' )

            return found_wines
            

        # debugging
        logger.debug('dump out the various things we just extracted')
        logger.debug('pricelistraw:len:%d', len(pricelistraw))
        logger.debug('pricelistreg:len:%d', len(pricelistreg))
        logger.debug('pricelistwrapper:len:%d', len(pricelistwrapper))
        logger.debug('-'*40)

        # pull out the entry of interest
        try:
            if len(pricelistwrapper):
                found_wines.append( hitime_extract_wine_from_DOM(winestore,0,titlelist,pricelistwrapper) )
            elif len(pricelistraw):
                found_wines.append( hitime_extract_wine_from_DOM(winestore,0,titlelist,pricelistraw) )
            else:
                found_wines.append( hitime_extract_wine_from_DOM(winestore,0,titlelist,pricelistreg) )

        except Exception as e:
            if pmsg: print('hitime_search:exception encounterd on entitycount:', entitycount)
            logger.info('exception encounterd on entitycount:%d', entitycount)
            exceptionPrint( e, 'hitime_extract_wine_from_DOM', 'ERROR:page is stale:'+srchstring, True, hitime_driver, 'hitime', 'hitime_search_extract_from_DOM' )
            if pmsg: print('hitime_search: {} : returned records:'.format(srchstring), len(found_wines))
            logger.info(rtnrecfmt, srchstring, len(found_wines))
            return found_wines


    # debugging
    if pmsg: print('hitime_search: {} : returned records:'.format(srchstring), len(found_wines))
    logger.info(rtnrecfmt, srchstring, len(found_wines))

    # if we did not get back records return that
    if not found_wines:
        return returnNoWineFound( winestore )

    # return the wines we found
    return found_wines

def hitime_starting_dialogue_click_closed( driver ):
    # check for the button and click it
    try:
        # find the element
        close_link = driver.find_element_by_xpath('//*[@id="contentInformation"]/div[2]/div[2]/a')
        loopcnt = 11
        while not close_link.is_displayed() and loopcnt:
            # increment the counter
            loopcnt -= 1
            # debugging
            if pmsg: print('hitime_driver:wait for the object to be displayed:', loopcnt)
            logger.info('wait for the object to be displayed:%d', loopcnt)
            # sleep
            time.sleep(2)

        # now we waited long enough - what do we do now?
        if close_link.is_displayed():
            # debugging
            if pmsg: print('hitime_driver:close_link.click')
            logger.info('close_link.click')
            # click the link
            close_link.click()
        else:
            # debugging - never ended up being displayed - so message this
            if pmsg: print('hitime_driver:close_link found but not displayed')
            logger.info('close_link found but not displayed')
    except NoSuchElementException:
        if pmsg: print('hitime_driver:close_link does not exist')
        logger.info('close_link does not exist')


# function to create a selenium driver for hitime and get past the close link
def create_hitime_selenium_driver(defaultzip):
    global verbose

    # Using Chrome to access web
    driver=create_webdriver_from_global_var('hitime_driver')

    # debugging
    if pmsg: print('hitime_driver:Go to hitimewine.net web page')
    logger.info('Go to hitimewine.net web page')
    
    # Open the website
    driver.get('https://hitimewine.net')

    # look for the search box
    results = find_elements_looped( driver, 'q', 'by_name', 'hitime_driver', 'waiting for search page to render')
    if not results:
        if pmsg: print('hitime_driver:ERROR:never found search page - return None:', srchstring)
        logger.warning('never found search page - return None:%s', srchstring)
        return None

    # if dialogue shows up - click it closed
    hitime_starting_dialogue_click_closed( driver )
    
    # make sure we have a search box in the page that we obtained
    try:
        search_box = driver.find_element_by_xpath('//*[@id="search"]')
    except  Exception as e:
        exceptionPrint( e, 'hitime_driver', 'ERROR:did not find search_box using xpath://*[@id="search"]:'+srchstring, True, driver, 'hitime', 'hitime_driver', exitPgm=True )


    # debugging
    if pmsg: print('hitime_driver:complete:---------------------------------------------------')
    logger.info('complete:---------------------------------------------------')
    

    # return the driver
    return driver


# --------------------------------------------------------------------------

#### WALLY ####


# function used to extract the data from the DOM that was returned
def wally_extract_wine_from_DOM(winestore,index,titlelist,pricelist):
    global verbose

    
    # extract the values
    winename = titlelist[index].text
    wineprice = pricelist[index].text
    
    # regex the price field to match our expections
    match = re.search('\$(.*)$',wineprice)
    if match:
        wineprice = match.group(1)
    
    # now clean up $ and ,
    wineprice = wineprice.replace('$','').replace(',','')

    # return the dictionary
    return { 'wine_store' : winestore, 'wine_name' : winename, 'wine_price' : wineprice, 'wine_year' : '', 'label' : winestore }


# Search for the wine
def wally_search( srchstring, wally_driver ):
    global verbose

    winestore = 'Wally-LA'
    
    # Select the search box(es) and find if any are visbile - there can be more than one returned value
    search_box = wally_driver.find_element_by_xpath('//*[@id="search"]')
    
    # first check to see that the search box is displayed - if not visible then click the bottom that makes it visible
    if not search_box.is_displayed():
        # debugging
        if pmsg: print('wally_search:search box is not displayed')
        logger.info('wally_search:search box is not displayed')

    # debugging
    if pmsg: print('wally_search:search for:', srchstring)
    logger.info('search for:%s', srchstring)

    # send in the string to this box and press RETURN
    search_box.clear()
    search_box.send_keys(srchstring)
    search_box.send_keys(Keys.RETURN)
    
    # pause for page to catch up
    time.sleep(1)

    # create the array that we will add to
    found_wines = []

    # grab the results - or - just put enough pause in here to let everything catch up
    results = find_elements_looped( wally_driver, 'breadcrumbs', 'by_class_name', 'wally_search', 'wait for first search response' )
    if not results:
        if pmsg: print('wally_search:ERROR:search results never returned a result:', srchstring)
        logger.warning('search results never returned a result:%s', srchstring)
        return returnNoWineFound( winestore )

    # grab the results - or - just put enough pause in here to let everything catch up
    results = find_elements_looped( wally_driver, 'category-products', 'by_class_name', 'wally_search', 'wait for search content' )
    if not results:
        if pmsg: print('wally_search:ERROR:search results never returned a result:', srchstring)
        logger.warning('search results never returned a result:%s', srchstring)
        return returnNoWineFound( winestore )

    # odd - but the javascript in the page drives the population of content - so we have to wait for this to happen
    loopcnt = 6
    resulttext = ''
    while not resulttext and loopcnt:
        try:
            resulttext = results[0].text
        except Exception as e:
            exceptionPrint( e, 'wally_search', 'ERROR:failed to get result.text for search on:'+srchstring, True, wally_driver, 'wally', 'wally_search' )
            if pmsg: print('wally_search:find_elements_looped again')
            logger.info('find_elements_looped again')
            results = find_elements_looped( wally_driver, 'category-products', 'by_class_name', 'wally_search', 'look for content again' )
            
        time.sleep(1)
        if pmsg: print('wally_search:waiting for result text to show up:result.text:', loopcnt)
        logger.info('waiting for result text to show up:loopcnt:%d', loopcnt)
        loopcnt -= 1
    
    
    # get the specifics we want
    results = wally_driver.find_elements_by_class_name('count-container')
    noresults = wally_driver.find_elements_by_class_name('searchspring-no_results')


    # if we get no results - we are done and return nothing
    if noresults:
        if pmsg: print('wally_search:no results returned for this wine')
        logger.info('no results returned for this wine:%s', srchstring)
        return returnNoWineFound( winestore )

    # check that we got results
    if not results:
        if pmsg: print('wally_search:ERROR:lack of response that is parsable - return no wines:', srchstring)
        logger.warning('lack of response that is parsable - return no wines:%s', srchstring)
        # saveBrowserContent( wally_driver, 'wally', 'wally_search')
        return returnNoWineFound( winestore )
        
    # we got results - figure out how many
    for result in results:
        try:
            if 'result' in result.text:
                winesfound = result.text.split()[1]
                if pmsg: print('wally_search:found wines:', winesfound)
                logger.info('found wines:%s', winesfound)
                break
            else:
                if pmsg: print('wally_search:unusable_result_text:', result.text)
                logger.info('unusable_result_text:%s', result.text)
        except Exception as e:
            exceptionPrint( e, 'wally_search', 'ERROR:failed to get result.text for search on:'+srchstring, True, wally_driver, 'wally', 'wally_search' )
            return []

    # create the array that we will add to
    found_wines = []

    # get results back and look for the thing we are looking for - the list of things we are going to process
    titlelist = wally_driver.find_elements_by_class_name('product-name')
    pricelist = wally_driver.find_elements_by_class_name('price-box')

    # debugging
    if pmsg: print('wally_search:pricelist records:',  len(pricelist))
    logger.info('pricelist records:%d',  len(pricelist))
    

    # message we have a problem
    if len(titlelist) != len(pricelist):
        if pmsg: print('wally_search:price and name lists different length:',srchstring,':len(wine):',len(titlelist),':len(price):',len(pricelist))
        logger.info('price and name lists different length:%s:len(wine):%d:len(price):%d',srchstring,len(titlelist),len(pricelist))
        # check to see if we don't have enough titles for prices
        if len(titlelist) < len(pricelist):
            if pmsg: print('wally_search:len-titlelist:',len(titlelist))
            if pmsg: print('wally_search:len-pricelist:',len(pricelist))
            if pmsg: print('wally_search:exitting program due to ERROR:titles are less than prices:', srchstring)
            if pmsg: print('wally_search:actually we just return an empty list and SKIP this wine')
            logger.info('len-titlelist:%d',len(titlelist))
            logger.info('len-pricelist:%d',len(pricelist))
            logger.info('exitting program due to ERROR:titles are less than prices:%s', srchstring)
            logger.info('actually we just return an empty list and SKIP this wine')
            saveBrowserContent( wally_driver, 'wally', 'wally_search')
            return found_wines

    # now loop through the wines we found
    for index in range(len(pricelist)):
        found_wines.append( wally_extract_wine_from_DOM(winestore,index,titlelist,pricelist) )

    # debugging
    logger.info(rtnrecfmt, srchstring, len(found_wines))

    if not found_wines:
        return returnNoWineFound( winestore )

    # return the wines we found
    return found_wines

# function to create a selenium driver for wallys
def create_wally_selenium_driver(defaultzip):
    global verbose

    # Using Chrome to access web
    driver=create_webdriver_from_global_var('wally_driver')

    # debugging
    if pmsg: print('wally_driver:Go to www.wallywine.com web page')
    logger.info('Go to www.wallywine.com web page')
    
    # Open the website
    try:
        driver.get('https://www.wallywine.com')
        search_box = driver.find_element_by_xpath('//*[@id="search"]')
    except Exception as e:
        exceptionPrint( e, 'wally_driver', 'ERROR:unable to get to the web site', True, driver, 'wally', 'wally_driver' )
        if pmsg: print('wally_driver:failed:REMOVING this store from this run')
        logger.warning('REMOVING this store from this run')
        driver = None

    # check to see if the dialogue is up and close it if it is
    close_btn = driver.find_elements_by_class_name('NostoCloseButton')
    if close_btn and close_btn[0].is_displayed():
        if pmsg: print('wally_driver:closing intro dialogue box')
        logger.info('wally_driver:closing intro dialogue box')
        close_btn[0].click()

    # debugging
    if pmsg: print('wally_driver:complete:---------------------------------------------------')
    logger.info('complete:---------------------------------------------------')
    

    # return the driver
    return driver


#### PAVILLIONS ####


# function used to extract the data from the DOM that was returned
def pavillions_extract_wine_from_DOM(winestore,index,titlelist,pricelist):
    global verbose

    
    # extract the values
    winename = titlelist[index].text
    wineprice = pricelist[index].text

    # if pmsg: print('pavillions_extract_wine_from_DOM:wineprice:',wineprice)

    # regex the price field to match our expections
    match = re.search('\$(.*)$',wineprice)
    if match:
        wineprice = match.group(1)
    
    # now clean up $ and ,
    wineprice = wineprice.replace('$','').replace(',','')

    # if the price is zero - return non
    if not wineprice:
        if pmsg: print('pavillions_extract_wine_from_DOM: no wine price - return None:', pricelist[index].text, ':', winename)
        logger.warning('no wine price - return None:%s:%s', pricelist[index].text, winename)
        return None

    # apply the 10% discount for buying 6 or more - but kill any rounding
    wineprice = str( int(float(wineprice)*100*0.9)/100 )

    # return the dictionary
    return { 'wine_store' : winestore, 'wine_name' : winename, 'wine_price' : wineprice, 'wine_year' : '', 'label' : winestore }


# Search for the wine
def pavillions_search( srchstring, pavillions_driver ):
    global verbose
    global test
    global pavillions_search_xpath

    winestore = 'Vons'

    # debugging
    if pmsg: print('pavillions_search:go to search page:https://shop.pavilions.com/home.html')
    logger.info('go to search page:https://shop.pavilions.com/home.html')

    # force entry on to the search page first
    if not get_url_looped( pavillions_driver, 'https://www.pavilions.com/shop', 'pavillions_search' ):
        if pmsg: print('pavillions_search:ERROR:never got page for this search - return nothing')
        logger.warning('never got page for this search - return nothing')
        return []


    # debugging
    if pmsg: print('pavillions_search:find the search_box')
    logger.info('pavillions_search:find the search_box')

    # find the search box (change the xpath to the search window)
    search_box = pavillions_find_search_box(pavillions_driver)
    
    # check to see the search box is visible - if not we have a problem
    if not search_box.is_displayed():
        # debugging
        logger.warning('search box 2 is not displayed - this is a problem - exit')
        # close the browser because we are going to quit
        if pmsg: print('pavilliions_search:exitting program due to ERROR:missing search box')
        saveBrowserContent( pavillions_driver, 'pav', 'pavillions_search' )
        pavillions_driver.quit()
        exitWithError()

    # debugging
    if pmsg: print('pavillions_search:search for:', srchstring, ' in wines:search_box:', search_box.get_attribute('name'))
    logger.info('search for:%s:in wines search_box:%s', srchstring, search_box.get_attribute('name'))

    # send in the string to this box and press RETURN
    search_box.clear()
    search_box.send_keys(srchstring + ' in wines')
    search_box.send_keys(Keys.RETURN)
    
    # create the array that we will add to
    found_wines = []

    # it may take time to get this to show up - so lets build a small loop here
    returned_result = find_elements_looped( pavillions_driver, 'search--title', 'by_class_name', 'pavillions_search', 'waiting for webpage')
    # first test - see if we got no results found - if so return the empty array
    if not returned_result:
        if pmsg: print('pavillions_search:', srchstring, ':no results returned - refresh the page we are looking at')
        if pmsg: print('pavillions_search:actually we just return an empty list and SKIP this wine')
        logger.info(rtnrecfmt, srchstring, 0)
        return returnNoWineFound( winestore )

    # result text
    result_text = returned_result[0].text

    # now check to see if the answer was no result
    if re.match('No results', result_text):
        # debugging
        if pmsg: print('pavillions_search:', srchstring, ':no results returned - refresh the page we are looking at')
        logger.info(rtnrecfmt, srchstring, 0)
        # return a record that says we could not find the record
        return returnNoWineFound( winestore )
    else:
        # debugging
        if pmsg: print('pavillions_search:following found results:',  result_text)
        logger.info('found results:%s',  result_text)

    # get results back and look for the thing we are looking for - the list of things we are going to process
    titlelist = pavillions_driver.find_elements_by_class_name('product-title')
    pricelist = pavillions_driver.find_elements_by_class_name('product-price')

    # convert to text - commented out for now - we can come back and look at this in the future
    if False:
        # convert web objects to text
        titlelisttext = [i.text for i in titlelist]
        pricelisttext = [i.text for i in pricelist]
        # debugging
        if pmsg: print('titlelisttext:', titlelisttext)
        if pmsg: print('pricelisttext:', pricelisttext)

    # message we have a problem
    if len(titlelist) != len(pricelist):
        if pmsg: print('pavillions_search:price and name lists different length:',srchstring,':len(wine):',len(titlelist),':len(price):',len(pricelist))
        logger.info('price and name lists different length:%s:len(wine):%d:len(price):%d',srchstring,len(titlelist),len(pricelist))

    # we are going to search for the min of these two lists
    resultcount = min( len(titlelist), len(pricelist) )

    # debugging
    if pmsg: print('pavillions_search:', srchstring, ':returned records:',  resultcount )
    logger.info(rtnrecfmt,srchstring,  resultcount )

    # now loop through the wines we found
    try:
        for index in range(resultcount):
            result = pavillions_extract_wine_from_DOM(winestore,index,titlelist,pricelist)
            if result:
                found_wines.append( result )
    except Exception as e:
        if pmsg: print('pavillions_search:index:',index)
        logger.info('index:%d',index)
        exceptionPrint( e, 'pavillions_search', 'ERROR:stale page', True, pavillions_driver, 'pav', 'pavillions_search' )
        if pmsg: print('pavillions_search:returning found_wines:', len(found_wines))
        logger.info('returning found_wines:%d', len(found_wines))
        return found_wines


    if not found_wines:
        return returnNoWineFound( winestore )

    # return the wines we found
    return found_wines

# generic find the search box
def pavillions_find_search_box(driver):
    search_box = pavillions_find_search_box_by_class_name(driver)
    if search_box:
        return search_box
    search_box = pavillions_find_search_box_by_id(driver)
    if search_box:
        return search_box
    search_box = pavillions_find_search_box_by_xpaths(driver)
    if search_box:
        return search_box

# find the search box by id
def pavillions_find_search_box_by_id(driver):
    # create the variable
    search_box=None
    try:
        # change the variable by look up
        search_box = driver.find_element_by_id('search-img')
        if pmsg: print('pavillions_find_search_box_by_id:search-img:found')
        logger.info('search-img:found')
    except Exception as e:
        if pmsg: print('pavillions_find_search_box_by_id:search-img:NOT-found')
        logger.info('search-img:NOT-found')

    if not search_box.is_displayed():
        search_box = None

    return search_box

# find the search box by class_name
def pavillions_find_search_box_by_class_name(driver):
    # create the variable
    search_box=None
    try:
        # change the variable by look up
        search_boxes = driver.find_elements_by_class_name('ecomm-search')
        # found some number of matches - find the one that is displayed
        counter=0
        for search_box in search_boxes:
            if search_box.is_displayed():
                if pmsg: print('pavillions_find_search_box_by_class_name:ecomm-search:found at index:', counter)
                logger.info('ecomm-search:found at index:%d', counter)
                break
            # increment the counter if we are not done
            counter+=1
        # check the final search_box
        if not search_box.is_displayed():
            search_box=None
            if pmsg: print('pavillions_find_search_box_by_class_name:ecomm-search:NOT-found-displayed')
            logger.info('ecomm-search:NOT-found-displayed')
    except Exception as e:
        if pmsg: print('pavillions_find_search_box_by_class_name:ecomm-search:NOT-found')
        logger.info('ecomm-search:NOT-found')

    # deal with the fact we did not find the search box again - by setting to None
    if not (search_box and search_box.is_displayed()):
        if pmsg: print('pavillions_find_search_box_by_class_name:ERROR:no search box - save screen and review')
        logger.warning('no search box - save screen and review')
        saveBrowserContent( driver, 'pav', 'pavillions_find_search_box_by_class_name' )
        # make sure it is set to None
        search_box = None

    return search_box


# find the search box by xpaths
def pavillions_find_search_box_by_xpaths(driver):
    # define the list of search strings we can use
    pavillions_search_xpaths = [
        '/html/body/div[1]/div/div/div[1]/div/div/div/div/div[2]/div[4]/form/div/div/input',
        '/html/body/div[1]/div/div/div[1]/div/div/div/div/div[1]/div[4]/form/div/div/input',
        '//*[@id="search-img"]',
    ]

    # what about class name look up (might check to see if we can look up on htis)
    # class="form-control input-search ecomm-search product-search-enabled"
    # driver.find_elements_by_class_name("form-control input-search ecomm-search product-search-enabled")

    # another strategy - find the displayed object base on classname search
    # matches=driver.find_elements_by_class_name('ecomm-search')
    # for searchbox in matches
    #    if searchbox.is_displayed():
    #        break;
    #
    # but if we use this - we need to figure out what to do with the
    # pavillions_search_xpath global variable that is used else where
    #
    # or convert this search logic in a function that gets called to find
    # the search box on each page.
    
    # loop through search strings to find the one that works
    for pavillions_search_xpath in pavillions_search_xpaths:
        # validate the search_box is visible
        try:
            if pmsg: print('pavillions_find_search_box_by_xpaths:find search:', pavillions_search_xpath)
            logger.info('find search:%s', pavillions_search_xpath)
            search_box = driver.find_element_by_xpath( pavillions_search_xpath )
        except Exception as e:
            if pmsg: print('pavillions_find_search_box_by_xpaths:ERROR:search box xpath not valid')
            logger.info('search box xpath not valid')
            continue

        # check to see the search box is visible - if not we have a problem
        if not search_box.is_displayed():
            # debugging
            if pmsg: print('pavillions_find_search_box_by_xpaths:ERROR:search box is not displayed - this is a problem - try another')
            logger.info('search box is not displayed - this is a problem - try another')
            #if pmsg: print_html_elem('pavillions_find_search_box_by_xpaths:search_box:', 0, search_box)
            # clear the search string
            pavillions_search_xpath = ''
            # close the browser because we are going to quit
            # driver.quit()
            # exitWithError()

            # clear the search_box we found - it is not the one we want
            search_box=None
        else:
            if test:
                if pmsg: print('pavillions_find_search_box_by_xpaths:test-enabled:search box:found')
            # now break out of hte loop we have what we need
            if pmsg: print('pavillions_find_search_box_by_xpaths:found_search_box:', pavillions_search_xpath)
            logger.info('found_search_box:%s', pavillions_search_xpath)
            # break out we have found the one we want to use
            break

    return search_box


def set_pavillions_shopping_zipcode(driver, defaultzip, storename):
    # debugging
    if pmsg: print('set_pavillions_shopping_zipcode:setting zipcode - get url to do this')
    logger.info('setting zipcode - get url to do this')

    # drive to the page that asks us the right queston
    if not get_url_looped( driver, 'https://www.pavilions.com/?action=changeStore', 'set_pavillions_shopping_zipcode'):
        if pmsg: print('set_pavillions_shopping_zipcode:ERROR:never got page for this changeStore - return nothing')
        logger.warning('never got page for this changeStore - program terminated')
        saveBrowserContent( driver, 'pav', 'set_pavillions_shopping_zipcode' )
        if pmsg: print('Program TERMINATED')
        exitWithError()


    # get the input box
    results = find_elements_looped( driver, 'fulfillment-content__search-wrapper__input', 'by_class_name', 'set_pavillions_shopping_zipcode', 'allowing changeStore page time to render')
    
    if not results:
        if pmsg: print('set_pavillions_shopping_zipcode:ERROR:never found:fulfillment-content__search-wrapper__input:', srchstring)
        logger.warning('never found:fulfillment-content__search-wrapper__input:%s', srchstring)
        saveBrowserContent( driver, 'pav', 'set_pavillions_shopping_zipcode' )
        if pmsg: print('Program TERMINATED')
        exitWithError()

    # message
    if pmsg: print('set_pavillions_shopping_zipcode:results returned:', len(results))
    logger.info('results returned:%d', len(results))

    # set the zipbox
    zipcode_box = results[0]

    # give time for this box to become displayed
    loopcnt=6
    while not zipcode_box.is_displayed() and loopcnt:
        # message
        if pmsg: print('set_pavillions_shopping_zipcode:zipcode_box is displayed:', zipcode_box.is_displayed(), ':loopcnt:', loopcnt)
        logger.info('zipcode_box is_displayed:%s:loopcnt:%d', zipcode_box.is_displayed(), loopcnt)
        time.sleep(2)
        loopcnt -= 1

    # message
    if pmsg: print('set_pavillions_shopping_zipcode:zipcode_box is displayed:', zipcode_box.is_displayed())
    logger.info('zipcode_box is_displayed:%s', zipcode_box.is_displayed())

    ### ZIPCODE - check to see if the zip code is selectable
    try:
        zipcode_box.clear()
        zipcode_box.send_keys(defaultzip)
        zipcode_box.send_keys(Keys.RETURN)
    except Exception as e:
        exceptionPrint( e,'set_pavillions_shopping_zipcode' , 'unable to populate zipcode_box:', True, driver, 'pav', 'set_pavillions_shopping_zipcode' )

    # debugging
    if pmsg: print('set_pavillions_shopping_zipcode:zipcode populated')
    logger.info('zipcode populated')

    # now get the list of card stores returned
    cardstore=find_elements_looped( driver, 'card-store', 'by_class_name', 'set_pavillions_shopping_zipcode', 'allow store list page to render', loopcnt=6)
    if not cardstore:
        if pmsg: print('set_pavillions_shopping_zipcode:ERROR:list of stores never returned')
        logger.warning('list of stores never returned')
        saveBrowserContent( driver, 'pav', 'set_pavillions_shopping_zipcode' )
        if pmsg: print('Program TERMINATED')
        exitWithError()
        
    if pmsg: print('set_pavillions_shopping_zipcode:list of store options obtained - step through them to find the one we want')
    logger.info('list of store options obtained - step through them to find the one we want')

    # step through these stores until we find the one we want
    for store in cardstore:
        if pmsg: print('set_pavillions_shopping_zipcode:stepping through stores:', store.text)
        logger.info('stepping through stores:%s', store.text)
        if storename in store.text:
            try:
                # we have a match
                storebtn=store.find_element_by_class_name('card-store-btn')
                storebtn.click()
                # sleep here
                if pmsg: print('set_pavillions_shopping_zipcode:clicked store button:', store.text)
                logger.info('clicked store button:%s', store.text)
                time.sleep(3)
            except Exception as e:
                exceptionPrint( e,'set_pavillions_shopping_zipcode' , 'found button and could not click it:'+storename, True, driver, 'pav', 'set_pavillions_shopping_zipcode' )

            return

    #debugging
    if pmsg: print('set_pavillions_shopping_zipcode:No matching address')
    logger.info('No matching address')



# function to create a selenium driver for pavillions and enter zipcode
def create_pavillions_selenium_driver(defaultzip,storename='26022 Marguerite Pkwy'):
    global verbose

    # global variable that defines which search box string to use
    global pavillions_search_xpath

    # Using Chrome to access web
    driver=create_webdriver_from_global_var('pavillions_driver')

    # debugging
    if pmsg: print('pavillions_driver:Go to shop.pavillions.com web page')
    logger.info('Go to shop.pavillions.com web page')
    
    # Open the website
    #driver.get('https://shop.pavilions.com/home.html')
    driver.get('https://www.pavilions.com/shop/aisles/beverages.2210.html')

    # check the default zip to see if it matches
    if pmsg: print('pavillions_driver:check current zipcode setting')
    logger.info('check current zipcode setting')
    driverzip = None
    try:
        if pmsg: print('pavillions_driver:finding the current zipcode')
        logger.info('finding the current zipcode')
        # pull out the current name
        shopInZip = driver.find_element_by_class_name('reserve-nav__current-instore-text')
        # check to see if it matches
        if shopInZip.text and storename in shopInZip.text:
            # we already have the zip we want - no reason to set it
            if pmsg: print('pavillions_driver:already set to defaultzip')
            logger.info('already set to defaultzip')
            # capture the driver zip
            driverzip = defaultzip
        else:
            if pmsg: print('pavillions_driver:current zip not a match:currently set as:', shopInZip.text)
            logger.info('current zip not a match:currently set as:%s', shopInZip.text)
    except:
        if pmsg: print('pavillions_driver:ERROR:unable to lookup:guest-pref-panel-zip')
        logger.warning('unable to lookup:guest-pref-panel-zip')

    # lookup the zipcode if not set
    if not driverzip:
        if pmsg: print('pavillions_driver:calling routine to set zipcode')
        logger.info('calling routine to set zipcode')
        set_pavillions_shopping_zipcode(driver,defaultzip,storename)

    ### SEARCH_BOX

    # there are 3 different ways to find the search box
    # 1) id='search-img'
    # 2) class_name='ecomm-search'
    # 3) xpath with a list of search pathes
    search_box = pavillions_find_search_box(driver)
    
    # check to see we have a search string
    if not search_box:
        if pmsg: print('create_pavillions_selenium_driver:ERROR:no search box found')
        logger.warning('no search box found')
        # save this page for future research
        saveBrowserContent( driver, 'pav', 'pav_driver' )
        #
        # close the browser because we are going to quit
        driver.quit()
        exitWithError()
        

    # debugging
    if pmsg: print('pavillions_driver:complete:---------------------------------------------------')
    logger.info('complete:---------------------------------------------------')
    
    # return the driver
    return driver


# ----------------------------------------------------


#### WINEX ####


# function used to extract the data from the DOM that was returned
def winex_extract_wine_from_DOM(winestore,titlelist,pricelist):
    global verbose

    
    # extract the values
    winename = titlelist[0].text
    wineprice = pricelist[0].text
    
    # regex the price field to match our expections
    match = re.search('\$(.*)$',wineprice)
    if match:
        wineprice = match.group(1)
    
    # now clean up $ and ,
    wineprice = wineprice.replace('$','').replace(',','')

    # return the dictionary
    return { 'wine_store' : winestore, 'wine_name' : winename, 'wine_price' : wineprice, 'wine_year' : '', 'label' : winestore }


# Search for the wine
def winex_search( srchstring, winex_driver ):
    global verbose

    winestore = 'WineEx'

    # debugging
    if pmsg: print('winex_search:search for:', srchstring)
    logger.info('search for:%s', srchstring)
    

    # create the url of interest
    url = 'https://www.winex.com/catalogsearch/result/?q=%s' % srchstring

    # get this page
    winex_driver.get(url)

    # create the array that we will add to
    found_wines = []

    # get results back and look for the thing we are looking for - the list of things we are going to process
    winelist  = winex_driver.find_elements_by_class_name('product-item-info')

    # check to see if we got an item count also
    items = winex_driver.find_elements_by_class_name('toolbar-number')
    itemcnt = 24
    if items:
        itemcnt = int(items[0].text)
        if pmsg: print('winex_search:items returned by search:', itemcnt)
        logger.info('items returned by search:%d', itemcnt)

    # message
    if pmsg: print('winex_search:found wines:', len(winelist))
    logger.info('found wines:%d', len(winelist))
          
    # now step through this list of wines and pull out the wines of interest
    index=0
    for wine in winelist:
        if index > itemcnt-1:
            if pmsg: print('winex_search:skipped because index:{} greater than found wines less one:{}'.format(index, itemcnt-1))
            logger.info('skipped because index:%d:greater than found wines less one:%d',index, itemcnt-1)
            break

        # debugging
        # if pmsg: print('winex_search:working on index:', index)
        didNotFail = True

        try:
            titlelist = wine.find_elements_by_class_name('product-item-link')
            availlist = wine.find_elements_by_class_name('stock-status-wx')
            pricelist = wine.find_elements_by_class_name('price')
        except Exception as e:
            if pmsg: print('winex_search:index:', index, ':was skipped due to exception:', str(e))
            logger.info('index:%d:was skipped due to exception:%s', index, str(e))
            titlelist = None
            availlist = None
            pricelist = None
            didNotFail = False

        if titlelist and availlist and pricelist:
            if availlist[0].text == 'In Stock':
                found_wines.append( winex_extract_wine_from_DOM(winestore,titlelist,pricelist) )
            elif availlist[0].text == 'Out of Stock':
                if pmsg: print('winex_search:skipped:out of stock:', titlelist[0].text)
                logger.info('skipped:out of stock:%s', titlelist[0].text)
        else:
            if didNotFail and titlelist:
                try:
                    if pmsg: print('winex_search:index:', index, ':skipping wine missing price or availability:', titlelist[0].text)
                    logger.info('index:%d:skipping wine missing price or availability:%s', index, titlelist[0].text)
                except:
                    if pmsg: print('winex_search:index:', index, ':skipping wine missing price or availability:')
                    logger.info('index:%d:skipping wine missing price or availability:', index)

        index += 1
                

    # debugging
    if pmsg: print('winex_search:', srchstring, ':returned records:', len(found_wines))
    logger.info(rtnrecfmt, srchstring, len(found_wines))

    if not found_wines:
        return returnNoWineFound( winestore )

    # return the wines we found
    return found_wines


# function to create a selenium driver for winexs
def create_winex_selenium_driver(defaultzip):
    global verbose

    # Using Chrome to access web
    driver=create_webdriver_from_global_var('winex_driver')

    # debugging
    if pmsg: print('winex_driver:Go to www.winex.com web page')
    logger.info('Go to www.winex.com web page')
    
    # Open the website
    if not get_url_looped( driver, 'https://www.winex.com', 'winex_driver' ):
        if pmsg: print('winex_driver:ERROR:removing this store from this run')
        logger.warning('removing this store from this run')
        driver = None

    # debugging
    if pmsg: print('winex_driver:complete:---------------------------------------------------')
    logger.info('complete:---------------------------------------------------')
    

    # return the driver
    return driver


# ----------------------------------------------------

### NAPA CAB ####

def napacab_over21( driver, debug=False ):
    # find the over21 button
    btns = driver.find_elements_by_class_name('pxpop-link')
    # loop until we clear out this btns
    loopcnt = 4
    while btns and loopcnt:
        # step through the buttons
        btncnt=0
        for btn in btns:
            btncnt += 1
            try:
                if btn.get_attribute('innerText') == "I'M OVER 21":
                    btn.click()
                    if pmsg: print('napacab_over21:pressed im over 21 button:', btncnt, ':', loopcnt)
                    logger.info('pressed im over 21 button:%s:%d', btncnt, loopcnt)
                    break

            except Exception as e:
                exceptionPrint( e, 'napacab_over21', 'tried to click the over21 button', True, driver, 'napacab', 'napacab_over21' )
                if pmsg: print('napacab_over21:ignoring this error')
                logger.info('ignoring this error')
                return

        # find the over21 button - should be gone
        btns = driver.find_elements_by_class_name('pxpop-link')
        loopcnt -= 1


def napacab_email_signup( driver, debug=False ):
    # find the email entry object
    emails = driver.find_elements_by_class_name('pxpop-email')
    # if we did something then find the close object
    if not emails:
        return

    # clear that field - to give it focus
    if pmsg: print('napacab_email_signup:found email popup:', len(emails))
    if pmsg: print('napacab_email_signup:clear email field - to get focus')
    logger.info('found email popup:%d', len(emails))
    logger.info('clear email field - to get focus')
    try:
        emails[0].clear()
    except Exception as e:
        exceptionPrint( e, 'napacab_email_signup', 'clear email signup ', True, driver, 'napacab', 'napacab_email_signup' )


    # find the close button
    btns = driver.find_elements_by_class_name('pxpop-close')

    # show number of buttons found
    if pmsg: print('napacab_email_signup:found close buttons:', len(btns))
    logger.info('found close buttons:%d', len(btns))
    

    # step through the buttons
    btncnt = 0
    for btn in btns:
        btncnt += 1
        if btn.is_displayed():
            if pmsg: print('napacab_email_signup:press email signup close button:', btncnt)
            logger.info('press email signup close button:%d', btncnt)
            try:
                btn.click()
            except Exception as e:
                exceptionPrint( e, 'napacab_email_signup', 'closing email signup button', True, driver, 'napacab', 'napacab_email_signup' )
                if pmsg: print('napacab_email_signup:force click through javascript')
                logger.info('force click through javascript')
                driver.execute_script("arguments[0].click();", btn)
                saveBrowser( driver, 'napacab', 'napacab_email_signup:forced click on email - get rid of this after debugging' )
                if pmsg: print('napacab_email_signup:ignoring this error')
                logger.info('ignoring this error')

            break


# function used to extract the data from the DOM that was returned
def napacab_extract_wine_from_DOM(winestore,index,titlelist,pricelist):
    global verbose

    
    # extract the values
    winename = titlelist[index].text
    wineprice = pricelist[index*2].text
    
    # regex the price field to match our expections
    match = re.search('\$(.*)$',wineprice)
    if match:
        wineprice = match.group(1)
    
    # now clean up $ and ,
    wineprice = wineprice.replace('$','').replace(',','')

    # return the dictionary
    return { 'wine_store' : winestore, 'wine_name' : winename, 'wine_price' : wineprice, 'wine_year' : '', 'label' : winestore }


# determine if this object is the one that tells us the number of returned entries per searched item
def napacab_return_results( napacab_driver, srchstring ):
    try:
        results = napacab_driver.find_elements_by_class_name('page-heading')
        for result in results:
            if pmsg: print('napacab_return_results:result.text:', result.text)
            logger.info('result.text:%s', result.text)
            if 'result' in result.text:
                if srchstring in result.text:
                    return results
                else:
                    if pmsg: print('napacab_return_results:result.text does not contain srchstring:', srchstring)
                    logger.info('result.text does not contain srchstring:%s', srchstring)
                    # saveBrowserContent( napacab_driver, 'napacab', 'napacab_return_results')
    except Exception as e:
        if pmsg: print('napacab_return_results:selenium exception:', str(e))
        if pmsg: print('napacab_return_results:page changed while processing - loop again')
        logger.info('selenium exception:%s', str(e))
        logger.info('page changed while processing - loop again')
        # exceptionPrint( e, 'napacab_return_results', 'evaluating returned results', True, napacab_driver, 'napacab', 'napacab_return_results' )

    # did not find that answer - so return back blank
    return []


# Search for the wine
def napacab_search( srchstring, napacab_driver ):
    global verbose

    winestore = 'NapaCab'

    # check for this dialogue before we start
    napacab_over21( napacab_driver )
    napacab_email_signup( napacab_driver )

    # Select the search box(es) and find if any are visbile - there can be more than one returned value
    results = napacab_driver.find_elements_by_xpath('//*[@id="search_query"]')

    # check to see if we found the search box
    if results:
        search_box = results[0]
    else:
        if pmsg: print('napacab_search:ERROR:did not find the search box - terminating')
        logger.error('did not find the search box - terminating')
        saveBrowserContent( napacab_driver, 'napacab', 'napacab_search:box_find' )
        exitWithError('napacab_search:search_box length was zero')
    
    # first check to see that the search box is displayed - if not visible then click the bottom that makes it visible
    if not search_box.is_displayed():
        # debugging
        if pmsg: print('napacab_search:search box is not displayed - we want to click the button that displays it')
        logger.info('search box is not displayed - we want to click the button that displays it')
        # make the search box visible if it is not
        napacab_driver.find_element_by_xpath('//*[@id="header-search-mobile"]/span').click()

    # debugging
    if pmsg: print('napacab_search:search for:', srchstring)
    logger.info('search for:%s', srchstring)

    # send in the string to this box and press RETURN
    search_box.clear()
    search_box.send_keys(srchstring)
    search_box.send_keys(Keys.RETURN)


    # look for the page heading
    results= napacab_return_results( napacab_driver, srchstring )
    loopcnt = 6
    while not results and loopcnt:
        if pmsg: print('napacab_search:waiting for web page to respond:', loopcnt)
        logger.info('waiting for web page to respond:%d', loopcnt)
        loopcnt -= 1
        time.sleep(3)
        results= napacab_return_results( napacab_driver, srchstring )
        

    # create the array that we will add to
    found_wines = []

    # check to see if we got any results
    if not results:
        if pmsg: print('napacab_search:ERROR:web site never responded - returning nothing and moving on:', srchstring)
        logger.warning('web site never responded - returning nothing and moving on:%s', srchstring)
        saveBrowserContent( napacab_driver, 'napacab', 'napacab_search' )
        # return noWineFound for now - but there is a bigger issue
        return  returnNoWineFound( winestore )

    # display what we got back
    if pmsg: print('napacab_search:results-length:', len(results))
    if pmsg: print('napacab_search:result.text:', results[0].text)
    logger.info('results-length:%d', len(results))
    logger.info('result.text:%s', results[0].text)

    # check to see if we got anything back
    if results[0].text.split(' ')[0] == '0':
        if pmsg: print('napacab_search:', srchstring, ':returned records: 0')
        logger.info ( rtnrecfmt, srchstring, 0 )
        # return a record that says we could not find the record
        return  returnNoWineFound( winestore )

    # get product informatoin
    prodcount = napacab_driver.find_elements_by_id("search-results-product-count")
    if pmsg: print('napacab_search:product count:', prodcount[0].text)
    logger.info('product count:%s', prodcount[0].text)
    if prodcount[0].text.replace('Products (','').replace(')','') == '0':
        if pmsg: print('napacab_search:', srchstring, ':returned records: 0')
        logger.info ( rtnrecfmt, srchstring, 0 )
        # return a record that says we could not find the record
        return  returnNoWineFound( winestore )


    # get results back and look for the thing we are looking for - the list of things we are going to process
    try:
        titlelist = napacab_driver.find_elements_by_class_name('card-title')
        pricelist = napacab_driver.find_elements_by_class_name('price--main')
    except:
        if pmsg: print('napacab_search:ERROR:failed to find card-title or price-main:', srchstring)
        logger.warning('failed to find card-title or price-main:%s', srchstring)
        # save this page for future research
        saveBrowserContent( napacab_driver, 'napacab', 'napacab_search' )
        # return noWineFound for now - but there is a bigger issue
        return  returnNoWineFound( winestore )
        
    # message we have a problem
    if len(titlelist)*2 != len(pricelist):
        if pmsg: print('napacab_search:price and name lists different length:',srchstring,':len(wine):',len(titlelist),':len(price):',len(pricelist))
        logger.info('price and name lists different length:%s:len(wine):%d:len(price):%d',srchstring,len(titlelist),len(pricelist))

    # messageing
    if pmsg: print('napacab_search:titlelist-length:', len(titlelist))
    logger.info('titlelist-length:%d', len(titlelist))

    # now loop through the wines we found
    try:
        for index in range(len(titlelist)):
            found_wines.append( napacab_extract_wine_from_DOM(winestore,index,titlelist,pricelist) )
    except Exception as e:
        exceptionPrint( e, 'napacab_search-extract_wine_from_DOM', 'extract out wines', True, napacab_driver, 'napacab', 'napacab_search-extract_wine_from_DOM' )
        if pmsg: print('napacab_search:moving on to next wine')
        logger.info('napacab_search:moving on to next wine')

    # messaging
    if pmsg: print('napacab_search:', srchstring, ':returned records:', len(found_wines))
    logger.info(rtnrecfmt, srchstring, len(found_wines))


    # watch to see if the popup came in after we are done
    time.sleep(2)
    napacab_over21( napacab_driver )
    napacab_email_signup( napacab_driver )

    # check if we have records
    if not found_wines:
        return  returnNoWineFound( winestore )

    # return the wines we found
    return found_wines

# function to create a selenium driver for napacab and get past popup
def create_napacab_selenium_driver(defaultzip):
    global verbose

    # Using Chrome to access web
    driver=create_webdriver_from_global_var('napacab_driver')

    # debugging
    if pmsg: print('napacab_driver:Go to https://www.napacabs.com/ web page')
    logger.info('Go to https://www.napacabs.com/ web page')
    
    
    # Open the website
    driver.get('https://www.napacabs.com/')

    # try to get the search box
    results = find_elements_looped( driver, '//*[@id="search_query"]', 'by_xpath', 'napacab_driver', 'waiting on search box:')
    if not results:
        if pmsg: print('napacab_driver:ERROR:did not find search box - removing this store for this run:', srchstring)
        logger.warning('did not find search box - removing this store for this run:%s', srchstring)
        driver=None
    else:
        # check to see if there is an over21 display and button
        napacab_over21( driver )

    
    # debugging
    if pmsg: print('napacab_driver:complete:---------------------------------------------------')
    logger.info('complete:---------------------------------------------------')
    

    # return the driver
    return driver


# -----------------------------------------------------------------------

#### RALPHS ####


# function used to extract the data from the DOM that was returned
def ralphs_extract_wine_from_DOM(winestore,index,titlelist,pricelist,sizelist):
    global verbose

    
    # extract the values
    winename = titlelist[index].text
    wineprice = pricelist[index].text

    # add the size to the name
    if sizelist:
        winename += ' ' + sizelist[index].text
    
    # regex the price field to match our expections
    match = re.search('\$(.*)<',wineprice)
    if match:
        wineprice = match.group(1)
    
    # now clean up $ and ,
    wineprice = wineprice.replace('$','').replace(',','')

    # return the dictionary
    return { 'wine_store' : winestore, 'wine_name' : winename, 'wine_price' : wineprice, 'wine_year' : '', 'label' : winestore }


# Search for the wine
def ralphs_search( srchstring, ralphs_driver ):
    global verbose

    winestore = 'Ralphs'

    ken = '''
    # try to get the search box
    results = find_elements_looped(ralphs_driver, 'SearchButton', 'by_class_name', 'ralphs_search', 'find search box')
    if not results:
        if pmsg: print('ralphs_search:ERROR:did not find search box')
        return []

    if pmsg: print('ralphs_search:search box count:', len(results))

    # set the variable
    search_box = results[0]

    if pmsg: print('ralphs_search:search box is_dislayed:', search_box.is_displayed())
    input()
    

    # debugging
    if pmsg: print('ralphs_search:search for:', srchstring)

    # send in the string to this box and press RETURN
    search_box.clear()
    search_box.send_keys(srchstring)
    search_box.send_keys(Keys.RETURN)
'''

    # debugging
    if pmsg: print('ralphs_search:search for:', srchstring)
    logger.info('search for:%s', srchstring)

    # create the search URL and then search
    url = 'https://www.ralphs.com/search?query={}%20wine&searchType=natural&fulfillment=all'.format(srchstring)
    ralphs_driver.get(url)

    # create the array that we will add to
    found_wines = []

    # get back the results
    results = find_elements_looped(ralphs_driver, 'ContainerGrid-header-title', 'by_class_name', 'ralphs_search', 'search results')
    if not results:
        if pmsg: print('ralphs_search:ERROR:never got a result from the search:', srchstring)
        logger.warning('never got a result from the search:%s', srchstring)
        # put in saveBrowser here
        return []

    loopcnt=4
    while results[0].text.startswith('Search') and loopcnt:
        if pmsg: print('ralphs_search:result count not populated yet - wait')
        logger.info('result count not populated yet - wait:%d', loopcnt)
        time.sleep(2)
        loopcnt -= 1

    # message
    if pmsg: print('ralphs_search:len result:', len(results))
    if pmsg: print('ralphs_search:results[0].text:', results[0].text)
    logger.info('len result:%d', len(results))
    logger.info('results[0].text:%s', results[0].text)

    # check to see if we got any results
    resultcnt = int(results[0].text.split()[0])
    if not resultcnt:
        if pmsg: print('ralphs_search:no results for:',srchstring)
        logger.info('no results for:%s',srchstring)
        return returnNoWineFound( winestore )
    
    # messaging
    if pmsg: print('ralphs_search:result count:', resultcnt)
    logger.info('result count:%d', resultcnt)

    
    # get the count from wine list
    loopcnt = 4
    winelist = ralphs_driver.find_elements_by_class_name('ProductCard')
    while loopcnt and (not winelist or len(winelist) < resultcnt):
        if pmsg: print('ralphs_search:len(winelist)<resultcnt:wait:', loopcnt)
        logger.info('len(winelist)<resultcnt:wait:%d', loopcnt)
        time.sleep(2)
        loopcnt -= 1
        winelist = ralphs_driver.find_elements_by_class_name('ProductCard')


    # messaging
    if pmsg: print('ralphs_search:winelist count:', len(winelist))
    logger.info('winelist count:%d', len(winelist))

    # debugging opportunity
    if len(winelist) != resultcnt:
        if pmsg: print('ralphs_search:DEBUGGING:resultcnt does not match winelist')
        logger.info('DEBUGGING:resultcnt does not match winelist')
        #saveBrowserContent( ralphs_driver, 'ralphs', 'ralphs_search:winelist-not-match-resultcnt')
    
    # step through the winelist
    index=0
    for item in winelist:
        
        # get results back and look for the thing we are looking for - the list of things we are going to process
        titlelist = item.find_elements_by_class_name('kds-Text--m')
        pricecontainerlist  = item.find_elements_by_class_name('kds-Price')
        priceoriglist = item.find_elements_by_class_name('kds-Price-original')
        pricepromolist = item.find_elements_by_class_name('kds-Price-promotional')
        availlist = item.find_elements_by_class_name('AvailableModalities-line1')
        sizelist = item.find_elements_by_class_name('ProductCard-sellBy-unit')

        # debugging
        # if pmsg: print('ralphs_search:lengths:index:{},title:{},pricepromo:{},pricecontainer:{},priceorig:{}'.format(index,len(titlelist),len(pricepromolist),len(pricecontainerlist),len(priceoriglist)))

        # extract out the wine and price
        try:
            if pricepromolist:
                found_wines.append( ralphs_extract_wine_from_DOM(winestore,0,titlelist,pricepromolist,sizelist) )
            else:
                found_wines.append( ralphs_extract_wine_from_DOM(winestore,0,titlelist,pricecontainerlist,sizelist) )
        except Exception as e:
            # failed - so message nad return what we found
            if pmsg: print('ralphs_extract_wine_DOM:index:', index)
            logger.info('index:%d', index)
            exceptionPrint( e, 'ralphs_extract_wine_from_DOM', 'ERROR:page is stale:'+srchstring, True, ralphs_driver, 'ralphs', 'ralphs_search')
            return found_wines


        # debugging - look at the availlist
        try:
            # debugging for now
            if availlist:
                if availlist[0].text != 'Pickup & Delivery Available':
                    if pmsg: print('ralphs_search:debugging:', titlelist[0].text, ':', availlist[0].text)
                    logger.info('debugging:%s:%s', titlelist[0].text, availlist[0].text)
        except Exception as e:
            if pmsg: print('ralphs_availlist_print:', index)
            logger.info('index:%d', index)
            exceptionPrint( e, 'ralphs_availlist_print', 'availlist-print:'+srchstring, True, ralphs_driver, 'ralphs', 'ralphs_search')

        # increment counter
        index += 1

    # debugging
    if pmsg: print('ralphs_search:', srchstring, ':returned records:', len(found_wines))
    logger.info(rtnrecfmt, srchstring, len(found_wines))

    if not found_wines:
        return returnNoWineFound( winestore )

    # return the wines we found
    return found_wines


# set the store from the dialogue
def ralphs_set_store( driver, defaultzip, storename, dataTestID ):
    # find the zip code box
    zip = driver.find_elements_by_class_name('kds-Input--compact')
    if zip:
        if pmsg: print('ralphs_set_store:found zip box - populating with:', defaultzip)
        logger.info('found zip box - populating with:%s', defaultzip)
        zip[0].clear()
        zip[0].send_keys(defaultzip)
        zip[0].send_keys(Keys.RETURN)

    # now wait a second to allow screen to update
    if pmsg: print('ralphs_set_store:wait 2 seconds')
    logger.info('wait 2 seconds')
    time.sleep(2)

    # get the list of buttons and search for the one that we want
    selectbtns = driver.find_elements_by_class_name('AvailableModality--Button')
    for btn in selectbtns:
        if btn.get_attribute('aria-label') == 'In-Store [object Object]   Select Store':
            if pmsg: print('ralphs_set_store:found the instore select button - click it')
            logger.info('found the instore select button - click it')
            btn.click()
            break

    # now find the button tied to the store we want to select
    storebtns = driver.find_elements_by_class_name('kds-Button')
    for store in storebtns:
        # debugging
        if pmsg: print('ralphs_set_store:checking button:', store.get_attribute('data-testid'))
        logger.info('checking button:%s', store.get_attribute('data-testid'))
        if store.get_attribute('data-testid') == dataTestID:
            if pmsg: print('ralphs_set_store:found store of interest:', dataTestID)
            if pmsg: print('ralphs_set_store:storename:', store.get_attribute('aria-label'))
            if pmsg: print('ralphs_set_store:click this button:', store.text)
            logger.info('found store of interest:%s', dataTestID)
            logger.info('storename:%s', store.get_attribute('aria-label'))
            logger.info('click this button:%s', store.text)
            store.click()
            if pmsg: print('ralphs_set_store:returning')
            logger.info('returning')
            return
        
    if pmsg: print('ralphs_set_store:NEVER found store of interest:', dataTestID)
    logger.info('NEVER found store of interest:%s', dataTestID)

        
# select the store
def ralphs_select_store( driver, defaultzip, storename, dataTestID ):
    # find the current store selected
    results = find_elements_looped(driver, 'CurrentModality-vanityName', 'by_class_name', 'ralphs_select_store', 'find current selected store')

    # did not find a selected store
    if not results:
        if pmsg: print('ralphs_select_store:ERROR:did not find current setting')
        logger.warning('did not find current setting')
        saveBrowserContent( driver, 'ralphs', 'ralphs_select_store:find current selected store' )

    # found the store compare it
    if results[0].text == storename:
        if pmsg: print('ralphs_select_store:store selected is correct:', storename)
        logger.info('store selected is correct:%s', storename)
        return

    # message
    if pmsg: print('ralphs_select_store:store not the one we want:', results[0].text)
    if pmsg: print('ralphs_select_store:check for zip code entry box')
    logger.info('store not the one we want:%s', results[0].text)
    logger.info('check for zip code entry box')
    
    # not the store we want - so lets see if
    zip = driver.find_elements_by_class_name('kds-Input--compact')
    if not zip:
        if pmsg: print('ralphs_select_store:change store dialogue not visible')
        logger.info('change store dialogue not visible')
        openDialoge = driver.find_elements_by_class_name('CurrentModality-rightArrow')
        if openDialoge:
            if pmsg: print('ralphs_select_store:found arrow to open dialogue - click it')
            logger.info('found arrow to open dialogue - click it:%d', len(openDialoge))
            openDialoge[0].click()
            # now check that we got what we were looking for
            
    # now set the store
    ralphs_set_store( driver, defaultzip, storename, dataTestID )
    
def ralphs_select_store_start( driver, defaultzip, storename, dataTestID ):
    # look the current setting
    # try to get the search box
    results = find_elements_looped(driver, 'ReactModal__Content--after-open', 'by_class_name', 'ralphs_select_store_start', 'find current selected store')

    # check to see if dialogue showed up and if not move on
    if not results:
        if pmsg: print('ralphs_select_store_start:dialogue did not show - skipping')
        logger.info('dialogue did not show - skipping')
        return

    # found the store compare it
    storelist = results[0].find_elements_by_class_name('kds-Text--l')
    if storelist and storelist[1].text == storename:
        if pmsg: print('ralphs_select_store_start:desired store already selected:', storename)
        logger.info('desired store already selected:%s:%s', 'kds-Text--l', storename)
        return
    elif storelist:
        logger.info('no match on storelist:%s:%d', 'kds-Text--l', len(storelist))
        if pmsg: print(storelist[1].text)
        for store in storelist:
            if pmsg: print(store.text)
            logger.info('store.text:%s', store.text)
            
    storelist = results[0].find_elements_by_class_name('CurrentModality-modalityType')
    if storelist and storelist[1].text == storename:
        if pmsg: print('ralphs_select_store_start:desired store already selected:', storename)
        logger.info('desired store already selected:%s:%s', 'CurrentModality-modalityType', storename)
        return
    elif storelist:
        logger.info('no match on storelist:%s:%d', 'CurrentModality-modalityType', len(storelist))

    # not the store we want - click the change button
    changebtns = results[0].find_elements_by_class_name('DynamicTooltip--Button--Change')
    if changebtns:
        if pmsg: print('ralphs_select_store_start:change button text:', changebtns[0].text)
        if pmsg: print('ralphs_select_store_start:change button is_displayed:', changebtns[0].is_displayed())
        if pmsg: print('ralphs_select_store_start:change button clicked')
        logger.info('change button text:%s', changebtns[0].text)
        logger.info('change button is_displayed:%s', changebtns[0].is_displayed())
        logger.info('change button clicked')
        changebtns[0].click()

    # this causes the set store dialogue to show up - call that script
    ralphs_set_store( driver, defaultzip, storename, dataTestID )

# function to create a selenium driver for ralphs and get past popup
def create_ralphs_selenium_driver(defaultzip, storename, dataTestID):
    global verbose

    # Using Chrome to access web
    driver=create_webdriver_from_global_var('ralphs_driver')

    # Open the website
    driver.get('https://www.ralphs.com/')

    # try to get the search box
    results = find_elements_looped(driver, 'searchInputWrapper', 'by_class_name', 'ralphs_driver', 'find search box')

    # check to see if we found the search box and if not set to none
    if not results:
        if pmsg: print('create_ralphs_selenium_driver:ERROR:did not find search string - setting driver to none')
        logger.warning('did not find search string - setting driver to none')
        saveBrowserContent( driver, 'ralphs', 'create_ralphs_selenium_driver' )
        driver=None

    # check to see if we have the prompting dialogue
    ralphs_select_store_start( driver, defaultzip, storename, dataTestID )

    # validate we have the store we wanted
    ralphs_select_store( driver, defaultzip, storename, dataTestID )

    # debugging
    if pmsg: print('ralphs_driver:complete:---------------------------------------------------')
    logger.info('complete:---------------------------------------------------')
    

    # return the driver
    return driver


# --------------------------------------------------------------------------



# routine use by email parser to grab the results for one wine
def get_wines_from_stores( srchstring_list, storelist, optiondict={}, debug=False ):
    global verbose


    # create the bevmo selenium driver
    if 'bevmo' in storelist:
        bevmo_driver = create_bevmo_selenium_driver('Ladera Ranch', '2962', retrycount=3)
        # if we did not get a valid driver - then we are not using this store.
        if bevmo_driver == None:  storelist.remove('bevmo')
    if 'pavillions' in storelist:
        pavillions_driver = create_pavillions_selenium_driver('92688')
    if 'wineclub' in storelist:
        wineclub_driver = create_wineclub_selenium_driver('92688')
        if wineclub_driver == None:  storelist.remove('wineclub')
    if 'hitime' in storelist:
        hitime_driver = create_hitime_selenium_driver('92688')
    if 'totalwine' in storelist:
        totalwine_driver = create_totalwine_selenium_driver('Laguna Hills', optiondict)
        # if we did not get a valid driver - then we are not using this store.
        if totalwine_driver == None:  storelist.remove('totalwine')
    if 'wally' in storelist:
        wally_driver = create_wally_selenium_driver('')
        if wally_driver == None:  storelist.remove('wally')
    if 'winex' in storelist:
        winex_driver = create_winex_selenium_driver('')
        if winex_driver == None:  storelist.remove('winex')
    if 'napacab' in storelist:
        napacab_driver = create_napacab_selenium_driver('92688')
               
    # create the list of records for each search string
    found_wines = []

    # step through the list
    for srchstring in srchstring_list:
        # find the wines for this search string
        if 'bevmo' in storelist:
            found_wines.extend( bevmo_search( srchstring, bevmo_driver ) )
            # debugging
            if verbose > 5: print('wineselenium.py:', srchstring, ' count of wines found:', len(found_wines))
        if 'pavillions' in storelist:
            found_wines.extend( pavillions_search( srchstring, pavillions_driver ) )
            # debugging
            if verbose > 5: print('wineselenium.py:', srchstring, ' count of wines found:', len(found_wines))
        if 'wineclub' in storelist:
            found_wines.extend( wineclub_search( srchstring, wineclub_driver ) )
            # debugging
            if verbose > 5: print('wineselenium.py:', srchstring, ' count of wines found:', len(found_wines))
        if 'totalwine' in storelist:
            found_wines.extend( totalwine_search( srchstring, totalwine_driver, optiondict ) )
            # debugging
            if verbose > 5: print('wineselenium.py:', srchstring, ' count of wines found:', len(found_wines))
        if 'hitime' in storelist:
            found_wines.extend( hitime_search( srchstring, hitime_driver ) )
            # debugging
            if verbose > 5: print('wineselenium.py:', srchstring, ' count of wines found:', len(found_wines))
        if 'wally' in storelist:
            found_wines.extend( wally_search( srchstring, wally_driver ) )
            # debugging
            if verbose > 5: print('wineselenium.py:', srchstring, ' count of wines found:', len(found_wines))
        if 'winex' in storelist:
            found_wines.extend( winex_search( srchstring, winex_driver ) )
            # debugging
            if verbose > 5: print('wineselenium.py:', srchstring, ' count of wines found:', len(found_wines))
        if 'napacab' in storelist:
            found_wines.extend( napacab_search( srchstring, napacab_driver ) )
            # debugging
            if verbose > 5: print('wineselenium.py:', srchstring, ' count of wines found:', len(found_wines))

        # debugging
        if verbose > 5: print('wineselenium.py:', srchstring, ' count of wines found:', len(found_wines))



    # close the browser we open when we are all done.
    if 'bevmo' in storelist:
        bevmo_driver.quit()
    if 'pavillions' in storelist:
        pavillions_driver.quit()
    if 'wineclub' in storelist:
        wineclub_driver.quit()
    if 'hitime' in storelist:
        hitime_driver.quit()
    if 'totalwine' in storelist:
        totalwine_driver.quit()
    if 'wally' in storelist:
        wally_driver.quit()
    if 'winex' in storelist:
        winex_driver.quit()
    if 'napacab' in storelist:
        napacab_driver.quit()

    # return the results you pulled
    return found_wines
    

# ---------------------------------------------------------------------------
if __name__ == '__main__':

    # capture the command line
    optiondict = kvutil.kv_parse_command_line( optiondictconfig, debug=False )

    # extract the values and put into variables
    test    = optiondict['test']
    verbose = optiondict['verbose']
    AppVersion = optiondict['AppVersion']

    # check if the browser is set
    if optiondict['browser'] in ('ff', 'firefox'):
        browser = 'firefox'

    # from the command line
    wineoutfile = optiondict['wineoutfile']
    winexlatfile = optiondict['winexlatfile']
    
    # dump out what we have done here
    if test:
        if pmsg: print('---------------TEST FLAG ENABLED---------------------------')
        if pmsg: print('test:browser:', browser)
        logger.info('----TEST FLAG ENABLED---------------------------')
        logger.info('test:browser:%s', browser)

        
    # check to see if we passed in srchlist instead of srchstring
    if optiondict['srchlist'] and not optiondict['srchstring']:
        if pmsg: print('srchlist was passed in INSTEAD of srchstring - substituting')
        logger.info('srchlist was passed in INSTEAD of srchstring - substituting')
        optiondict['srchstring'] = optiondict['srchlist']
    

    # debugging
    if verbose > 0:
        if pmsg: print('---------------STARTUP(v', optiondictconfig['AppVersion']['value'], ')-(', datetime.datetime.now().strftime('%Y%m%d:%T'), ')---------------------------')
    logger.info('STARTUP(v%s)%s', optiondictconfig['AppVersion']['value'], '-'*40)

    # define the store list - all the stores we COULD process
    storelist = [
        'bevmo',
        'hitime',
        'pavillions',
#        'totalwine',  #commented out because we call this all by itself
        'wineclub',
        'wally',
        'winex',
#        'napacab',  #  moved this back to winerequest to get the performance back
        'ralphs',
    ]

    ##### STORELIST ######

    # check to see if we got a command line store list
    if optiondict['storelist']:
        storelist = [ optiondict['storelist'] ]
    elif optiondict['store_list']:
        if pmsg: print('store_list was passed INSTEAD of storelist - substituting')
        logger.info('store_list was passed INSTEAD of storelist - substituting')
        storelist = [ optiondict['store_list'] ]


    # uncomment this line if you want to limit the number of stores you are working
    #storelist = ['wally']
    #storelist = ['hitime']
    #storelist = ['wineclub']
    #storelist = ['pavillions']
    if test:
        # storelist = ['totalwine']
        if optiondict['storelist']:
            storelist = [ optiondict['storelist'] ]
        # display what it is we are going after
        if pmsg: print('test:storelist:', storelist)
        logger.info('test:storelist:%s', storelist)

    #### TOTAL WINE - Gmail Password Test ######

    # test to see the password was passed in
    if 'totalwine' in storelist and not optiondict['EmailFromPassword']:
        if pmsg: print('wineselenium.py:you must set the EmailFromPassword for account:', optiondict['EmailFromAddr'])
        if pmsg: print('TERMINATING')
        logger.error('you must set the EmailFromPassword for account:%s', optiondict['EmailFromAddr'])
        logger.error('TERMINATING')
        sys.exit(1)

    # debugging
    logger.info('storelist:%s', storelist)


    ### SEARCH LIST ####

    # srchstring - set at None - then we will look up the information from the file
    srchstring_list = None

    # uncommnet a line below if you want define the wines you are checking for
    #srchstring_list = ['attune','groth','beringer','hewitt','crawford','foley']
    if test:
        #srchstring_list = ['groth']
        srchstring_list = ['groth','cakebread','foley']
        #srchstring_list = ['foley']
        #srchstring_list = ['macallan']
        #srchstring_list = ['hewitt']
        #srchstring_list = ['silver oak']
        #srchstring_list = ['macallan']
        #srchstring_list = ['attune']
        #srchstring_list = ['richard']
        #srchstring_list = ['arista','richard','richard cognac']
        #srchstring_list = ['kosta']
        #srchstring_list = ['cakebread']
        #srchstring_list = ['hope']
        # determine if the person assed in the wine to search for
        if optiondict['srchstring']:
            if optiondict['srchstring'] == 'None':
                srchstring_list = None
            else:
                srchstring_list = [ optiondict['srchstring'] ]
        if optiondict['srchstring_list']:
            srchstring_list = optiondict['srchstring_list']
            
        if pmsg: print('test:srchstring_list:', srchstring_list)
        logger.info('test:srchstring_list:%s', srchstring_list)

    # if not user defined - generate the list if we don't have one predefined
    if srchstring_list == None:
        srchstring_list = get_winelist_from_file( wineinputfile )
        remove_already_processed_wines( wineoutfile, srchstring_list )
        if not srchstring_list:
            if pmsg: print('main:no wines to search for - ending program')
            logger.info('no wines to search for - ending program')
            sys.exit()


    ### WINE_XLAT ####

    # load in xlat file in to a module level variable
    read_wine_xlat_file( winexlatfile, debug=verbose )

    # create each of the store drivers we need to use
    if 'totalwine' in storelist:
        totalwine_driver = create_totalwine_selenium_driver('Laguna Hills', optiondict)
        # if we did not get a valid driver - then we are not using this store.
        if totalwine_driver == None:  
            storelist.remove('totalwine')
            logger.warning('removing store from this run:totalwine')
            if pmsg: print('main:FAILED:removed store from search:totalwine')
    if 'bevmo' in storelist:
        bevmo_driver = create_bevmo_selenium_driver('Ladera Ranch', '2962', retrycount=3)
        # if we did not get a valid driver - then we are not using this store.
        if bevmo_driver == None:  
            storelist.remove('bevmo')
            logger.warning('removing store from this run:bevmo')
            if pmsg: print('main:FAILED:removed store from search:bevmo')
    if 'pavillions' in storelist:
        pavillions_driver = create_pavillions_selenium_driver('92692')
    if 'wineclub' in storelist:
        wineclub_driver = create_wineclub_selenium_driver('92688')
        # if we did not get a valid driver - then we are not using this store.
        if wineclub_driver == None:  
            storelist.remove('wineclub')
            logger.warning('removing store from this run:wineclub')
            if pmsg: print('main:FAILED:removed store from search:wineclub')
    if 'hitime' in storelist:
        hitime_driver = create_hitime_selenium_driver('92688')
    if 'wally' in storelist:
        wally_driver = create_wally_selenium_driver('')
        if wally_driver == None:
            storelist.remove('wally')
            logger.warning('removing store from this run:wally')
            if pmsg: print('main:FAILED:removed store from search:wally')
    if 'winex' in storelist:
        winex_driver = create_winex_selenium_driver('')
        if winex_driver == None:  storelist.remove('winex')
    if 'napacab' in storelist:
        napacab_driver = create_napacab_selenium_driver('92688')
    if 'ralphs' in storelist:
        ralphs_driver = create_ralphs_selenium_driver('92677', 'La Paz & Marguerite S/C', "SelectStore-70300076")
        # if we did not get a valid driver - then we are not using this store.
        if ralphs_driver == None:  
            storelist.remove('ralphs')
            logger.warning('removing store from this run:ralphs')
            if pmsg: print('main:FAILED:removed store from search:ralphs')
        
               
               
    # dump out what we have done here
    if verbose > 0:
        if pmsg: print('------------------------------------------')
        if pmsg: print('wineselenium.py:version:',AppVersion)
        if pmsg: print('wineselenium.py:storelist:', storelist)
        if pmsg: print('wineselenium.py:wineoutfile:', wineoutfile)
        if pmsg: print('wineselenium.py:srchstring_list:', srchstring_list)
        if pmsg: print('------------------------------------------')

        logger.info('version:%s',AppVersion)
        logger.info('storelist:%s', storelist)
        logger.info('wineoutfile:%s', wineoutfile)
        logger.info('srchstring_list:%s', srchstring_list)
        logger.info('%s', '-'*40)
        
    # step through the list
    for srchstring in srchstring_list:
        # create the list of records for each search string
        found_wines = []
        # find the wines for this search string
        # find the wines for this search string
        if 'bevmo' in storelist:
            found_wines.extend( bevmo_search( srchstring, bevmo_driver ) )
            # debugging
            if verbose > 5: print('wineselenium.py:', srchstring, ' count of wines found:', len(found_wines))
        if 'pavillions' in storelist:
            found_wines.extend( pavillions_search( srchstring, pavillions_driver ) )
            # debugging
            if verbose > 5: print('wineselenium.py:', srchstring, ' count of wines found:', len(found_wines))
        if 'wineclub' in storelist:
            found_wines.extend( wineclub_search( srchstring, wineclub_driver ) )
            # debugging
            if verbose > 5: print('wineselenium.py:', srchstring, ' count of wines found:', len(found_wines))
        if 'totalwine' in storelist:
            found_wines.extend( totalwine_search( srchstring, totalwine_driver, optiondict ) )
            # debugging
            if verbose > 5: print('wineselenium.py:', srchstring, ' count of wines found:', len(found_wines))
        if 'hitime' in storelist:
            found_wines.extend( hitime_search( srchstring, hitime_driver ) )
            # debugging
            if verbose > 5: print('wineselenium.py:', srchstring, ' count of wines found:', len(found_wines))
        if 'wally' in storelist:
            found_wines.extend( wally_search( srchstring, wally_driver ) )
            # debugging
            if verbose > 5: print('wineselenium.py:', srchstring, ' count of wines found:', len(found_wines))
        if 'winex' in storelist:
            found_wines.extend( winex_search( srchstring, winex_driver ) )
            # debugging
            if verbose > 5: print('wineselenium.py:', srchstring, ' count of wines found:', len(found_wines))
        if 'napacab' in storelist:
            found_wines.extend( napacab_search( srchstring, napacab_driver ) )
            # debugging
            if verbose > 5: print('wineselenium.py:', srchstring, ' count of wines found:', len(found_wines))
        # find the wines for this search string
        if 'ralphs' in storelist:
            found_wines.extend( ralphs_search( srchstring, ralphs_driver ) )
            # debugging
            if verbose > 5: print('wineselenium.py:', srchstring, ' count of wines found:', len(found_wines))

        # debugging
        if pmsg: print('wineselenium.py:', srchstring, ' count of wines found:', len(found_wines))
        logger.info( '%s:count of wines found:%d', srchstring, len(found_wines) )

        # call the print routine
        save_wines_to_file(wineoutfile, srchstring, found_wines)


    # close the browser we open when we are all done.
    if 'bevmo' in storelist:
        bevmo_driver.quit()
    if 'pavillions' in storelist:
        pavillions_driver.quit()
    if 'wineclub' in storelist:
        wineclub_driver.quit()
    if 'hitime' in storelist:
        hitime_driver.quit()
    if 'totalwine' in storelist:
        totalwine_driver.quit()
    if 'wally' in storelist:
        wally_driver.quit()
    if 'winex' in storelist:
        winex_driver.quit()
    if 'napacab' in storelist:
        napacab_driver.quit()
    if 'ralphs' in storelist:
        ralphs_driver.quit()

# eof
