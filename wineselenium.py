'''
@author:   Ken Venner
@contact:  ken@venerllc.com
@version:  1.105

Using Selenium and Chrome - screen scrape wine websites to draw
down wine pricing and availiability information

'''

from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException

import requests

import kvutil

import time
import re
import datetime
import sys


# application variables
optiondictconfig = {
    'AppVersion' : {
        'value' : '1.105',
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
    'srchstring' : {
        'value' : None,
        'description' : 'defines the name of the wine to search for when in test mode',
    },
    'srchlist' : {
        'value' : None,
        'description' : 'mistaken command line for srchstring',
    },
    'storelist' : {
        'value' : None,
        'description' : 'defines the name of the store we are querying - only when testing',
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
    'waitonerror' : {
        'value' : False,
        'type'  : 'bool',
        'description' : 'defines if we wait on error vs exit',
    },

    'bevmoretrycount' : {
        'value' : 3,
        'type'  : 'int',
        'description' : 'defines number of times we attempt to create the bevmo driver',
    },

}

# define if we are running in test mode
test=False

# global variable - rundate set at strat
datefmt = '%m/%d/%Y'
rundate = datetime.datetime.now().strftime(datefmt)
store_wine_lookup = {}
AppVersion    = 'NotSet'
wineoutfile   = 'wineselenium.csv'
wineinputfile = 'getwines.bat'  #overwritten later
winexlatfile  = 'wine_xlat.csv' #overwritten later
verbose=1

# global variable as we need to figure out at run time which to use
pavillions_search_xpath = ''

# --- FILE ROUTINES --------------------

# -- read in the list of wines
def get_winelist_from_file( getwines_file ):
    # get the results
    searchlist = []

    # open file and process
    with open(getwines_file, 'r') as fp:
        # for each line in the file see if it matches a regex of interest
        for line in fp:
            # regex #1 match
            m=re.match('perl\s+findwine.pl\s+search="([^"]*)"\s', line)
            # if that did not match - try regex #2 match
            if not m:
                m=re.match('perl\s+findwine.pl\s+search=([^\s]*)\s', line)
               
            # test to see if we got a match on any regext
            if m:
                # extract out the match which is the wine
                searchlist.append(m.group(1))

    # return the list we found
    return searchlist

# take from the list of wines we need to process - remove those already processed
def remove_already_processed_wines( winefile, searchlist):
    global verbose

    # create the hash that captures what we have seen and not seen already
    seen_wines = []

    # put try loop in to deal with case when file does not exist
    try:
        # give  some information here
        print('remove_already_processed_wines:winefile:', winefile)
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
            print('remove_already_processed_wines:', winefile, ':does not exist-no wines removed from processing list')

    # log informaton
    print('remove_already_processed_wines:seen_wines:', seen_wines)

    # return the pruned list
    return searchlist

# read in the translation file from store/wine to store/wine with vintage
def read_wine_xlat_file( getwines_file, debug=False ):
    # blank dictionary to start
    store_wine_lookup = {}
    
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
                        print('read_wine_xlat_file:',elem[0],':',elem[1],' mapping changed from (', store_wine_lookup[elem[0]][elem[1]], ') to (', elem[2], ')')
                # set the value no matter what
                store_wine_lookup[elem[0]][elem[1]] = elem[2]
            
    # return
    return store_wine_lookup


# now convert a wine name to appropriate translatoin
def xlat_wine_name( store_wine_lookup, store, wine ):
    global verbose
    
    if store in store_wine_lookup.keys():
        # debugging
        if verbose > 5:
            print('xlat_wine_name:store matched:', store)
            print('xlat_wine_name:store list of wines:', store_wine_lookup[store])
        if wine in store_wine_lookup[store].keys():
            # debugging
            if verbose > 5:
                print('xlat_wine_name:wine matched:', wine)
            return store_wine_lookup[store][wine]

    # using the name provided - regex the name field to remove any commas
    if re.search(',', wine):
        # debugging
        if verbose > 1:
            print ('xlat_wine_name:comma in wine:',wine)
        wine = re.sub(',',' ',wine)
        # debugging
        if verbose > 2:
            print ('xlat_wine:comma stripped from wine:',wine)
    
    # pass back the wine passed in (cleaned up)
    return wine



# -- output file
def save_wines_to_file(file, srchstring, winelist):
    global verbose

    # debugging
    if verbose > 5:
        print ('save_wines_to_file:started')

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
                    if verbose > 5:
                        print ('xlat_wine:comma in price:',rec['wine_price'])
                    # strip out the comma in price if it exists (might wnat to get rid of this)
                    rec['wine_price'] = re.sub(',','',rec['wine_price'])
                    # debugging
                    if verbose > 6:
                        print ('xlat_wine:comma stripped from price:',rec['wine_price'])
                
                # save - but also convert the wine name if there is a translation
                winecsv.write(','.join([rundate,srchstring,rec['wine_store'],xlat_wine_name(store_wine_lookup,rec['wine_store'],rec['wine_name']),rec['wine_price']])+"\n")
            else:
                # debugging
                if verbose > 0:
                    print ('save_wines_to_file:no wine price for:', rec['wine_store'], ':', rec['wine_name'])

    # debugging
    if verbose > 0:
        print ('save_wines_to_file:', srchstring, ':completed')
                
# routine that saves the current browser content to a file
def saveBrowserContent( driver, filenametemplate, function ):
    filename = kvutil.filename_unique( 'fail' + filenametemplate + '.html', {'uniqtype': 'datecnt', 'forceuniq' : True } )
    with open( filename, 'wb' ) as p:
        p.write( driver.page_source.encode('utf-8') )
    print(function + ':saved html page content to:', filename)

    filename = kvutil.filename_unique( 'fail' + filenametemplate + '.png', {'uniqtype': 'datecnt', 'forceuniq' : True } )
    driver.save_screenshot(filename)
    print(function + ':saved page screen shot to:', filename)

        
# ---------------------------------------------------------------------------

# dump out an HTML element additional data
def print_html_elem( msg, index, elem):
    print ('-----------------------------------------')
    print ('index:', index)
    print (msg, ' class:', elem.get_attribute('class'))
    print (msg, ' type:', elem.get_attribute('type'))
    print (msg, ' id:', elem.get_attribute('id'))
    print (msg, ' parentElement:', elem.get_attribute('parentElement'))
    print (msg, ' outerHTML:', elem.get_attribute('outerHTML'))
    print (msg, ' text:', elem.get_attribute('text'))
    print (msg, ' displayed:', elem.is_displayed())
    print (msg, ' location:', elem.location)
    print (msg, ' size:', elem.size)
    print ('-----------------------------------------')

# exit application with error code
def exitWithError( msg='' ):
    # display optional message
    if msg:
        print(msg)

    # display that we terminated and then terminate
    print('TERMINATE')
    sys.exit(1)

# -----------------------------------------------------------------------

# CHROME SPECIFIC FEATURES #

# created this because upgrade to ChromeDriver 75 broke this script
def create_chrome_webdriver_w3c_off():
    # turn off w3c - implemented 20190623;kv
    opt = webdriver.ChromeOptions()
    opt.add_experimental_option('w3c', False)
    driver = webdriver.Chrome(chrome_options=opt)
    return driver

# -----------------------------------------------------------------------

#### BEVMO ####

# function used to extract the data from the DOM that was returned
def bevmo_extract_wine_from_DOM(index,winelist):
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
                print(winename, ':5 cent sale')
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
                    print ('BevMo' , ":", winename, ":", pricetype, ":", wineprice)
                # stop looking
                break
    #
    # final extracted wine data
    return { 'wine_store' : 'BevMo', 'wine_name' : winename, 'wine_price' : wineprice, 'wine_year' : '', 'label' : '' }

def bevmo_search_box_find( bevmo_driver, waitonerror=False ):

    # define what we are looking for
    search_box=None
    page_refresh_count_down = 3 # wait times
    while not search_box and page_refresh_count_down:
        # debugging
        print('bevmo_search_box_find:get the main url for the website fresh counter:', page_refresh_count_down)

        # refresh page and find search box
        bevmo_driver.get('https://www.bevmo.com')

        # sret the inner loop coutner
        search_count_down = 4 # wait for times

        # loop while we have not found the search box and 
        while not search_box and search_count_down:
        
            # wait time for page to refres
            print('bevmo_search_box_find:pause 3 sec to allow page to refresh counter:', search_count_down)
            time.sleep(3)
            
            # Select the search box(es) and find if any are visbile - there can be more than one returned value
            # find the search box
            print('bevmo_search_box_find:find the search boxes count down:', search_count_down)
            search_boxes = bevmo_driver.find_elements_by_name('fp-input-search')
            
            # capture the count of boxes found
            search_box = len(search_boxes)
            print('bevmo_search_box_find:search boxes_found:', search_box)
            
            # decrement the count down
            search_count_down -= 1

        # out of this loop - decrement the outter loop counter
        page_refresh_count_down -= 1

        # and loop again if we don't have a search box

    # debugging
    if len(search_boxes) == 0:
        print('bevmo_search_box_find:number of search_boxes:', len(search_boxes))
        print('bevmo_search_box_find:exiting program due to error:no search boxes after many tries')
        # fail and leave the browser up so we can take a look at it
        saveBrowserContent( bevmo_driver, 'bevmo', 'bevmo_search_box_find' )
        if waitonerror:
            input()
        else:
            exitWithError()

    # debugging
    print('bevmo_search_box_find:locate the visible search box')

    # search the returned boxes to see if any are visible
    for index in range(len(search_boxes)):
        if waitonerror:
            print('bevmo_search_box_find:index:', index)
        search_box = search_boxes[index]
        # wrap this in a try/catch to capture errors
        try:
            # check to see if this check box is displayed
            if search_boxes[index].is_displayed():
                # visible - so we are done
                # debugging
                print ('bevmo_search_box_find:search box index:', index, ':is visible - search_box set to this value')
                return search_boxes[index]
        except:
            print('bevmo_search_box_find:search_boxes[index].is_displayed():errored out')

    # did not find a displayed search box - click the search button if visible and try again
    print('bevmo_search_box_find:no visible search boxes - click the search icon')
    #xpathstr = '//*[@id="header"]/div[3]/div[1]/div[2]/div[1]/a/span[1]'
    #searchbtn = bevmo_driver.find_element_by_xpath(xpathstr)
    classname = 'glyphicon-search'
    searchbtns = bevmo_driver.find_elements_by_class_name(classname)
    print('bevmo_search_box_find:find search button icon count:', len(searchbtns))
    if len(searchbtns):
        searchbtn = searchbtns[0]
        if searchbtn.is_displayed():
            print('bevmo_search_box_find:click search icon')
            searchbtn.click()
            # pause for a second
            time.sleep(1)
        else:
            print('bevmo_search_box_find:search button NOT visible - NOT pressed')
    else:
        print('bevmo_search_box_find:search button not found:', classname)

    # find the search box
    print('bevmo_search_box_find:find the search boxes:again')
    search_boxes = bevmo_driver.find_elements_by_name('fp-input-search')
    print('bevmo_search_box_find:boxes_found again:', len(search_boxes))

    # debugging
    print('bevmo_search_box_find:locate the visible search box:again')

    # search the returned boxes to see if any are visible
    for index in range(len(search_boxes)):
        if waitonerror:
            print('bevmo_search_box_find:again:index:', index)
        search_box = search_boxes[index]
        # check to see if this check box is displayed
        if search_boxes[index].is_displayed():
            # visible - so we are done
            # debugging
            print ('bevmo_search_box_find:search boxes:again:', index, 'is visible - search_box set to this value')
            return search_boxes[index]

    print('bevmo_search_box_find:no visible search boxes:again')
    print('is displayed:', search_box.is_displayed())
    print('pause')
    sys.exit()
    input()

    # find the search box
    print('bevmo_search_box_find:find the search boxes:again2')
    search_boxes = bevmo_driver.find_elements_by_name('fp-input-search')
    print('bevmo_search_box_find:boxes_found again2:', len(search_boxes))
    print('bevmo_search_box_find:first box is displayed?:', search_boxes[0].is_displayed())

    if search_boxes[0].is_displayed():
        return search_boxes[0]

    # return None we did not find one
    return None


# create a search on the web
def bevmo_search( srchstring, bevmo_driver, waitonerror=False ):
    global verbose

    # no wine found record
    noWineFound =  { 'wine_store' : 'BevMo', 'wine_name' : 'Sorry no matches were found', 'wine_price' : '1', 'wine_year' : '', 'label' : '' }

    # set the variable
    search_box = None

    # loop X times searching for the search box
    for i in range(4):
        # Open the website
        print('bevmo_search:call bevmo_search_box_find:', i)

        # get the search box we are working with
        search_box = bevmo_search_box_find( bevmo_driver, waitonerror )

        # test to see if we found the search_box
        if search_box:
            break

    # if no search box found - big problems
    if not search_box:
        print('bevmo_search:never found the displayed search box')

        # fail and leave the browser up so we can take a look at it
        saveBrowserContent( bevmo_driver, 'bevmo', 'bevmo_search-search_box' )
        if waitonerror:
            input()
        else:
            exitWithError()

    # debugging
    if verbose > 0:
        print ('bevmo_search:search for:', srchstring)

    # send in the string to this box and press RETURN
    try:
        search_box.clear()
        search_box.send_keys(srchstring)
        search_box.send_keys(Keys.RETURN)
    except  Exception as e:
        print ('bevmo_search:entering search string')
        print ('bevmo_search:type:', type(e))
        print ('bevmo_search:args:', e.args)
        print ('bevmo_search:exiting program due to error')
        saveBrowserContent( bevmo_driver, 'bevmo', 'bevmo_search')
        return []
    
    # create the array that we will add to
    found_wines = []

    # debugging
    pausetime = 5
    if verbose > 0:
        print ('bevmo_search:pause ', pausetime, ' sec to allow search results to return')
    # put a minor pause
    time.sleep(pausetime)

    # first test - see if we got no results found - if so return the empty array
    try:
        if bevmo_driver.find_element_by_class_name('fp-product-not-found'):
            if verbose > 0:
                print ('bevmo_search:', srchstring, ':no results returned - refresh the page we are looking at')
            # update the website we are pointing at
            bevmo_driver.get('https://www.bevmo.com')
            # debugging
            if verbose > 0:
                print ('bevmo_search:page refreshed to:www.bevmo.com')
                print ('bevmo_search:returned:',noWineFound)
            # return a record that says we could not find the record
            return [ noWineFound ]
        else:
            # debugging
            if verbose > 1:
                print('bevmo_search:did not error when searching for fp-product-not-found:' + srchstring)
    except NoSuchElementException:
        # debugging
        if verbose > 1:
            print ('bevmo_search:fp-product-not-found does not exist - there must be results')
    except NoSuchWindowException as e:
        print ('bevmo_search:window unexpectantly closed - error:', str(e))
        if waitonerror:
            input()
        else:
            exitWithError()
    except  Exception as e:
        print ('bevmo_search:fp-product-not-found - not found for (' + srchstring + ') - results were found (expected) - error:', str(e))
        print ('bevmo_search:type:', type(e))
        print ('bevmo_search:args:', e.args)
        print ('bevmo_search:exiting program due to error')
        saveBrowserContent( bevmo_driver, 'bevmo', 'bevmo_search')
        return []
        # exitWithError()

    # get results back and look for the thing we are looking for - the list of things we are going to process
    winelist = bevmo_driver.find_elements_by_class_name('fp-item-content')
    
    # debugging
    print('bevmo_search:', srchstring, ':returned records:',  len(winelist))

    # now loop through the wines we found
    for index in range(len(winelist)):
        # get the values of interest from this section of the page
        rec =  bevmo_extract_wine_from_DOM(index,winelist)
        # if we were not out of stock, save teh record
        if rec:
            found_wines.append( rec )
        # debugging
        if verbose > 1:
            print('rec:', rec)

    # debugging
    if verbose > 5:
        print ('bevmo_search:found_wines:',found_wines)

    # if we did not find any wines - send back that we did not find any wines
    if not found_wines:
        if verbose > 1:
            print ('bevmo_search:found not wines - fill found_wines with that value')
        # set the return value to found no wines
        found_wines.append( noWineFound )

    # update the website we are pointing at
    print ('bevmo_search:', srchstring, ':results found:refresh the page we are looking at')
    bevmo_driver.get('https://www.bevmo.com')

    # return the wines we found
    return found_wines

# if we don't get the age dialogue - get the select store dialogue
def set_bevmo_store_nopopup(driver, waitonerror=False):
    try:
        print('set_bevmo_store_nonpopup:no-21:click-select-store')
        selectStoreBtns = driver.find_elements_by_class_name('fp-store-label')
        for selectStoreBtn in selectStoreBtns:
            if selectStoreBtn.is_displayed():
                selectStoreBtn.click()
                return True
    except:
        print('set_bevmo_store_nopopup:did not find classname:fp-store-label')
        # did not find what we were looking for
        if waitonerror:
            input()
        else:
            exitWithError()
        return None

# function to create a selenium driver for bevmo and get past the store selector
def create_bevmo_selenium_driver(defaultstore, defaultstoreid, retrycount=0, waitonerror=False):
    loopcnt = retrycount + 1
    while(loopcnt):
        try:
            return create_bevmo_selenium_driver_worker(defaultstore, defaultstoreid, waitonerror=False)
        except  Exception as e:
            print('create_bevmo_selenium_driver:loopcnt:',loopcnt,':failed-try again')
            print('create_bevmo_selenium_driver:error:', str(e))
            print('create_bevmo_selenium_driver:type:', type(e))
            print('create_bevmo_selenium_driver:args:', e.args)
            loopcnt -= 1

    # all loops failed - give up on bevmo
    print('create_bevmo_selenium_driver:failed-all-attempts:skip-bevmo')
    return None
    
    
# function to create a selenium driver for bevmo and get past the store selector
def create_bevmo_selenium_driver_worker(defaultstore, defaultstoreid, waitonerror=False):
    global verbose

    # debugging
    if verbose > 0:
        print('bevmo_driver:start:---------------------------------------------------')
        print('bevmo_driver:Start up webdriver.Chrome')
    
    # Using Chrome to access web
    # driver = webdriver.Chrome()
    driver=create_chrome_webdriver_w3c_off()

    # debugging
    print ('bevmo_driver:Go to www.bevmo.com web page')
    
    # Open the website
    driver.get('https://www.bevmo.com')

    # loop waiting for the modal dialogue to appear
    modal_found = None
    modal_count_down = 4

    while not modal_found and modal_count_down:
        
        # 
        # ok - need to figure this out - but we must wait
        timewait = 4
        print ('bevmo_driver:sleep for ' + str(timewait) + ' seconds to allow the storeselect to pop up')
        time.sleep(timewait)

        # see if we can find this
        try:
            modal_found = driver.find_elements_by_class_name('fp-modal-content')
        except:
            print('bevmo_driver:did not find modal window yet:', modal_count_down)

        # decrement the modal count down
        modal_count_down -= 1
        

    # check for the checkbox
    try:
        # test for the form
        print('bevmo_driver:find i am 21 form')
        modalform = driver.find_element_by_class_name('modal-content')

        # i am 21 checkbox - find check box and fill it in
        print('bevmo_driver:find i am 21 check box and click')
        checkboxes = driver.find_elements_by_class_name('fp-checkbox')
        for checkbox in checkboxes:
            if checkbox.is_displayed():
                print('bevmo_driver:wait 2 seconds for screen to make box clickable')
                time.sleep(2)
                checkbox.click()
                break
        else:
            print('bevmo_driver:21 checkbox cnt:', len(checkboxes), ':none were displayed')
            return None

    except  Exception as e:
        print('bevmo_driver:failed i am 21 check')
        print ('bevmo_driver:error:', str(e))
        print ('bevmo_driver:type:', type(e))
        print ('bevmo_driver:args:', e.args)
        set_bevmo_store_nopopup(driver, waitonerror)

    # sleep for 1 second to allow page to respond
    time.sleep(1)

    # select the store we want to work with
    try:
        # pick up at the store
        print('bevmo_driver:find and click pickup at store')
        buttons=driver.find_elements_by_class_name('btn-primary')
        print ('bevmo_driver:number of buttons:', len(buttons))
        for button in buttons:
            if button.get_attribute('data-action') == 'change-pickup':
                print('bevmo_driver:clicking button with text:', button.text)
                print('bevmo_driver:is button displayed:', button.is_displayed())
                print('bevmo_driver:before-clicking-button:saving-browser-for-debugging')
                saveBrowserContent( driver, 'bevmo', 'bevmo_driver-click-button' )
                time.sleep(1)
                button.click()
                print('bevmo_driver:button successfully clicked')
        
    except  Exception as e:
        # we expect this to fail here so lets just deal with it
        print('bevmo_driver:failed and expected - sleep 20 seconds')
        time.sleep(20)
        saveBrowserContent( driver, 'bevmo', 'bevmo_search-btn-primary' )

    print('bevmo_driver:now looking to select our preferred store')
    try:
        # loop enough times to allow for the page to refresh
        loopcnt=4
        while(loopcnt):
            # wait 
            print('bevmo_driver:wait 5 secs for stores to display')
            time.sleep(5)

            # see if the critical field is there and displayed
            searchbtns = driver.find_elements_by_class_name('fp-btn-search')

            # no buttons found - just loop
            if not searchbtns:
                print('bevmo_driver:search button does not exist yet:loop again:', loopcnt)
                loopcnt -= 1
                continue

            # assume we are going to loop decrement the loopcnt
            loopcnt -= 1

            # now see if we are just done
            print('bevmo_driver:number of searchbtns:', len(searchbtns))
            for searchbtn in searchbtns:
                # print('bevmo_driver:searchbtn-text:', searchbtn.text)
                if searchbtn.is_displayed():
                    print('bevmo_driver:search button found - continue processing')
                    loopcnt = 0
                    break

            # we did not find the button - communicate this
            if loopcnt:
                print('bevmo_driver:search button not visible:loop again:', loopcnt)
                

        # loop enough times to allow for the page to refresh
        loopcnt=4
        while(loopcnt):
            # find the object to put the default store into
            print('bevmo_driver:find field to enter store info:fp-input-q')
            zipboxes = driver.find_elements_by_name('fp-input-q')
            print('bevmo_driver:count of zipboxes:', len(zipboxes))
            if not zipboxes:
                print('bevmo_driver:saving-browser-for-debugging:no ziboxes were found:loopcnt:', loopcnt)
                saveBrowserContent( driver, 'bevmo', 'bevmo_search_fp-btn-mystore' )
                loopcnt -= 1
                # wait 
                print('bevmo_driver:wait 5 secs for stores to display')
                time.sleep(5)
            else:
                loopcnt = 0

        # with or without zipboxes
        index=0
        for zipbox in zipboxes:
            try:
                if zipbox.is_displayed():
                    print('bevmo_driver:found zipbox displayed')
                    break
                else:
                    print('bevmo_driver:not displayed:', index)
                    index += 1
            except:
                print('bevmo_driver:zipbox element not attached to the page:', index)
                index += 1
        else:
            print('bevmo_driver:no store inputs are displayed')

        # enter the default store
        print('bevmo_driver:ready to enter store information')
        zipbox.clear()
        print('bevmo_driver:enter store-cleared')
        zipbox.send_keys(defaultstore)
        print('bevmo_driver:enter store-value')
        zipbox.send_keys(Keys.RETURN)
        print('bevmo_driver:pressed return')

        # wait 
        print('bevmo_driver:wait 5 sec for stores to display')
        time.sleep(5)

        # select the cotinue button of the first one returned
        print('bevmo_driver:find the store of interest - and click that button')
        buttons=driver.find_elements_by_class_name('fp-btn-mystore')
        for button in buttons:
            if button.get_attribute('data-store-id') == defaultstoreid:
                print( 'bevmo_driver:clicking button on store:', defaultstoreid )
                button.click()

    except  Exception as e:
        print ('bevmo_driver:failed selecting store')
        print ('bevmo_driver:error:', str(e))
        print ('bevmo_driver:type:', type(e))
        print ('bevmo_driver:args:', e.args)
        if waitonerror:
            input()
        else:
            saveBrowserContent( driver, 'bevmo', 'bevmo_search_fp-btn-mystore' )
            # changed from exist to raise errir
            print('bevmo_driver:raising error')
            raise 
            # we used to exit
            print('bevmo_driver:should not get here - exitWithError')
            exitWithError()
        return None

    # pause to let screen refresh
    print('bevmo_driver:pause 3 seconds to allow screen to refresh for selected store')
    time.sleep(3)

    # Test that the store got set correctly
    # XPATH:  //*[@id="header"]/div[1]/div/div/div/div[2]/div/div/a/span[1]
    print('bevmo_driver:see what store was selected')
    selectedstores = driver.find_elements_by_class_name('fp-store-label')
    print('bevmo_driver:count of selectedstores:', len(selectedstores))
    for selectedstore in selectedstores:
        print('bevmo_driver:selectedstore:', selectedstore.text)
        if selectedstore.is_displayed():
            print('bevmo_driver:selected store name:', selectedstore.text)
            break

    # debugging
    if verbose > 0:
        print('bevmo_driver:complete:---------------------------------------------------')
    
    # return the driver
    return driver


# --------------------------------------------------------------------------

#### TOTALWINE ####


# function used to extract the data from the DOM that was returned
def totalwine_extract_wine_from_DOM(index,titlelist,pricelist,sizelist,fldmatch):
    
    # extract the values
    winename = titlelist[index].text 
    wineprice = pricelist[index].text

    # print('totalwine_extract_wine_from_DOM:',wineprice)

    # size is pulled out based on what fldmatch solution we have
    if fldmatch == 'searchPageContainer':
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
        #print('totalwine_extract_wine_from_DOM:split price:',wineprice)
    elif ('bottle' in wineprice):
        wineprice = wineprice.split(' ')[0]
    elif match:
        wineprice = match.group(1)
        #print('totalwine_extract_wine_from_DOM:match on price',wineprice)
    
    # now clean up $ and ,
    wineprice = wineprice.replace('$','').replace(',','')
    
    # return the dictionary
    return { 'wine_store' : 'TotalCA', 'wine_name' : winename, 'wine_price' : wineprice, 'wine_year' : '', 'label' : '' }


# Search for the wine
def totalwine_search( srchstring, totalwine_driver ):
    global verbose

    # create the array that we will add to
    found_wines = []

    loopcnt = 4
    while(loopcnt):

        # debugging
        print('totalwine_search:go to search page:www.totalwine.com')

        # force the page to start at the top of the page
        totalwine_driver.get('https://www.totalwine.com/')

        # debugging
        print('totalwine_search:find the search_box')
        
        # Select the search box(es) and find if any are visbile - there can be more than one returned value
        try:
            search_box = totalwine_driver.find_element_by_xpath('//*[@id="header-search-text"]')
            print ('totalwine_search:search box found:header-search-text')
            loopcnt = 0
        except Exception as e:
            print('totalwine_search:failed to find:header-search-text')
            # try a different way
            try:
                search_box = totalwine_driver.find_element_by_xpath('//*[@id="at_searchProducts"]')
                print ('totalwine_search:search box found:at_searchProducts')
                loopcnt = 0
            except Exception as e:
                print ('totalwine_search:failed to find:at_searchProducts:loopcnt:', loopcnt)
                saveBrowserContent( totalwine_driver, 'totalwine', 'totalwine_search' )
                print('totalwine_search:could not find search box after both lookups:loopcnt:', loopcnt)
                loopcnt -= 1

    # check that we got a search box
    if not search_box:
        print('totalwine_search:failed to find a search box')
        exitWithError()
        pass

    
    # first check to see that the search box is displayed - if not visible then click the bottom that makes it visible
    if not search_box.is_displayed():
        # debugging
        print ('totalwine_search:search box is not displayed - we want to click the button that displays it')
        # make the search box visible if it is not
        try:
            totalwine_driver.find_element_by_xpath('//*[@id="header-search-mobile"]/span').click()
        except Exception as e:
            print('totalwine_search:could not find search box after both lookups')
            saveBrowserContent( totalwine_driver, 'totalwine', 'totalwine_search' )
            exitWithError()
            pass

    # debugging
    print ('totalwine_search:search for:', srchstring)

    # send in the string to this box and press RETURN
    search_box.clear()
    search_box.send_keys(srchstring)
    search_box.send_keys(Keys.RETURN)

    
    # test to see the result count we got back
    returned_recs = None
    loopcnt = 0
    while returned_recs == None:
        # sleep to give page time to fill in
        print('totalwine_search:pause 0.5 sec to allow the page to fill in')
        time.sleep(0.5)

        # returned records id field: anProdCount, listCount, searchPageContainer
        for fldmatch in ('anProdCount','listCount'):
            print('totalwine_search:fldmatch:',fldmatch)
            resultsfld = totalwine_driver.find_elements_by_id(fldmatch)
            if resultsfld:
                print('totalwine_search:count found on fld:', fldmatch)
                print('totalwine_search:count of fld:', len(resultsfld))
                returned_recs = resultsfld[0].get_attribute('value')
                break

        # first two fields did not work - see if we are on searchPageContainer
        if not returned_recs:
            fldmatch = 'searchPageContainer'
            resultsfld = totalwine_driver.find_elements_by_id(fldmatch)
            if resultsfld:
                print('totalwine_search:count found on fld:', fldmatch)
                print('totalwine_search:count of fld:', len(resultsfld))
                returned_recs = 1

        if not returned_recs:
            fldmatch="resultsTitle__drQnygRS"
            resultsfld = totalwine_driver.find_elements_by_class_name(fldmatch)
            if resultsfld:
                noWineFound =  { 'wine_store' : 'TotalCA', 'wine_name' : 'Sorry no matches were found', 'wine_price' : '1', 'wine_year' : '', 'label' : '' }

                print ('total_search:returned:',noWineFound)
                # return a record that says we could not find the record
                return [ noWineFound ]
                

        # check to see if we have looped to many times
        if loopcnt > 10:
            print('totalwine_search:looped too many times - exiting program')
            saveBrowserContent( totalwine_driver, 'totalwine', 'totalwine_search' )
            exitWithError()
        else:
            loopcnt += 1
            print('totalwine_search:loopcnt:',loopcnt)

    # check to see if we got no results
    if returned_recs == 0:
        print('totalwine_search:', srchstring, ':no results returned - refresh the page we are looking at')
        # update the website we are pointing at
        totalwine_driver.get('https://www.totalwine.com')
        # return a record that says we could not find a record
        return []

    # debugging
    print('totalwine_search:', srchstring, ':returned records:', returned_recs)
    
    # get results back and look for the thing we are looking for - the list of things we are going to process
    if fldmatch == 'searchPageContainer':
        titlelist = totalwine_driver.find_elements_by_class_name('title__11ZhZ3BZ')
        availlist = []
        #mix6list = totalwine_driver.find_elements_by_class_name('plp-product-buy-mix')
        sizelist  = []
        pricelist = totalwine_driver.find_elements_by_class_name('pricingHolder__1VkKua4M')

    else:
        titlelist = totalwine_driver.find_elements_by_class_name('plp-product-title')
        availlist = totalwine_driver.find_elements_by_class_name('plp-product-buy-limited')
        #mix6list = totalwine_driver.find_elements_by_class_name('plp-product-buy-mix')
        sizelist  = totalwine_driver.find_elements_by_class_name('plp-product-qty')
        pricelist = totalwine_driver.find_elements_by_class_name('price')
            
    # debugging
    print('totalwine_search:Counts:title,avail,size,price,fldmatch:', len(titlelist),len(availlist),len(sizelist),len(pricelist),fldmatch)


    # debugging
    if False:
        print ('titlelist-len:', len(titlelist))
        print ('availlist-len:', len(availlist))
        #print ('mix6list-len:', len(mix6list))
        print ('sizelist-len:', len(sizelist))
        print ('pricelist-len:', len(pricelist))

    # message we have a problem
    if len(titlelist) != len(pricelist):
        print('totalwine_search:price and name lists different length:',srchstring,':len(wine):',len(titlelist),':len(price):',len(pricelist))

    
    # now loop through the wines we found
    for index in range(len(pricelist)):
        # we don't grab records where they are out of stock
        if not titlelist[index]:
            print('totalwine_search:no wine title for this row:row skipped')
        if len(availlist)==0 or availlist[index] != "This item is out of stock":
            # this is not out of stock
            found_wines.append( totalwine_extract_wine_from_DOM(index,titlelist,pricelist,sizelist,fldmatch) )
        else:
            # show the out of stock entries to the user/log
            print ('totalwine_search:',titlelist[index],':',availlist[index])

    # debugging
    if verbose > 5:
        print ('totalwine_search:found_wines:', found_wines)

    # return the wines we found
    return found_wines

# function to create a selenium driver for totalwine and get past age question
def create_totalwine_selenium_driver(defaultstore):
    global verbose

    # debugging
    if verbose > 0:
        print('totalwine_driver:start:---------------------------------------------------')
        print ('totalwine_driver:Start up webdriver.Chrome')
    
    
    # Using Chrome to access web
#    driver = webdriver.Chrome()
    driver=create_chrome_webdriver_w3c_off()

    # debugging
    print ('totalwine_driver:Go to www.totalwine.com web page')
    
    # Open the website
    driver.get('https://www.totalwine.com')

    # sleep to allow the dialogue to come up
    print ('totalwine_driver:sleep 1 to allow popup to appear')
    time.sleep(1)

    # check for the button being visible
    try:
        if driver.find_element_by_xpath('//*[@id="btnYes"]'):
            print ('totalwine_driver:found the yes button')
            if driver.find_element_by_xpath('//*[@id="btnYes"]').is_displayed():
                print ('totalwine_driver:button is visible-click to say yes')
                driver.find_element_by_xpath('//*[@id="btnYes"]').click()
    except:
        print('totalwine_driver:no age button displayed - moving along')

    # check to see if we are set to the store of interest (don't pass default - we want a blank if we don't find this)
    store_name = totalwine_driver_get_store(driver)

    # debugging
    print ('totalwine_driver:current store_name:', store_name)

    ### Block out
    if 0:
        # if we get choose store - go to page and test again
        if store_name == 'Choose a location':
            # debugging
            print('totalwine_driver:get_page:www.totalwine.com/store-finder')
            
            # now change the store we are working with
            driver.get('https://www.totalwine.com/store-finder')
            
            # check on store_name again
            store_name = totalwine_driver_get_store(driver)
            
            # debugging
            print ('totalwine_driver:current store_name:', store_name)
    ### endif Block out

    # test to see if store matches current store
    if not re.search(defaultstore, store_name):
        # debugging
        print ('totalwine_driver:current store not set to:', defaultstore, ':set the store')
        store_name = totalwine_driver_set_store(driver, defaultstore)
        print ('totalwine_driver:new store_name:', store_name)
    else:
        print('totalwine_driver:store set to default')
            
    # debugging
    print('totalwine_driver:complete:---------------------------------------------------')
    
    # return the driver
    return driver

# get the store that the website is configured to search
def totalwine_driver_get_store(driver, defaultstore=''):
    global verbose
    # class checks first
    for classname in ('anGlobalStore', 'header-store-details'):
        try:
            print('totalwine_driver_get_store:check_for_class_name:', classname) 
            store = driver.find_elements_by_class_name(classname)
            if store:
                print('totalwine_driver_get_store:class_name:', classname, ':type:', type(store))
                if not isinstance(store,list):
                    # not a list - just pull the value (and lets us know if that value is displayed)
                    print('totalwine_driver_get_store:class_name:', classname, ':not_list:is_displayed:', store.is_displayed())
                    store_name = store.get_attribute('innerText')
                else:
                    # it is a list - we need to figure out which one we want to use
                    print('totalwine_driver_get_store:class_name:', classname, ':number of matches:', len(store))
                    # set it to the first match even if not displayed and then override that if we find a displayed value
                    store_name = store[0].get_attribute('innerText')
                    # loop through entries looking for one that is displaying
                    for i in range(len(store)):
                        print('totalwine_driver_get_store:class_name:', classname, ':', i, ':is_displayed:', store[i].is_displayed())
                        if store[i].is_displayed():
                            store_name = store[i].get_attribute('innerText')
                            print('totalwine_driver_get_store:class_name:', classname, ':found displayed value:set store_name and break out')
                            break
                print('totalwine_driver_get_store:anGlobalStore found-capturing the name:', store_name)
                # get the store attribute
                return store_name.replace('\t','')
        except Exception as e:
            print('totalwine_driver_get_store:ERROR:anGlobalStore:', str(e))
    
    # debugging - did not find the store
    print('totalwine_driver_get_store:did not find store using class_name')

    # now pull the name that is the name of the current store
    for idname in ('globalStoreName_desktop', 'globalStoreName', 'globalStoreName_mobile'):
        try:
            print('totalwine_driver_get_store:check_for_xpath:', idname)
            store = driver.find_element_by_xpath('//*[@id="' + idname + '"]')
            if store:
                # print('totalwine_driver_get_store:', idname, ':type:', type(store))
                if not isinstance(store,list):
                    print('totalwine_driver_get_store:', idname, ':store:is_displayed:', store.is_displayed())
                    store_name = store.get_attribute('innerText')
                else:
                    print('totalwine_driver_get_store:', idname, ':number of matches:', len(store))
                    for i in range(len(store)):
                        print(idname, ':', i, ':is_displayed:', store[i].is_displayed())
                    store_name = store[0].get_attribute('innerText')
                print('totalwine_driver_get_store:', idname, ':found-capturing name:', store_name)
                # get the store attribute
                return store_name
        except Exception as e:
            print('totalwine_driver_get_store:ERROR:', idname, ':', str(e))
    
    print('totalwine_driver_get_store::did not find the name - setting return value to defaultstore:', defaultstore)
    return defaultstore

# change the store the website is configured to search
def totalwine_driver_set_store(driver, defaultstore):
    global verbose

    # debugging
    print('totalwine_driver_set_store:get:www.totalwine.com/store-finder')

    # now change the store we are working with
    driver.get('https://www.totalwine.com/store-finder')

    # search for the field to enter data into
    try:
        store_search_box = driver.find_element_by_xpath('//*[@id="storelocator-query"]')
    except Exception as e:
        print('totalwine_driver_set_store:ERROR:storelocator-query:', str(e))
        saveBrowserContent( driver, 'totalwine', 'totalwine_driver_set_store' )
        exitWithError()

    # dislay a message
    print('totalwine_driver_set_store:search for default store:', defaultstore)

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
            print('totalwine_driver_set_store:wait to find returned stores 3 secs')
            time.sleep(3)
            matching_count_down -= 1

    # now capture the store we found
    select_store=matching_stores[0]
    #
    # select_store = driver.find_element_by_xpath('//*[@id="bottomLeft"]/ul/div/div[1]/li[1]/div/span[6]/button')
    #print('totalwine_driver_set_store:find and click select this store button:', select_store.get_attribute('name'))
    print('totalwine_driver_set_store:find and click select this store button:', select_store.get_attribute('aria-label'))
    try:
        select_store.click()
        print('totalwine_driver_set_store:clicked and selected store button')
    except Exception:
        print('totalwine_driver_set_store:store is not clickable - must already be selected')

    # sleep for 1 second to allow page refresh
    print('totalwine_driver_set_store:sleep 1 sec to allow for page refresh')
    time.sleep(1)

    # now pull the name of the store we are currently configured to work from
    return totalwine_driver_get_store(driver, defaultstore)

    # --------------------------------------------------------------------------

#### WINECLUB ####


# function used to extract the data from the DOM that was returned
def wineclub_extract_wine_from_DOM(index,titlelist,pricelist):
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
    return { 'wine_store' : 'WineClub', 'wine_name' : winename, 'wine_price' : wineprice, 'wine_year' : '', 'label' : '' }


# Search for the wine
def wineclub_search( srchstring, wineclub_driver ):
    global verbose

    # Select the search box(es) and find if any are visbile - there can be more than one returned value
    search_box = wineclub_driver.find_elements_by_xpath('//*[@id="search"]')

    print('wineclub_search:len search box:', len(search_box))
    if len(search_box) > 0:
        search_box = search_box[0]
    else:
        # debugging
        if not 'took too long' in wineclub_driver.page_source:
            print ('wineclub_driver:Go to theoriginalwineclub.com/wine.html web page')
    
            # call routine that finds teh search box and pulls back the search page
            found_search_box, search_box = get_wineclub_url( driver )

            # check to see if we found the search box and if not set to none
            if not found_search_box:
                print('create_wineclub_selenium_driver:did not find search string - setting driver to none')
                saveBrowserContent( wineclub_driver, 'wineclub', 'wineclub_search_box_find' )
                exitWithError('wineclub_search:search_box length was zero')
    
    # first check to see that the search box is displayed - if not visible then click the bottom that makes it visible
    if not search_box.is_displayed():
        # debugging
        print ('wineclub_search:search box is not displayed - we want to click the button that displays it')
        # make the search box visible if it is not
        wineclub_driver.find_element_by_xpath('//*[@id="header-search-mobile"]/span').click()

    # debugging
    print ('wineclub_search:search for:', srchstring)

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
        print('wineclub_search:price and name lists different length:',srchstring,':len(wine):',len(titlelist),':len(price):',len(pricelist))

    # debugging
    if verbose > 5:
        print ('wineclub_search:pricelist:', pricelist)

    # debugging
    print('wineclub_search:', srchstring, ':returned records:',  len(pricelist))
    
    # now loop through the wines we found
    for index in range(len(pricelist)):
        found_wines.append( wineclub_extract_wine_from_DOM(index,titlelist,pricelist) )

    # debugging
    if verbose > 5:
        print ('wineclub_search:found_wines:', found_wines)

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
            print('wineclub_driver:waiting on search box (wait 1 second):', cnt)
            print('error:', str(e))
            if 'took too long' in driver.page_source:
                # did not find a valid page
                print('wineclub_driver:page did not load - took too long - try again')
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
                print('wineclub_driver:page did not load - took too long - try again')
                driver.get('https://theoriginalwineclub.com/wine.html')
                cnt -= 1


    return found_search_box,search_box

# function to create a selenium driver for wineclub and get past popup
def create_wineclub_selenium_driver(defaultzip):
    global verbose

    # debugging
    if verbose > 0:
        print('wineclub_driver:start:---------------------------------------------------')
        print ("wineclub:Start up webdriver.Chrome")
    
    # Using Chrome to access web
#    driver = webdriver.Chrome()
    driver=create_chrome_webdriver_w3c_off()


    # debugging
    print ('wineclub_driver:Go to theoriginalwineclub.com/wine.html web page')
    
    # call routine that finds teh search box and pulls back the search page
    found_search_box, search_box = get_wineclub_url( driver )

    # check to see if we found the search box and if not set to none
    if not found_search_box:
        print('create_wineclub_selenium_driver:did not find search string - setting driver to none')
        saveBrowserContent( driver, 'wineclub', 'create_wineclub_selenium_driver' )
        driver=None

    # debugging
    print('wineclub_driver:complete:---------------------------------------------------')
    

    # return the driver
    return driver


# --------------------------------------------------------------------------

#### HITIME ####

# check to see if we want to keep this price element
def hitimes_price_elem_include( msg, price ):
    global verbose

    
    # do regex and skip old price entries
    if re.search('old-price', price.get_attribute('id')):
        # debugging
        if verbose > 4:
            print('hitime_search:old-price-throw away')
        return False
    elif re.search('\-related', price.get_attribute('id')):
        # debugging
        if verbose > 4:
            print('hitime_search:-related-throw away')
        return False
    else:
        # debugging
        if verbose > 4:
            print('hitime_search:keep-this-price:',  price.get_attribute('id'))
        return True


# function used to extract the data from the DOM that was returned
# pulling back the price record with the lowest price
def hitime_extract_wine_from_DOM(index,titlelist,pricelist):
    global verbose

    
    # extract the values for title
    winename = titlelist[index].text

    # now find the lowest of prices
    winepricemin=100000.00
    for winepricerec in pricelist:
        #print('winepricemin:', winepricemin, ':winepricerec:', winepricerec.text)
        winepriceflt = float(winepricerec.text.replace('$','').replace(',',''))
        if winepricemin > winepriceflt:
            winepricemin = winepriceflt
            # print('min set to:', winepricemin)

    # found the low price convert to string
    wineprice = str(winepricemin)
   
    # old logic commented out
    if False:
        # regex the price field to match our expections
        match = re.search('\$(.*)$',wineprice)
        if match:
            wineprice = match.group(1)

        # now clean up $ and ,
        wineprice = wineprice.replace('$','').replace(',','')
        
    # return the dictionary
    return { 'wine_store' : 'HiTimes', 'wine_name' : winename, 'wine_price' : wineprice,  'wine_year' : '', 'label' : '' }


# Search for the wine
def hitime_search( srchstring, hitime_driver ):
    global verbose

    # Select the search box(es) and find if any are visbile - there can be more than one returned value
    try:
        search_box = hitime_driver.find_element_by_xpath('//*[@id="search"]')
    except  Exception as e:
        print ('hitime_search://*[@id="search"]:no found:error:', str(e))
        print ('hitime_search:type:', type(e))
        print ('hitime_search:args:', e.args)
        saveBrowserContent( hitime_driver, 'hitime', 'hitime_driver' )
        # now get the page again - see if this fixes it
        print ('hitime_search:get the URL again')
        hitime_driver.get('https://hitimewine.net')
        time.sleep(3)
        # do it again
        try:
            print ('hitime_search:find the search field - 2nd attempt')
            search_box = hitime_driver.find_element_by_xpath('//*[@id="search"]')
        except  Exception as e:
            print ('hitime_search://*[@id="search"]:no found:error:', str(e))
            print ('hitime_search:type:', type(e))
            print ('hitime_search:args:', e.args)
            print ('hitime_search:exiting program due to error')
            saveBrowserContent( hitime_driver, 'hitime', 'hitime_driver' )
            exitWithError()
 
    # first check to see that the search box is displayed - if not visible then click the bottom that makes it visible
    if not search_box.is_displayed():
        # debugging
        print ('hitime_search:search box is not displayed')

    # debugging
    print ('hitime_search:search for:', srchstring)

    # send in the string to this box and press RETURN
    search_box.clear()
    search_box.send_keys(srchstring)
    search_box.send_keys(Keys.RETURN)
    
    # create the array that we will add to
    found_wines = []

    # check to see how many results we got back
    try:
        returned_results = hitime_driver.find_elements_by_class_name('empty-catalog')
        if (len(returned_results) > 0):
            print('hitime_search:found-empty-catalog-text:', returned_results[0].text)
            # debugging
            print ('hitime_search:', srchstring, ':no results returned - refresh the page we are looking at')
            # update the website we are pointing at
            hitime_driver.get('https://hitimewine.net')
            # return no results
            return []
        else:
            # debugging
            if verbose > 1:
                print('hitime_search:found-empty-catalog-results:len:', len(returned_results))

    except NoSuchElementException:
        print ('hitime_search:empty-catalog:object not found')
        
    # get results back and look for the thing we are looking for - the list of things we are going to process
    entitylist = hitime_driver.find_elements_by_xpath('//*[@id="category-products-grid"]/ol/li')

    # debugging
    if verbose > 5:
        print('entitylist:', entitylist)

    # step through this list
    for entity in entitylist:
        # extract out for this entry these - we use elements so we don't need to try/catch
        titlelist = entity.find_elements_by_class_name('product-name')
        pricelistraw = entity.find_elements_by_class_name('price')
        pricelistreg = entity.find_elements_by_class_name('regular-price')
        pricelistwrapper = entity.find_elements_by_class_name('price-wrapper')

        # debugging
        if verbose > 5:
            print('pricelistraw:', pricelistraw)
            print('pricelistreg:', pricelistreg)
            print('pricelistwrapper:', pricelistwrapper)

        # pull out the entry of interest
        if len(pricelistwrapper):
            found_wines.append( hitime_extract_wine_from_DOM(0,titlelist,pricelistwrapper) )
        elif len(pricelistraw):
            found_wines.append( hitime_extract_wine_from_DOM(0,titlelist,pricelistraw) )
        else:
            found_wines.append( hitime_extract_wine_from_DOM(0,titlelist,pricelistreg) )


    # debugging
    print ('hitime_search:found_wines:', len(found_wines))

    # return the wines we found
    return found_wines

# function to create a selenium driver for hitime and get past the close link
def create_hitime_selenium_driver(defaultzip):
    global verbose

    # debugging
    if verbose > 0:
        print('hitime_driver:start:---------------------------------------------------')
        print('hitime_driver:Start up webdriver.Chrome')
    
    # Using Chrome to access web
#    driver = webdriver.Chrome()
    driver=create_chrome_webdriver_w3c_off()

    # debugging
    print ('hitime_driver:Go to hitimewine.net web page')
    
    # Open the website
    driver.get('https://hitimewine.net')

    # sleep to allow the dialogue to come up
    print ('hitime_driver:sleep 1 to allow popup to appear')
    time.sleep(1)

    # check for the button and click it
    try:
        # find the element
        close_link = driver.find_element_by_xpath('//*[@id="contentInformation"]/div[2]/div[2]/a')
        # set the loop counter
        loopcnt = 0
        while not close_link.is_displayed() and loopcnt < 11:
            # increment the counter
            loopcnt += 1
            # debugging
            print('hitime_driver:wait 1 second for the object to be displayed-loopcnt:', loopcnt)
            # sleep
            time.sleep(1)

        # now we waited long enough - what do we do now?
        if close_link.is_displayed():
            # debugging
            print('hitime_driver:close_link.click')
            # click the link
            close_link.click()
        else:
            # debugging - never ended up being displayed - so message this
            print('hitime_driver:close_link found but not displayed')
    except NoSuchElementException:
        print ('hitime_driver:close_link does not exist')

    # make sure we have a search box in the page that we obtained
    try:
        search_box = driver.find_element_by_xpath('//*[@id="search"]')
    except  Exception as e:
        print ('hitime_driver://*[@id="search"]:no found:error:', str(e))
        print ('hitime_driver:type:', type(e))
        print ('hitime_driver:args:', e.args)
        print ('hitime_driver:exiting program due to error')
        saveBrowserContent( hitime_driver, 'hitime', 'hitime_driver' )
        exitWithError()


    # debugging
    print('hitime_driver:complete:---------------------------------------------------')
    

    # return the driver
    return driver


# --------------------------------------------------------------------------

#### WALLY ####


# function used to extract the data from the DOM that was returned
def wally_extract_wine_from_DOM(index,titlelist,pricelist):
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
    return { 'wine_store' : 'Wally-LA', 'wine_name' : winename, 'wine_price' : wineprice, 'wine_year' : '', 'label' : '' }


# Search for the wine
def wally_search( srchstring, wally_driver ):
    global verbose

    # Select the search box(es) and find if any are visbile - there can be more than one returned value
    search_box = wally_driver.find_element_by_xpath('//*[@id="search"]')
    
    # first check to see that the search box is displayed - if not visible then click the bottom that makes it visible
    if not search_box.is_displayed():
        # debugging
        print ('wally_search:search box is not displayed')

    # debugging
    print ('wally_search:search for:', srchstring)

    # send in the string to this box and press RETURN
    search_box.clear()
    search_box.send_keys(srchstring)
    search_box.send_keys(Keys.RETURN)
    
    # create the array that we will add to
    found_wines = []

    # get results back and look for the thing we are looking for - the list of things we are going to process
    titlelist = wally_driver.find_elements_by_class_name('product-name')
    pricelist = wally_driver.find_elements_by_class_name('price-box')

    # debugging
    print('wally_search:', srchstring, ':returned records:',  len(pricelist))
    
    # debugging
    if verbose > 5:
        print ('wally_search:pricelist:', pricelist)

    # message we have a problem
    if len(titlelist) != len(pricelist):
        print('wally_search:price and name lists different length:',srchstring,':len(wine):',len(titlelist),':len(price):',len(pricelist))
        # check to see if we don't have enough titles for prices
        if len(titlelist) < len(pricelist):
            print('wally_search:len-titlelist:',len(titlelist))
            print('wally_search:len-pricelist:',len(pricelist))
            print('wally_search:exitting program due to error:titles are less than prices')
            print('wally_search:actually we just return an empty list and SKIP this wine')
            saveBrowserContent( wally_driver, 'wally', 'wally_search')
            return found_wines
            #exitWithError()

    # now loop through the wines we found
    for index in range(len(pricelist)):
        found_wines.append( wally_extract_wine_from_DOM(index,titlelist,pricelist) )

    # debugging
    if verbose > 5:
        print ('wally_search:found_wines:', found_wines)

    # return the wines we found
    return found_wines

# function to create a selenium driver for wallys
def create_wally_selenium_driver(defaultzip):
    global verbose

    # debugging
    if verbose > 0:
        print('wally_driver:start:---------------------------------------------------')
        print ('wally_driver:Start up webdriver.Chrome')
    
    # Using Chrome to access web
#    driver = webdriver.Chrome()
    driver=create_chrome_webdriver_w3c_off()

    # debugging
    print ('wally_driver:Go to www.wallywine.com web page')
    
    # Open the website
    try:
        driver.get('https://www.wallywine.com')
        search_box = driver.find_element_by_xpath('//*[@id="search"]')
    except Exception as e:
        print('wally_driver:error:', str(e))
        print('wally_driver:failed:REMOVING this store from this run')
        driver = None

    # debugging
    print('wally_driver:complete:---------------------------------------------------')
    

    # return the driver
    return driver


#### PAVILLIONS ####


# function used to extract the data from the DOM that was returned
def pavillions_extract_wine_from_DOM(index,titlelist,pricelist):
    global verbose

    
    # extract the values
    winename = titlelist[index].text
    wineprice = pricelist[index].text

    # print('pavillions_extract_wine_from_DOM:wineprice:',wineprice)

    # regex the price field to match our expections
    match = re.search('\$(.*)$',wineprice)
    if match:
        wineprice = match.group(1)
    
    # now clean up $ and ,
    wineprice = wineprice.replace('$','').replace(',','')

    # return the dictionary
    return { 'wine_store' : 'Vons', 'wine_name' : winename, 'wine_price' : wineprice, 'wine_year' : '', 'label' : '' }


# Search for the wine
def pavillions_search( srchstring, pavillions_driver ):
    global verbose
    global test
    global pavillions_search_xpath

    # debugging
    print ('pavillions_search:go to search page:shop.pavilions.com/home.html')

    # force entry on to the search page first
    pavillions_driver.get('https://shop.pavilions.com/home.html')

    # debugging
    print ('pavillions_search:find the search_box')

    # find the search box (change the xpath to the search window)
    search_box = pavillions_find_search_box(pavillions_driver)
    
    # debugging
    if verbose > 5:
        # find all the matches - get all - not just first
        search_boxs = pavillions_driver.find_elements_by_xpath('//*[@id="search-img"]')
        print('number of search_boxs:', len(search_boxs))
        for element in search_boxs:
            print_html_elem('pavillions_search:element:', 0, element)
            print('=================================')

    # check to see the search box is visible - if not we have a problem
    if not search_box.is_displayed():
        # debugging
        print ('pavillions_search:search box 2 is not displayed - this is a problem - exit')
        print_html_elem('pavillions_search:search_box2:', 0, search_box)
        # close the browser because we are going to quit
        print('pavilliions_search:exitting program due to error:missing search box')
        saveBrowserContent( pavillions_driver, 'pav', 'pavillions_search' )
        pavillions_driver.quit()
        exitWithError()

    # debugging
    print ('pavillions_search:search for:', srchstring, ' in wines:search_box:', search_box.get_attribute('name'))

    # send in the string to this box and press RETURN
    search_box.clear()
    search_box.send_keys(srchstring + ' in wines')
    search_box.send_keys(Keys.RETURN)
    
    # create the array that we will add to
    found_wines = []

    # it may take time to get this to show up - so lets build a small loop here
    for tries in range(4):
        try:
            returned_result = pavillions_driver.find_element_by_xpath('//*[@id="search-summary_0"]/div/div/h1')
            break
        except Exception as e:
            print('pavillions_search:did not find [search-summary_0] waiting 1 second try number:', tries)
            time.sleep(1)
    
    # first test - see if we got no results found - if so return the empty array
    try:
        # see if we got a result string back - errors out if we did not
        returned_result = pavillions_driver.find_element_by_xpath('//*[@id="search-summary_0"]/div/div/h1')
        #search changed on 2018-10-25
        #returned_result = pavillions_driver.find_element_by_xpath('//*[@id="searchNrResults"]')

        # debugging
        if 0:
            print ('returned result object:', returned_result)
            print ('returned result:', returned_result.text)
            print ('returned result tag_name:', returned_result.tag_name)
            print ('returned result parent:', returned_result.parent)
            print ('returned result innerHTML:', returned_result.get_attribute('innerHTML'))
            print ('returned result Text:', returned_result.get_attribute('text'))
            print ('returned result innerText:', returned_result.get_attribute('innerText'))
            print ('returned result textContext:', returned_result.get_attribute('textContext'))
            print ('returned result value:', returned_result.get_attribute('value'))
            print ('returned result ID:', returned_result.get_attribute('id'))
            print ('returned result name:', returned_result.get_attribute('name'))
            print ('returned result class:', returned_result.get_attribute('class'))
            print ('returned result type:', returned_result.get_attribute('type'))
            
        # we must wait for the element to show
        while not returned_result.text:
            print ('pavillions_search:Waiting 1 second on result text to show')
            time.sleep(1)
            
        # result text
        result_text = returned_result.text

        # now check to see if the answer was no result
        if re.match('No results', result_text):
            # debugging
            print ('pavillions_search:', srchstring, ':no results returned - refresh the page we are looking at')
            # return a record that says we could not find the record
            return found_wines
        else:
            # debugging
            print('pavillions_search:following found results:',  result_text)
    except  Exception as e:
        print ('pavillions_search:search-summary_0 - not found for (' + srchstring + ') - result were found - error:', str(e))
        print ('pavillions_search:type:', type(e))
        print ('pavillions_search:args:', e.args)
        print ('pavillions_search:exitting program due to error:debug why we did not get back search-summary_0')
        saveBrowserContent( pavillions_driver, 'pav', 'pavillions_search' )
        # test a modified case to see if we can debug this some more (2018-10-25)
        try:
            returned_result = pavillions_driver.find_element_by_xpath('//*[@id="search-summary_0"')
            print('pavillions_search:id="search-summary_0":found this xpath')
        except Exception as e:
            print('pavillions_search:id="search-summary_0":NOT found')
        if test:
            exitWithError('quitting - debug in the browser please')

        print('pavillions_search:actually we just return an empty list and SKIP this wine')
        return found_wines
        # exitWithError()

    # get results back and look for the thing we are looking for - the list of things we are going to process
    titlelist = pavillions_driver.find_elements_by_class_name('product-title')
    pricelist = pavillions_driver.find_elements_by_class_name('product-price')

    # convert to text - commented out for now - we can come back and look at this in the future
    if False:
        # convert web objects to text
        titlelisttext = [i.text for i in titlelist]
        pricelisttext = [i.text for i in pricelist]
        # debugging
        print('titlelisttext:', titlelisttext)
        print('pricelisttext:', pricelisttext)

    # message we have a problem
    if len(titlelist) != len(pricelist):
        print('pavillions_search:price and name lists different length:',srchstring,':len(wine):',len(titlelist),':len(price):',len(pricelist))

    # debugging
    if verbose > 5:
        print ('pavillions_search:pricelist:', pricelist)
    
    # debugging
    print('pavillions_search:', srchstring, ':returned records:',  len(pricelist))

    # now loop through the wines we found
    for index in range(len(pricelist)):
        found_wines.append( pavillions_extract_wine_from_DOM(index,titlelist,pricelist) )

    # debugging
    if verbose > 5:
        print ('pavillions_search:found_wines:', found_wines)

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
        print('pavillions_find_search_box_by_id:search-img:found')
    except Exception as e:
        print('pavillions_find_search_box_by_id:search-img:NOT-found')

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
                print('pavillions_find_search_box_by_class_name:ecomm-search:found at index:', counter)
                break
            # increment the counter if we are not done
            counter+=1
        # check the final search_box
        if not search_box.is_displayed():
            search_box=None
            print('pavillions_find_search_box_by_class_name:ecomm-search:NOT-found-displayed')
    except Exception as e:
        print('pavillions_find_search_box_by_class_name:ecomm-search:NOT-found')

    if not search_box.is_displayed():
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
            print('pavillions_find_search_box_by_xpaths:find search:', pavillions_search_xpath)
            search_box = driver.find_element_by_xpath( pavillions_search_xpath )
        except Exception as e:
            print('pavillions_find_search_box_by_xpaths:search box xpath not valid')
            continue

        # check to see the search box is visible - if not we have a problem
        if not search_box.is_displayed():
            # debugging
            print ('pavillions_find_search_box_by_xpaths:search box is not displayed - this is a problem - try another')
            print_html_elem('pavillions_find_search_box_by_xpaths:search_box:', 0, search_box)
            # clear the search string
            pavillions_search_xpath = ''
            # close the browser because we are going to quit
            # driver.quit()
            # exitWithError()

            # clear the search_box we found - it is not the one we want
            search_box=None
        else:
            if test:
                print('pavillions_find_search_box_by_xpaths:test-enabled:search box:found')
            # now break out of hte loop we have what we need
            print('pavillions_find_search_box_by_xpaths:found_search_box:', pavillions_search_xpath)
            # break out we have found the one we want to use
            break

    return search_box

# set the default shopping zipcode for this browser
def set_pavillions_shopping_zipcode(driver, defaultzip):
    # debugging
    print('pavillions_driver:setting zipcode')
    
    # drive to set the zipdoe
    driver.get('https://shop.pavilions.com/change-zipcode.html')
    
    
    ### ZIPCODE - check to see if the zip code is selectable
    try:
        # see if the zipcode field is here
        if driver.find_element_by_xpath('//*[@id="zipcode"]'):
            # debugging
            print ('pavillions_driver:filling in the zipcode: ', defaultzip)
            
            # set the store to the defaultstore
            zipcode_box = driver.find_element_by_xpath('//*[@id="zipcode"]')
            
            # fill in the infomratoin
            zipcode_box.clear()
            zipcode_box.send_keys(defaultzip)
            zipcode_box.send_keys(Keys.RETURN)
            
            # debugging
            print ('pavillions_driver:zipcode populated')
            
            # see if we get the response
            try:
                shopInZip = driver.find_element_by_class_name('guest-pref-panel-zip')
            except:
                shopInZip = None
                
            while not shopInZip:
                # pause to give time for the search page to show
                timewait = 2
                print ('pavillions_driver:sleep for ' + str(timewait) + ' seconds to allow the search to pop up')
                time.sleep(timewait)
                
                # see if we get the response
                try:
                    shopInZip = driver.find_element_by_class_name('guest-pref-panel-zip')
                except:
                    shopInZip = None
                    
        else:
            # debugging
            print ('pavillions_driver:No zipcode to enter')
    except  Exception as e:
        print ('pavillions_driver:zipcode - not found for (' + defaultzip + ') - results were found - error:', str(e))



# function to create a selenium driver for pavillions and enter zipcode
def create_pavillions_selenium_driver(defaultzip):
    global verbose

    # global variable that defines which search box string to use
    global pavillions_search_xpath

    # debugging
    if verbose > 0:
        print('pavillions_driver:start:---------------------------------------------------')
        print ('pavillions_driver:Start up webdriver.Chrome')
    
    # Using Chrome to access web
#    driver = webdriver.Chrome()
    driver=create_chrome_webdriver_w3c_off()

    # debugging
    print ('pavillions_driver:Go to shop.pavillions.com web page')
    
    # Open the website
    driver.get('https://shop.pavilions.com/home.html')

    # check the default zip to see if it matches
    print('pavillions_driver:check current zipcode setting')
    driverzip = None
    try:
        print('pavillions_driver:finding the current zipcode')
        # read the default zip
        shopInZip = driver.find_element_by_class_name('guest-pref-panel-zip')
        # check to see if it matches
        if shopInZip.text and shopInZip.text[-5:] == defaultzip:
            # we already have the zip we want - no reason to set it
            print('pavillions_driver:already set to defaultzip')
            # capture the driver zip
            driverzip = defaultzip
        else:
            print('pavillions_driver:current zip not a match')
    except:
        print('pavillions_driver:unable to lookup:guest-pref-panel-zip')

    # lookup the zipcode if not set
    if not driverzip:
        print('pavillions_driver:calling routine to set zipcode')
        set_pavillions_shopping_zipcode(driver,defaultzip)

    ### SEARCH_BOX

    # there are 3 different ways to find the search box
    # 1) id='search-img'
    # 2) class_name='ecomm-search'
    # 3) xpath with a list of search pathes
    search_box = pavillions_find_search_box(driver)

    # check to see we have a search string
    if not search_box:
        print('create_pavillions_selenium_driver:no search box found')
        # save this page for future research
        saveBrowserContent( driver, 'pav', 'pav_driver' )
        #
        print('create_pavillions_selenium_driver:should have saved html')
        # close the browser because we are going to quit
        driver.quit()
        exitWithError()
        

    # debugging
    print('pavillions_driver:complete:---------------------------------------------------')
    
    # return the driver
    return driver


# ----------------------------------------------------


#### WINEX ####


# function used to extract the data from the DOM that was returned
def winex_extract_wine_from_DOM(index,titlelist,pricelist):
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
    return { 'wine_store' : 'WineEx', 'wine_name' : winename, 'wine_price' : wineprice, 'wine_year' : '', 'label' : '' }


# Search for the wine
def winex_search( srchstring, winex_driver ):
    global verbose

    # debugging
    print ('winex_search:search for:', srchstring)

    # create the url of interest
    url = 'https://www.winex.com/catalogsearch/result/?q=%s' % srchstring

    # get this page
    winex_driver.get(url)

    # create the array that we will add to
    found_wines = []

    # get results back and look for the thing we are looking for - the list of things we are going to process
    winelist  = winex_driver.find_elements_by_class_name('product-item-info')
    titlelist = winex_driver.find_elements_by_class_name('product-item-link')
    availlist = winex_driver.find_elements_by_class_name('stock-status-wx')
    pricelist = winex_driver.find_elements_by_class_name('price-wrapper')
    # pricelist = finalpricelist.find_elements_by_class_name('price')
    # calculate the min number of entries returned
    minEntries = min( len(winelist),len(titlelist),len(availlist),len(pricelist) )


    # debugging
    print('winex_search:Counts:wine,title,avail,price:', len(winelist),len(titlelist),len(availlist),len(pricelist))
    print('winex_search:minEntries:', minEntries)
    
    # debugging
    if verbose > 5:
        for index in range(minEntries):
            print ('index:', index)
            if 0 and index < len(winelist):
                print('wine:', winelist[index].text)
            if index + 1 < len(titlelist):
                print('title:', titlelist[index].text)
            if index + 1 < len(pricelist):
                print('price:', pricelist[index].text)
            if index + 1 < len(availlist):
                print('avail:', availlist[index].text)
                

    # now loop through the wines we found
    for index in range(minEntries):
        # if out of stock skip this entry
        if availlist[index].text == 'Out of Stock':
            print('winex_search:out of stock:', titlelist[index].text)
            next
        if verbose > 1:
            print('index:', index)
        try:
            titlelist[index].text
            found_wines.append( winex_extract_wine_from_DOM(index,titlelist,pricelist) )
        except:
            print('could not get the title for index:',index)
            saveBrowserContent( winex_driver, 'winex', 'winex_search' )


    # debugging
    if verbose > 5:
        print ('winex_search:found_wines:', found_wines)

    # return the wines we found
    return found_wines

# function to create a selenium driver for winexs
def create_winex_selenium_driver(defaultzip):
    global verbose

    # debugging
    if verbose > 0:
        print('winex_driver:start:---------------------------------------------------')
        print ('winex_driver:Start up webdriver.Chrome')
    
    # Using Chrome to access web
#    driver = webdriver.Chrome()
    driver=create_chrome_webdriver_w3c_off()

    # debugging
    print ('winex_driver:Go to www.winex.com web page')
    
    # Open the website
    try:
        driver.get('https://www.winex.com')
    except Exception as e:
        print('winex_driver:error:', str(e))
        print('winex_driver:failed:REMOVING this store from this run')
        driver = None

    # debugging
    print('winex_driver:complete:---------------------------------------------------')
    

    # return the driver
    return driver


# ----------------------------------------------------

### NAPA CAB ####

# function used to extract the data from the DOM that was returned
def napacab_extract_wine_from_DOM(index,titlelist,pricelist):
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
    return { 'wine_store' : 'NapaCab', 'wine_name' : winename, 'wine_price' : wineprice, 'wine_year' : '', 'label' : '' }


# Search for the wine
def napacab_search( srchstring, napacab_driver ):
    global verbose

    # no wine found record
    noWineFound =  { 'wine_store' : 'NapaCab', 'wine_name' : 'Sorry no matches were found', 'wine_price' : '1', 'wine_year' : '', 'label' : '' }

    # Select the search box(es) and find if any are visbile - there can be more than one returned value
    search_box = napacab_driver.find_elements_by_xpath('//*[@id="search_query"]')

    print('napacab_search:len search box:', len(search_box))
    if len(search_box) > 0:
        search_box = search_box[0]
    else:
        saveBrowserContent( napacab_driver, 'napacab', 'napacab_search_box_find' )
        exitWithError('napacab_search:search_box length was zero')
    
    # first check to see that the search box is displayed - if not visible then click the bottom that makes it visible
    if not search_box.is_displayed():
        # debugging
        print ('napacab_search:search box is not displayed - we want to click the button that displays it')
        # make the search box visible if it is not
        napacab_driver.find_element_by_xpath('//*[@id="header-search-mobile"]/span').click()

    # debugging
    print ('napacab_search:search for:', srchstring)

    # send in the string to this box and press RETURN
    search_box.clear()
    search_box.send_keys(srchstring)
    search_box.send_keys(Keys.RETURN)

    # pause to allow time to load the page
    print('napacab_search:wait 3 seconds for page load')
    time.sleep(3)
    
    # create the array that we will add to
    found_wines = []

    # capture from the page the number of results returned
    try:
        resultsheading = napacab_driver.find_elements_by_id('search-results-heading')
    except:
        print('napacab_search:failed to find search-results-heading')
        # save this page for future research
        saveBrowserContent( napacab_driver, 'napacab', 'napacab_search' )
        # return noWineFound for now - but there is a bigger issue
        return [ noWineFound ]

    # check to see if we got anything back
    if resultsheading:
        if resultsheading[0].text.split(' ')[0] == '0':
            print ('napacab_search:returned:',noWineFound)
            # return a record that says we could not find the record
            return [ noWineFound ]

    # get results back and look for the thing we are looking for - the list of things we are going to process
    try:
        titlelist = napacab_driver.find_elements_by_class_name('card-title')
        pricelist = napacab_driver.find_elements_by_class_name('price--main')
    except:
        print('napacab_search:failed to find card-title or price-main')
        # save this page for future research
        saveBrowserContent( napacab_driver, 'napacab', 'napacab_search' )
        # return noWineFound for now - but there is a bigger issue
        return [ noWineFound ]
        
    # message we have a problem
    if len(titlelist)*2 != len(pricelist):
        print('napacab_search:price and name lists different length:',srchstring,':len(wine):',len(titlelist),':len(price):',len(pricelist))

    # debugging
    if verbose > 5:
        print ('napacab_search:pricelist:', pricelist)

    # debugging
    print('napacab_search:', srchstring, ':returned records:',  len(titlelist))
    
    # now loop through the wines we found
    for index in range(len(titlelist)):
        found_wines.append( napacab_extract_wine_from_DOM(index,titlelist,pricelist) )

    # debugging
    if verbose > 5:
        print ('napacab_search:found_wines:', found_wines)

    # return the wines we found
    return found_wines

# function to create a selenium driver for napacab and get past popup
def create_napacab_selenium_driver(defaultzip):
    global verbose

    # debugging
    if verbose > 0:
        print('napacab_driver:start:---------------------------------------------------')
        print ("napacab:Start up webdriver.Chrome")
    
    # Using Chrome to access web
#    driver = webdriver.Chrome()
    driver=create_chrome_webdriver_w3c_off()

    # debugging
    print ('napacab_driver:Go to https://www.napacabs.com/ web page')
    
    # Open the website
    driver.get('https://www.napacabs.com/')

    # try to get the search box
    cnt=10
    found_search_box = False
    while(cnt):
        try:
            search_box = driver.find_element_by_xpath('//*[@id="search_query"]')
        except  Exception as e:
            # did not find the search box
            print('napacab_driver:waiting on search box (wait 1 second):', cnt)
            print('error:', str(e))
            time.sleep(1)
            cnt -= 1
        else:
            # get out of this loop we got what we wanted
            found_search_box = True
            cnt = 0

    # check to see if we found the search box and if not set to none
    if not found_search_box:
        driver=None

    # click the over21 button
    btns = driver.find_elements_by_class_name('pxpop-link')
    # step through the buttons
    for btn in btns:
        if btn.get_attribute('innerText') == "I'M OVER 21":
            print('napacab:press im over 21 button')
            btn.click()
            break
    else:
        print('napacab:never pressed the im over 21 button')


    # debugging
    print('napacab_driver:complete:---------------------------------------------------')
    

    # return the driver
    return driver

# -----------------------------------------------



# routine use by email parser to grab the results for one wine
def get_wines_from_stores( srchstring_list, storelist, debug=False ):
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
        totalwine_driver = create_totalwine_selenium_driver('Laguna Hills')
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
            if verbose > 5: print ('wineselenium.py:', srchstring, ' count of wines found:', len(found_wines))
        if 'pavillions' in storelist:
            found_wines.extend( pavillions_search( srchstring, pavillions_driver ) )
            # debugging
            if verbose > 5: print ('wineselenium.py:', srchstring, ' count of wines found:', len(found_wines))
        if 'wineclub' in storelist:
            found_wines.extend( wineclub_search( srchstring, wineclub_driver ) )
            # debugging
            if verbose > 5: print ('wineselenium.py:', srchstring, ' count of wines found:', len(found_wines))
        if 'totalwine' in storelist:
            found_wines.extend( totalwine_search( srchstring, totalwine_driver ) )
            # debugging
            if verbose > 5: print ('wineselenium.py:', srchstring, ' count of wines found:', len(found_wines))
        if 'hitime' in storelist:
            found_wines.extend( hitime_search( srchstring, hitime_driver ) )
            # debugging
            if verbose > 5: print ('wineselenium.py:', srchstring, ' count of wines found:', len(found_wines))
        if 'wally' in storelist:
            found_wines.extend( wally_search( srchstring, wally_driver ) )
            # debugging
            if verbose > 5: print ('wineselenium.py:', srchstring, ' count of wines found:', len(found_wines))
        if 'winex' in storelist:
            found_wines.extend( winex_search( srchstring, winex_driver ) )
            # debugging
            if verbose > 5: print ('wineselenium.py:', srchstring, ' count of wines found:', len(found_wines))
        if 'napacab' in storelist:
            found_wines.extend( napacab_search( srchstring, napacab_driver ) )
            # debugging
            if verbose > 5: print ('wineselenium.py:', srchstring, ' count of wines found:', len(found_wines))

        # debugging
        if verbose > 5: print ('wineselenium.py:', srchstring, ' count of wines found:', len(found_wines))



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

    # from the command line
    wineoutfile = optiondict['wineoutfile']
    winexlatfile = optiondict['winexlatfile']
    
    # dump out what we have done here
    if test:
        print ('---------------TEST FLAG ENABLED---------------------------')


    # check to see if we passed in srchlist instead of srchstring
    if optiondict['srchlist'] and not optiondict['srchstring']:
        print('srchlist was passed in INSTEAD of srchstring - substituting')
        optiondict['srchstring'] = optiondict['srchlist']
    

    # debugging
    if verbose > 0:
        print ('---------------STARTUP(v', optiondictconfig['AppVersion']['value'], ')-(', datetime.datetime.now().strftime('%Y%m%d:%T'), ')---------------------------')

    # define the store list - all the stores we COULD process
    storelist = [
        'bevmo',
        'hitime',
        'pavillions',
        'totalwine',
        'wineclub',
        'wally',
        'winex',
        'napacab',
    ]

    # check to see if we got a command line store list
    if optiondict['storelist']:
        storelist = [ optiondict['storelist'] ]

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
        print('test:storelist:', storelist)

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
        print('test:srchstring_list:', srchstring_list)

    # if not user defined - generate the list if we don't have one predefined
    if srchstring_list == None:
        print('wineselenium.py:load list of wines from:',wineinputfile)
        srchstring_list = get_winelist_from_file( wineinputfile )
        remove_already_processed_wines( wineoutfile, srchstring_list )
        if not srchstring_list:
            print('main:no wines to search for - ending program')
            sys.exit()

    # load in xlat file in to a global variable
    store_wine_lookup = read_wine_xlat_file( winexlatfile, debug=verbose )

    # create each of the store drivers we need to use
    if 'totalwine' in storelist:
        totalwine_driver = create_totalwine_selenium_driver('Laguna Hills')
        # if we did not get a valid driver - then we are not using this store.
        if totalwine_driver == None:  
            storelist.remove('totalwine')
            print('main:FAILED:removed store from search:totalwine')
    if 'bevmo' in storelist:
        bevmo_driver = create_bevmo_selenium_driver('Ladera Ranch', '2962', optiondict['bevmoretrycount'], optiondict['waitonerror'])
        # if we did not get a valid driver - then we are not using this store.
        if bevmo_driver == None:  
            storelist.remove('bevmo')
            print('main:FAILED:removed store from search:bevmo')
    if 'pavillions' in storelist:
        pavillions_driver = create_pavillions_selenium_driver('92688')
    if 'wineclub' in storelist:
        wineclub_driver = create_wineclub_selenium_driver('92688')
        # if we did not get a valid driver - then we are not using this store.
        if wineclub_driver == None:  
            storelist.remove('wineclub')
            print('main:FAILED:removed store from search:wineclub')
    if 'hitime' in storelist:
        hitime_driver = create_hitime_selenium_driver('92688')
    if 'wally' in storelist:
        wally_driver = create_wally_selenium_driver('')
        if wally_driver == None:
            storelist.remove('wally')
            print('main:FAILED:removed store from search:wally')
    if 'winex' in storelist:
        winex_driver = create_winex_selenium_driver('')
        if winex_driver == None:  storelist.remove('winex')
    if 'napacab' in storelist:
        napacab_driver = create_napacab_selenium_driver('92688')
               
               
    # dump out what we have done here
    if verbose > 0:
        print ('------------------------------------------')
        print ('wineselenium.py:version:',AppVersion)
        print ('wineselenium.py:srchstring_list:', srchstring_list)
        print ('wineselenium.py:storelist:', storelist)
        print ('------------------------------------------')
        
    # step through the list
    for srchstring in srchstring_list:
        # create the list of records for each search string
        found_wines = []
        # find the wines for this search string
        # find the wines for this search string
        if 'bevmo' in storelist:
            found_wines.extend( bevmo_search( srchstring, bevmo_driver, optiondict['waitonerror'] ) )
            # debugging
            if verbose > 5: print ('wineselenium.py:', srchstring, ' count of wines found:', len(found_wines))
        if 'pavillions' in storelist:
            found_wines.extend( pavillions_search( srchstring, pavillions_driver ) )
            # debugging
            if verbose > 5: print ('wineselenium.py:', srchstring, ' count of wines found:', len(found_wines))
        if 'wineclub' in storelist:
            found_wines.extend( wineclub_search( srchstring, wineclub_driver ) )
            # debugging
            if verbose > 5: print ('wineselenium.py:', srchstring, ' count of wines found:', len(found_wines))
        if 'totalwine' in storelist:
            found_wines.extend( totalwine_search( srchstring, totalwine_driver ) )
            # debugging
            if verbose > 5: print ('wineselenium.py:', srchstring, ' count of wines found:', len(found_wines))
        if 'hitime' in storelist:
            found_wines.extend( hitime_search( srchstring, hitime_driver ) )
            # debugging
            if verbose > 5: print ('wineselenium.py:', srchstring, ' count of wines found:', len(found_wines))
        if 'wally' in storelist:
            found_wines.extend( wally_search( srchstring, wally_driver ) )
            # debugging
            if verbose > 5: print ('wineselenium.py:', srchstring, ' count of wines found:', len(found_wines))
        if 'winex' in storelist:
            found_wines.extend( winex_search( srchstring, winex_driver ) )
            # debugging
            if verbose > 5: print ('wineselenium.py:', srchstring, ' count of wines found:', len(found_wines))
        if 'napacab' in storelist:
            found_wines.extend( napacab_search( srchstring, napacab_driver ) )
            # debugging
            if verbose > 5: print ('wineselenium.py:', srchstring, ' count of wines found:', len(found_wines))

        # debugging
        print ('wineselenium.py:', srchstring, ' count of wines found:', len(found_wines))

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

# eof
