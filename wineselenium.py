'''
@author:   Ken Venner
@contact:  ken@venerllc.com
@version:  1.60

Using Selenium and Chrome - screen scrape wine websites to draw
down wine pricing and availiability information

'''

from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException

import kvutil

import time
import re
import datetime
import sys


# application variables
optiondictconfig = {
    'AppVersion' : {
        'value' : '1.60',
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
}

# define if we are running in test mode
test=False

# global variable - rundate set at strat
datefmt = '%m/%d/%Y'
rundate = datetime.datetime.now().strftime(datefmt)
store_wine_lookup = {}
AppVersion    = 'NotSet'
wineoutfile   = 'wineselenium.csv'
wineinputfile = 'getwines.bat'
winexlatfile  = 'wine_xlat.csv'
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
            print('remove_already_processed_wines:', winefile, ':does not exist-no stores removed from processing list')

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
    with open( filename, 'w' ) as p:
        p.write( driver.page_source )
    print(function + ':saved html page content to:', filename)
        
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

#### BEVMO ####

# function used to extract the data from the DOM that was returned
def bevmo_extract_wine_from_DOM(index,winelist):
    global verbose

    # Step thorugh this list and extract out the data of interest - we are doing one example
    #
    # extract out the single element that is the product name
    winename = winelist[index].find_elements_by_class_name('product-name')[0].text

    #
    # step through the prices until we find one that works
    # this price types are ordered in preference of use
    # we will stop looking once we find a price
    pricetypes = ['special-price','promo-price','regular-price','old-price']
    for pricetype in pricetypes:
        # search for this element
        priceelement = winelist[index].find_elements_by_class_name(pricetype)
        # if we got back any values (the len > 0)
        if len(priceelement):
            # this is the price we are going with
            wineprice = priceelement[0].text
            # now strip the unwanted text
            wineprice = re.sub('\s+.*', '', wineprice)
            # now strip the dollar sign
            wineprice = re.sub('\$', '', wineprice)
            # now clean up $ and ,
            wineprice = wineprice.replace('$','').replace(',','')
            # debugging
            if verbose > 1:
                print ('BevMo' , ":", winename, ":", pricetype, ":", wineprice)
            # stop looking
            break
    #
    # final extracted wine data
    return { 'wine_store' : 'BevMo', 'wine_name' : winename, 'wine_price' : wineprice, 'wine_year' : '', 'label' : '' }

        
# create a search on the web
def bevmo_search( srchstring, bevmo_driver ):
    global verbose

    # Select the search box(es) and find if any are visbile - there can be more than one returned value
    search_boxes = bevmo_driver.find_elements_by_name('w')

    # debugging
    if len(search_boxes) == 0:
        print('bevmo_search:number of search_boxes:', len(search_boxes))
        print ('bevmo_search:exiting program due to error:no search boxes')
        saveBrowserContent( bevmo_driver, 'bevmo', 'bevmo_search' )
        exitWithError()

    # search the returned boxes to see if any are visible
    for index in range(len(search_boxes)):
        search_box = search_boxes[index]
        # check to see if this check box is displayed
        if search_boxes[index].is_displayed():
            # visible - so we are done
            # debugging
            if verbose > 1:
                print ('bevmo_search:search boxes:', index, 'is visible - search_box set to this value')
            break


    # first check to see that the search box is displayed - if not visible then click the bottom that makes it visible
    if not search_box.is_displayed():
        # debugging
        if verbose > 0:
            print ('bevmo_search:search box is not displayed - we want to click the button that displays it')
        # make the search box visible if it is not
        try:
            bevmo_driver.find_element_by_xpath('//*[@id="header-search-mobile"]/span').click()
        except  Exception as e:
            print ('bevmo_search://*[@id="search"]:no found:error:', str(e))
            print ('bevmo_search:type:', type(e))
            print ('bevmo_search:args:', e.args)
            print ('bevmo_search:exiting program due to error')
            saveBrowserContent( bevmo_driver, 'bevmo', 'bevmo_driver' )
            exitWithError()

    # debugging
    if verbose > 0:
        print ('bevmo_search:search for:', srchstring)

    # send in the string to this box and press RETURN
    search_box.clear()
    search_box.send_keys(srchstring)
    search_box.send_keys(Keys.RETURN)
    
    # create the array that we will add to
    found_wines = []

    # debugging
    if verbose > 0:
        print ('bevmo_search:pause 0.5 sec to allow page to fill in')
    # put a minor pause
    time.sleep(0.5)

    # first test - see if we got no results found - if so return the empty array
    try:
        if bevmo_driver.find_element_by_xpath('//*[@id="sli_noresult"]'):
            # debugging
            if verbose > 0:
                print ('bevmo_search:', srchstring, ':no results returned - refresh the page we are looking at')
            # update the website we are pointing at
            bevmo_driver.get('https://www.bevmo.com')
            # debugging
            if verbose > 0:
                print ('bevmo_search:page refreshed to:www.bevmo.com')
            # return a record that says we could not find the record
            return []
        else:
            # debugging
            if verbose > 1:
                print('bevmo_search:did not error when searching for sli_noresult:' + srchstring)
    except NoSuchElementException:
        # debugging
        if verbose > 1:
            print ('bevmo_search:sli_noresults does not exist - there must be results')
    except NoSuchWindowException as e:
        print ('bevmo_search:window unexpectantly closed - error:', str(e))
        exitWithError()
    except  Exception as e:
        print ('bevmo_search:sli_noresults - not found for (' + srchstring + ') - results were found (expected) - error:', str(e))
        print ('bevmo_search:type:', type(e))
        print ('bevmo_search:args:', e.args)
        print ('bevmo_search:exiting program due to error')
        saveBrowserContent( bevmo_driver, 'bevmo', 'bevmo_search')
        return []
        # exitWithError()

    # get results back and look for the thing we are looking for - the list of things we are going to process
    winelist = bevmo_driver.find_elements_by_class_name('product-info')
    
    # debugging
    print('bevmo_search:', srchstring, ':returned records:',  len(winelist))

    # now loop through the wines we found
    for index in range(len(winelist)):
        found_wines.append( bevmo_extract_wine_from_DOM(index,winelist) )

    # debugging
    if verbose > 5:
        print ('bevmo_search:found_wines:',found_wines)

    # update the website we are pointing at
    print ('bevmo_search:', srchstring, ':results found:refresh the page we are looking at')
    bevmo_driver.get('https://www.bevmo.com')

    # return the wines we found
    return found_wines

# function to create a selenium driver for bevmo and get past the store selector
def create_bevmo_selenium_driver(defaultstore):
    global verbose

    # debugging
    if verbose > 0:
        print('bevmo_driver:start:---------------------------------------------------')
        print('bevmo_driver:Start up webdriver.Chrome')
    
    # Using Chrome to access web
    driver = webdriver.Chrome()

    # debugging
    print ('bevmo_driver:Go to www.bevmo.com web page')
    
    # Open the website
    driver.get('https://www.bevmo.com')

    # ok - need to figure this out - but we must wait
    timewait = 7
    print ('bevmo_driver:sleep for ' + str(timewait) + ' seconds to allow the storeselect to pop up')
    time.sleep(timewait)
    
    # test to see if we have store selection dialogue here
    loopcnt = 1
    maxloopcnt = 6
    popupfound = 0
    storeset = 0
    oldxpathstr = '//*[@id="storeselect-popup"]/div[1]/img'
    xpathstr = '//*[@id="storeselect-popup"]/div[2]/fieldset/ol/li[1]/div/div/select'
    while loopcnt < maxloopcnt and not popupfound:
        # put in a try/catch loop - to deal with the case where a page is not returned
        try:
            # try to get the element
            popupfound = driver.find_element_by_xpath(xpathstr)
            # found it - set the loop count to max loop count
            loopcnt = maxloopcnt
        except:
            # did not find it - set flag and increment loop count
            popupfound = 0
            loopcnt += 1
            # display message and sleep
            print ('bevmo_driver:did not find the storeselect-popup - waiting 5 seconds')
            time.sleep(5)

    # check to see if we found the popup
    if not popupfound:
        # try to look for the other things
        try:
            storeset = driver.find_element_by_xpath('//*[@id="selected-store"]')
            # found so return it
            return driver
        except:
            pass

        # exit this driver
        driver.quit()
        # message to user
        print('bevmo_drive:could not find the page - disabling bevmo site')
        # return value to not use this website
        return None
            
    # print out that we found it
    print ('bevmo_driver:found the storeselect-popup')
        
    # see if the icon is visibile - if true we need to process this screen
    if driver.find_element_by_xpath(xpathstr).is_displayed():
        # debugging
        print ('bevmo_driver:need to fill out the store select popup with store: ', defaultstore)
        # set the store to the defaultstore
        driver.find_element_by_xpath('//*[@id="storeselect-popup"]/div[2]/fieldset/ol/li[1]/div/div/select/option[contains(text(), "' + defaultstore + '")]').click()
        # checkbox for i am 21
        driver.find_element_by_xpath('//*[@id="storeselect-popup"]/div[2]/fieldset/ol/li[4]/input').click()
        # click the select button
        driver.find_element_by_xpath('//*[@id="storeselect-select"]/span/span').click()
    else:
        # debugging
        print ('bevmo_driver:Store select popup is not displayed')

    # debugging
    if verbose > 0:
        print('bevmo_driver:complete:---------------------------------------------------')
    
    # return the driver
    return driver


# --------------------------------------------------------------------------

#### TOTALWINE ####


# function used to extract the data from the DOM that was returned
def totalwine_extract_wine_from_DOM(index,titlelist,pricelist,availlist,sizelist):
    
    # extract the values
    winename = titlelist[index].text 
    wineprice = pricelist[index].text

    # add size if size is NOT 750ml
    if sizelist[index].text != '750ml':
        winename += ' (' + sizelist[index].text + ')'
        
    # regex the price field to match our expections
    match = re.search('\$\s*(.*)$',wineprice)
    if match:
        wineprice = match.group(1)

    # now clean up $ and ,
    wineprice = wineprice.replace('$','').replace(',','')
    
    # return the dictionary
    return { 'wine_store' : 'TotalCA', 'wine_name' : winename, 'wine_price' : wineprice, 'wine_year' : '', 'label' : '' }


# Search for the wine
def totalwine_search( srchstring, totalwine_driver ):
    global verbose

    # create the array that we will add to
    found_wines = []

    # debugging
    print('totalwine_search:go to search page:www.totalwine.com')

    # force the page to start at the top of the page
    totalwine_driver.get('https://www.totalwine.com/')

    # debugging
    print('totalwine_search:find the search_box')

    # Select the search box(es) and find if any are visbile - there can be more than one returned value
    try:
        search_box = totalwine_driver.find_element_by_xpath('//*[@id="header-search-text"]')
        print ('totalwine_search:search box:header-search-text')
    except Exception as e:
        # try a different way
        try:
            search_box = totalwine_driver.find_element_by_xpath('//*[@id="at_searchProducts"]')
            print ('totalwine_search:search box:at_searchProducts')
        except Exception as e:
            print('totalwine_search:could not find search box after both lookups')
            saveBrowserContent( totalwine_driver, 'totalwine', 'totalwine_search' )
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

    # sleep to give page time to fill in
    print('totalwine_search:pause 0.5 sec to allow the page to fill in')
    time.sleep(0.5)
    
    # test to see the result count we got back
    returned_recs = None
    loopcnt = 0
    while returned_recs == None:
        try:
            returned_recs = totalwine_driver.find_element_by_id('anProdCount').get_attribute('value')
        except NoSuchElementException:
            # failed to find this attribute in the DOM
            try:
                # message to the user and then look for alternate attribute
                print('totalwine_search:exception on search for anProdCount:NoSuchElementException')
                print('totalwine_search:now search for listCount')
                returned_recs = totalwine_driver.find_element_by_id('listCount').get_attribute('value')
            except  Exception as f:
                # did not find alternate attribute - now we have problem
                print('totalwine_search:exception on search for listCount:', str(f))
                print('totalwine_search:pause 0.5 sec (again) to allow the page to fill in')
                time.sleep(0.5)
                loopcnt += 1
        #except TimeoutException as e:
        #    print('totalwine_search:browser timeout error - exit program - error message:', str(e))
        #    exitWithError()
        except  Exception as e:
            print('totalwine_search:exception on search for anProdCount:error-string:', str(e))
            time.sleep(0.5)
            loopcnt += 1

        # check to see if we have looped to many times
        if loopcnt > 10:
            print('totalwine_search:looped too many times - exiting program')
            exitWithError()

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
    titlelist = totalwine_driver.find_elements_by_class_name('plp-product-title')
    availlist = totalwine_driver.find_elements_by_class_name('plp-product-buy-limited')
    sizelist  = totalwine_driver.find_elements_by_class_name('plp-product-qty')
    pricelist = totalwine_driver.find_elements_by_class_name('price')

    # debugging
    if False:
        print ('titlelist-len:', len(titlelist))
        print ('availlist-len:', len(availlist))
        print ('sizelist-len:', len(sizelist))
        print ('pricelist-len:', len(pricelist))

    # message we have a problem
    if len(titlelist) != len(pricelist):
        print('totalwine_search:price and name lists different length:',srchstring,':len(wine):',len(titlelist),':len(price):',len(pricelist))

    
    # now loop through the wines we found
    for index in range(len(pricelist)):
        # we don't grab records where they are out of stock
        if availlist[index] != "This item is out of stock":
            # this is not out of stock
            found_wines.append( totalwine_extract_wine_from_DOM(index,titlelist,pricelist,availlist,sizelist) )
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
    driver = webdriver.Chrome()

    # debugging
    print ('totalwine_driver:Go to www.totalwine.com web page')
    
    # Open the website
    driver.get('https://www.totalwine.com')

    # sleep to allow the dialogue to come up
    print ('totalwine_driver:sleep 1 to allow popup to appear')
    time.sleep(1)

    # check for the button being visible
    if driver.find_element_by_xpath('//*[@id="btnYes"]'):
        print ('totalwine_driver:found the yes button')
        if driver.find_element_by_xpath('//*[@id="btnYes"]').is_displayed():
            print ('totalwine_driver:button is visible-click to say yes')
            driver.find_element_by_xpath('//*[@id="btnYes"]').click()

    # check to see if we are set to the store of interest (don't pass default - we want a blank if we don't find this)
    store_name = totalwine_driver_get_store(driver)

    # debugging
    print ('totalwine_driver:current store_name:', store_name)

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
    store_search_box = driver.find_element_by_xpath('//*[@id="storelocator-query"]')
    print('totalwine_driver_set_store:search for default store:', defaultstore)

    # now send in the keys
    store_search_box.send_keys(defaultstore)
    store_search_box.send_keys(Keys.RETURN)

    # check to see if this now has selected this as our store

    # now we need to select the store that returns
    select_store = driver.find_element_by_xpath('//*[@id="shopThisStore"]')
    print('totalwine_driver_set_store:find and click select this store button:', select_store.get_attribute('name'))
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

# function to create a selenium driver for wineclub and get past popup
def create_wineclub_selenium_driver(defaultzip):
    global verbose

    # debugging
    if verbose > 0:
        print('wineclub_driver:start:---------------------------------------------------')
        print ("wineclub:Start up webdriver.Chrome")
    
    # Using Chrome to access web
    driver = webdriver.Chrome()

    # debugging
    print ('wineclub_driver:Go to theoriginalwineclub.com/wine.html web page')
    
    # Open the website
    driver.get('https://theoriginalwineclub.com/wine.html')

    # try to get the search box
    cnt=10
    found_search_box = False
    while(cnt):
        try:
            search_box = driver.find_element_by_xpath('//*[@id="search"]')
        except  Exception as e:
            # did not find the search box
            print('wineclub_driver:waiting on search box (wait 1 second):', cnt)
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
def hitime_extract_wine_from_DOM(index,titlelist,pricelist):
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

        # debugging
        if verbose > 5:
            print('pricelistraw:', pricelistraw)
            print('pricelistreg:', pricelistreg)

        # pull out the entry of interest
        if len(pricelistraw):
            found_wines.append( hitime_extract_wine_from_DOM(0,titlelist,pricelistraw) )
        else:
            found_wines.append( hitime_extract_wine_from_DOM(0,titlelist,pricelistreg) )


    # debugging
    if verbose > 5:
        print ('hitime_search:found_wines:', found_wines)

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
    driver = webdriver.Chrome()

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
    driver = webdriver.Chrome()

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
                print('pavillions_find_search_box_by_class_name:ecomm-search:found:', counter)
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
    driver = webdriver.Chrome()

    # debugging
    print ('pavillions_driver:Go to shop.pavillions.com web page')
    
    # Open the website
    driver.get('https://shop.pavilions.com/home.html')

    
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
            
            # pause to give time for the search page to show
            timewait = 2
            print ('pavillions_driver:sleep for ' + str(timewait) + ' seconds to allow the search to pop up')
            time.sleep(timewait)
            
        else:
            # debugging
            print ('pavillions_driver:No zipcode to enter')
    except  Exception as e:
        print ('pavillions_driver:zipcode - not found for (' + defaultzip + ') - results were found - error:', str(e))

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

# routine use by email parser to grab the results for one wine
def get_wines_from_stores( srchstring_list, storelist, debug=False ):
    global verbose


    # create the bevmo selenium driver
    if 'bevmo' in storelist:
        bevmo_driver = create_bevmo_selenium_driver('Ladera Ranch')
        # if we did not get a valid driver - then we are not using this store.
        if bevmo_driver == None:  storelist.remove('bevmo')
    if 'pavillions' in storelist:
        pavillions_driver = create_pavillions_selenium_driver('92688')
    if 'wineclub' in storelist:
        wineclub_driver = create_wineclub_selenium_driver('92688')
    if 'hitime' in storelist:
        hitime_driver = create_hitime_selenium_driver('92688')
    if 'totalwine' in storelist:
        totalwine_driver = create_totalwine_selenium_driver('Laguna Hills')
        # if we did not get a valid driver - then we are not using this store.
        if totalwine_driver == None:  storelist.remove('totalwine')
    if 'wally' in storelist:
        wally_driver = create_wally_selenium_driver('')
        if wally_driver == None:  storelist.remove('wally')
               
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
    
    # dump out what we have done here
    if test:
        print ('---------------TEST FLAG ENABLED---------------------------')


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
    ]


    # uncomment this line if you want to limit the number of stores you are working
    #storelist = ['wally']
    #storelist = ['hitime']
    #storelist = ['wineclub']
    #storelist = ['pavillions']
    if test:
        # specified in the code
        storelist = ['pavillions']
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

    # if not user defined - generate the list if we don't have one predefined
    if srchstring_list == None:
        print('wineselenium.py:load list of wines from:',wineinputfile)
        srchstring_list = get_winelist_from_file( wineinputfile )
        remove_already_processed_wines( wineoutfile, srchstring_list )

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
        bevmo_driver = create_bevmo_selenium_driver('Ladera Ranch')
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

# eof
