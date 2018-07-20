from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException

import time
import re
import datetime
import sys

# appversion
appversion = '1.06'

# global variable - rundate set at strat
datefmt = '%m/%d/%Y'
rundate = datetime.datetime.now().strftime(datefmt)
store_wine_lookup = {}
wineoutfile = 'wineselenium.csv'
wineinputfile = 'getwines.bat'
winexlatfile = 'wine_xlat.csv'
verbose=1

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
def remove_already_processed_wines( winefile, searchlist ):
    # create the hash that captures what we have seen and not seen already
    seen_wines = []

    # put try loop in to deal with case when file does not exist
    try:
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
        if verbose > 0:
            print('remove_already_processed_wines:', winefile, ':does not exist-no stores removed from processing list')
        
    # return the pruned list
    return searchlist

# read in the translation file from store/wine to store/wine with vintage
def read_wine_xlat_file( getwines_file ):
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
                    if verbose > 0:
                        print('read_wine_xlat_file:',elem[0],':',elem[1],' mapping changed from (', store_wine_lookup[elem[0]][elem[1]], ') to (', elem[2], ')')
                # set the value no matter what
                store_wine_lookup[elem[0]][elem[1]] = elem[2]
            
    # return
    return store_wine_lookup


# now convert a wine name to appropriate translatoin
def xlat_wine_name( store_wine_lookup, store, wine ):
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



# -----------------------------------------------------------------------

#### BEVMO ####

# function used to extract the data from the DOM that was returned
def bevmo_extract_wine_from_DOM(index,winelist):
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
            # debugging
            if verbose > 1:
                print ('BevMo' , ":", winename, ":", pricetype, ":", wineprice)
            # stop looking
            break
    #
    # final extracted wine data
    return { 'wine_store' : 'BevMo', 'wine_name' : winename, 'wine_price' : wineprice }

        
# create a search on the web
def bevmo_search( srchsring, bevmo_driver ):
    # Select the search box(es) and find if any are visbile - there can be more than one returned value
    search_boxes = bevmo_driver.find_elements_by_name('w')

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
        bevmo_driver.find_element_by_xpath('//*[@id="header-search-mobile"]/span').click()

    # debugging
    if verbose > 0:
        print ('bevmo_search:search for:', srchstring)

    # send in the string to this box and press RETURN
    search_box.clear()
    search_box.send_keys(srchstring)
    search_box.send_keys(Keys.RETURN)
    
    # create the array that we will add to
    found_wines = []

    # put a minor pause
    if verbose > 0:
        print ('bevmo_search:pause 0.5 sec to allow page to fill in')
    time.sleep(0.5)

    # first test - see if we got no results found - if so return the empty array
    try:
        if bevmo_driver.find_element_by_xpath('//*[@id="sli_noresult"]'):
            # debugging
            if verbose > 1:
                print ('bevmo_search:', srchstring, ':no results returned - refresh the page we are looking at')
            # update the website we are pointing at
            bevmo_driver.get('https://www.bevmo.com')
            # return a record that says we could not find the record
            return [{ 'wine_store' : 'BevMo', 'wine_name' : srchstring + ' - no results found', 'wine_price' : 0 }]
        else:
            # debugging
            if verbose > 1:
                print('bevmo_search:did not error when searching for sli_noresult:' + srchstring)
    except NoSuchElementException:
        if verbose > 1:
            print ('bevmo_search:sli_noresults does not exist - there must be results')
    except  Exception as e:
        print ('bevmo_search:sli_noresults - not found for (' + srchstring + ') - results were found (expected) - error:', str(e))
        print ('bevmo_search:type:', type(e))
        print ('bevmo_search:args:', e.args)


    # get results back and look for the thing we are looking for - the list of things we are going to process
    winelist = bevmo_driver.find_elements_by_class_name('product-info')
    
    # debugging
    print('bevmo_search:returned records:',  len(winelist))

    # now loop through the wines we found
    for index in range(len(winelist)):
        found_wines.append( bevmo_extract_wine_from_DOM(index,winelist) )

    # debugging
    if verbose > 5:
        print ('bevmo_search:found_wines:',found_wines)

    # return the wines we found
    return found_wines

# function to create a selenium driver for bevmo and get past the store selector
def create_bevmo_selenium_driver(defaultstore):
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
    while not driver.find_element_by_xpath('//*[@id="storeselect-popup"]/div[1]/img'):
        print ('bevmo_driver:did not find the storeselect-popup - waiting 5 seconds')
        time.sleep(5)
        
    # print out that we found it
    print ('bevmo_driver:found the storeselect-popup')
        
    # see if the icon is visibile - if true we need to process this screen
    if driver.find_element_by_xpath('//*[@id="storeselect-popup"]/div[1]/img').is_displayed():
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
    
    # return the dictionary
    return { 'wine_store' : 'TotalCA', 'wine_name' : winename, 'wine_price' : wineprice }


# Search for the wine
def totalwine_search( srchsring, totalwine_driver ):
    # Select the search box(es) and find if any are visbile - there can be more than one returned value
    search_box = totalwine_driver.find_element_by_xpath('//*[@id="header-search-text"]')
    
    # first check to see that the search box is displayed - if not visible then click the bottom that makes it visible
    if not search_box.is_displayed():
        # debugging
        print ('totalwine_search:search box is not displayed - we want to click the button that displays it')
        # make the search box visible if it is not
        totalwine_driver.find_element_by_xpath('//*[@id="header-search-mobile"]/span').click()

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
            except  Exception as e:
                # did not find alternate attribute - now we have problem
                print('totalwine_search:exception on search for listCount:', str(e))
                print('totalwine_search:pause 0.5 sec (again) to allow the page to fill in')
                time.sleep(0.5)
                loopcnt += 1
        except  Exception as e:
            print('totalwine_search:exception on search for anProdCount:error-string:', str(e))
            time.sleep(0.5)
            loopcnt += 1

        # check to see if we have looped to many times
        if loopcnt > 10:
            print('totalwine_search:looped too many times - exiting program')
            sys.exit()

    # check to see if we got no results
    if returned_recs == 0:
        print('totalwine_search:', srchstring, ':no results returned - refresh the page we are looking at')
        # update the website we are pointing at
        totalwine_driver.get('https://www.totalwine.com')
        # return a record that says we could not find a record
        return [{ 'wine_store' : 'TotalCA', 'wine_name' : srchstring + ' - no results found', 'wine_price' : 0 }]        

    # debugging
    print('totalwine_search:returned records:', returned_recs)
    
    # create the array that we will add to
    found_wines = []

    # get results back and look for the thing we are looking for - the list of things we are going to process
    titlelist = totalwine_driver.find_elements_by_class_name('plp-product-title')
    availlist = totalwine_driver.find_elements_by_class_name('plp-product-buy-limited')
    sizelist  = totalwine_driver.find_elements_by_class_name('plp-product-qty')
    pricelist = totalwine_driver.find_elements_by_class_name('price')

    # debugging
    # print ('pricelist:', pricelist)

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

# function to create a selenium driver for bevmo and get past the store selector
def create_totalwine_selenium_driver(defaultstore):
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

    # check to see if we are set to the store of interest
    store = driver.find_elements_by_class_name('anGlobalStore')
    store_name = store[0].get_attribute('innerText')
    
    # debugging
    print ('totalwine_driver:store_name:', store_name)
    
    # test to see if store matches current store
    if not re.search(defaultstore, store_name):
        # debugging
        print ('totalwine_driver:store not set to:', defaultstore)
        # now change the store we are working with
        driver.get('https://www.totalwine.com/store-finder')
        # search for the field to enter data into
        store_search_box = driver.find_element_by_xpath('//*[@id="storelocator-query"]')
        # now send in the keys
        store_search_box.send_keys(defaultstore)
        store_search_box.send_keys(Keys.RETURN)
    else:
        print('totalwine_driver:store set to default')
            
    # debugging
    print('totalwine_driver:complete:---------------------------------------------------')
    
    # return the driver
    return driver


# --------------------------------------------------------------------------

#### WINECLUB ####


# function used to extract the data from the DOM that was returned
def wineclub_extract_wine_from_DOM(index,titlelist,pricelist):
    
    # extract the values
    winename = titlelist[index].text
    wineprice = pricelist[index].text
    
    # regex the price field to match our expections
    match = re.search('\$(.*)$',wineprice)
    if match:
        wineprice = match.group(1)
    
    # return the dictionary
    return { 'wine_store' : 'WineClub', 'wine_name' : winename, 'wine_price' : wineprice }


# Search for the wine
def wineclub_search( srchsring, wineclub_driver ):
    # Select the search box(es) and find if any are visbile - there can be more than one returned value
    search_box = wineclub_driver.find_element_by_xpath('//*[@id="search"]')
    
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
    print('wineclub_search:returned records:',  len(pricelist))
    
    # now loop through the wines we found
    for index in range(len(pricelist)):
        found_wines.append( wineclub_extract_wine_from_DOM(index,titlelist,pricelist) )

    # debugging
    if verbose > 5:
        print ('wineclub_search:found_wines:', found_wines)

    # return the wines we found
    return found_wines

# function to create a selenium driver for bevmo and get past the store selector
def create_wineclub_selenium_driver(defaultzip):
    # debugging
    if verbose > 0:
        print('wineclub_driver:start:---------------------------------------------------')
        print ("Start up webdriver.Chrome")
    
    # Using Chrome to access web
    driver = webdriver.Chrome()

    # debugging
    print ('wineclub_driver:Go to theoriginalwineclub.com web page')
    
    # Open the website
    driver.get('https://theoriginalwineclub.com')

    # sleep to allow the dialogue to come up
    print ('wineclub_driver:sleep 1 to allow popup to appear')
    time.sleep(1)

    # check for the button being visible
    if driver.find_element_by_class_name("ctct-popup-close"):
        print ('wineclub_driver:found the close button')
        print ('wineclub_driver:give 0.5 seconds for button to be visible')
        time.sleep(0.5)
        if driver.find_element_by_class_name("ctct-popup-close").is_displayed():
            print ('wineclub_driver:button is visible-click to close')
            driver.find_element_by_class_name("ctct-popup-close").click()
        else:
            print('wineclub_driver:button is NOT visible')

    # debugging
    print('wineclub_driver:complete:---------------------------------------------------')
    

    # return the driver
    return driver


# --------------------------------------------------------------------------

#### HITIME ####

# check to see if we want to keep this price element
def hitimes_price_elem_include( msg, price ):
    
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
    
    # extract the values
    winename = titlelist[index].text
    wineprice = pricelist[index].text
   
    # regex the price field to match our expections
    match = re.search('\$(.*)$',wineprice)
    if match:
        wineprice = match.group(1)
    
    # return the dictionary
    return { 'wine_store' : 'HiTimes', 'wine_name' : winename, 'wine_price' : wineprice }


# Search for the wine
def hitime_search( srchsring, hitime_driver ):
    # Select the search box(es) and find if any are visbile - there can be more than one returned value
    search_box = hitime_driver.find_element_by_xpath('//*[@id="search"]')
    
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
            return [{ 'wine_store' : 'HiTimes', 'wine_name' : srchstring + ' - no results found', 'wine_price' : 0 }]            
        else:
            # debugging
            if verbose > 1:
                print('hitime_search:found-empty-catalog-results:len:', len(returned_results))

    except NoSuchElementException:
        print ('hitime_search:empty-catalog:object not found')
        
    # get results back and look for the thing we are looking for - the list of things we are going to process
    titlelist = hitime_driver.find_elements_by_class_name('product-name')
    pricelistraw = hitime_driver.find_elements_by_class_name('price')
    pricelistreg = hitime_driver.find_elements_by_class_name('regular-price')

    
    # we need to attempt to filter down this list
    index = 0
    for title in titlelist:
        # debugging
        if verbose > 5: 
            print_html_elem( 'hitimes_search:title', index, title )
        # increment the index
        index += 1

    # RAW filter out of this list any "old" price entries
    index = 0
    pricelistrawfiltered = []
    if len(pricelistraw) > len(titlelist):
        # not the same size - so filter down
        for price in pricelistraw:
            # debugging
            if verbose > 4:
                print_html_elem( 'hitimes_search:raw price', index, price )

            # increment the counter
            index += 1
            # determine if we are keeping this item
            if hitimes_price_elem_include( 'hitimes_search:reg:', price):
                # keep this price
                pricelistrawfiltered.append(price)

    # price is not greater than title list - see if they are the same - if they are - set it
    elif len(titlelist) == len(pricelistraw):
        # debugging
        if verbose > 0:
            print('hitime_search:price-raw-same-length-just-copy-over')
        pricelistrawfiltered = pricelistraw

    # REG filter out of this list any "old" price entries
    index = 0
    pricelistregfiltered = []
    if len(pricelistreg) > len(titlelist):
        # we need to attempt to filter down this list
        for price in pricelistreg:
            # debugging
            if verbose > 4:
                print_html_elem( 'hitimes_search:reg price', index, price )

            # increment the counter
            index += 1
            # determine if we are keeping this item
            if hitimes_price_elem_include( 'hitimes_search:reg:', price):
                # keep this price
                pricelistregfiltered.append(price)
    # price is not greater than title list - see if they are the same - if they are - set it
    elif len(titlelist) == len(pricelistreg):
        # debugging
        if verbose > 4:
            print('hitime_search:price-regular-same-length-just-copy-over')
        pricelistregfiltered = pricelistreg

    # debugging
    if verbose > 4:
        print('len titlelist:', len(titlelist))
        print('len pricelistraw:', len(pricelistraw))
        print('len pricelistreg:', len(pricelistreg))
        print('len pricelistrawfiltered:', len(pricelistrawfiltered))
        print('len pricelistregfiltered:', len(pricelistregfiltered))

    # debugging
    print('hitime_search:returned records:',  len(titlelist))

    # message we have a problem
    if len(titlelist) == len(pricelistrawfiltered):
        if verbose > 4:
            print('hitimes_search:pricelistrawfiltered')
        pricelist = pricelistrawfiltered
    elif len(titlelist) == 1 and len(pricelistrawfiltered) > 1:
        if verbose > 4:
            print('hitimes_search:pricelistrawfiltered:one-wine')
        pricelist = pricelistrawfiltered
    elif len(titlelist) == len(pricelistregfiltered):
        if verbose > 4:
            print('hitimes_search:pricelistregfiltered')
        pricelist = pricelistregfiltered
    else:
        print('hitime_search:price and name lists different length:',srchstring,':len(wine):',len(titlelist),':len(price):',len(pricelist))
        pricelist = pricelistrawfiltered

    # now loop through the wines we found
    for index in range(len(titlelist)):
        found_wines.append( hitime_extract_wine_from_DOM(index,titlelist,pricelist) )

    # debugging
    if verbose > 5:
        print ('hitime_search:found_wines:', found_wines)

    # return the wines we found
    return found_wines

# function to create a selenium driver for bevmo and get past the store selector
def create_hitime_selenium_driver(defaultzip):
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


    # debugging
    print('hitime_driver:complete:---------------------------------------------------')
    

    # return the driver
    return driver


# --------------------------------------------------------------------------

#### WALLY ####


# function used to extract the data from the DOM that was returned
def wally_extract_wine_from_DOM(index,titlelist,pricelist):
    
    # extract the values
    winename = titlelist[index].text
    wineprice = pricelist[index].text
    
    # regex the price field to match our expections
    match = re.search('\$(.*)$',wineprice)
    if match:
        wineprice = match.group(1)
    
    # return the dictionary
    return { 'wine_store' : 'Wally-LA', 'wine_name' : winename, 'wine_price' : wineprice }


# Search for the wine
def wally_search( srchsring, wally_driver ):
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

    # message we have a problem
    if len(titlelist) != len(pricelist):
        print('wally_search:price and name lists different length:',srchstring,':len(wine):',len(titlelist),':len(price):',len(pricelist))

    # debugging
    if verbose > 5:
        print ('wally_search:pricelist:', pricelist)

    # debugging
    print('wally_search:returned records:',  len(pricelist))
    
    # now loop through the wines we found
    for index in range(len(pricelist)):
        found_wines.append( wally_extract_wine_from_DOM(index,titlelist,pricelist) )

    # debugging
    if verbose > 5:
        print ('wally_search:found_wines:', found_wines)

    # return the wines we found
    return found_wines

# function to create a selenium driver for bevmo and get past the store selector
def create_wally_selenium_driver(defaultzip):
    # debugging
    if verbose > 0:
        print('wally_driver:start:---------------------------------------------------')
        print ('wally_driver:Start up webdriver.Chrome')
    
    # Using Chrome to access web
    driver = webdriver.Chrome()

    # debugging
    print ('wally_driver:Go to www.wallywine.com web page')
    
    # Open the website
    driver.get('https://www.wallywine.com')

    # debugging
    print('wally_driver:complete:---------------------------------------------------')
    

    # return the driver
    return driver


#### PAVILLIONS ####


# function used to extract the data from the DOM that was returned
def pavillions_extract_wine_from_DOM(index,titlelist,pricelist):
    
    # extract the values
    winename = titlelist[index].text
    wineprice = pricelist[index].text

    # regex the price field to match our expections
    match = re.search('\$(.*)$',wineprice)
    if match:
        wineprice = match.group(1)
    
    # return the dictionary
    return { 'wine_store' : 'Vons', 'wine_name' : winename, 'wine_price' : wineprice }


# Search for the wine
def pavillions_search( srchsring, pavillions_driver ):
    # Select the search box(es) and find if any are visbile - there can be more than one returned value
    search_box = pavillions_driver.find_element_by_xpath('//*[@id="ecomm-search"]')

    # first check to see that the search box is displayed - if not visible then click the bottom that makes it visible
    if not search_box.is_displayed():
        # debugging
        print ('pavillions_search:search box is not displayed - this is a problem - exit')
        sys.exit()

    # debugging
    print ('pavillions_search:search for:', srchstring, ' in wines')

    # send in the string to this box and press RETURN
    search_box.clear()
    search_box.send_keys(srchstring + ' in wines')
    search_box.send_keys(Keys.RETURN)
    
    # create the array that we will add to
    found_wines = []
    
    # first test - see if we got no results found - if so return the empty array
    try:
        # see if we got a result string back - errors out if we did not
        returned_result = pavillions_driver.find_element_by_xpath('//*[@id="searchNrResults"]')

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
            # update the website we are pointing at
            pavillions_driver.get('https://shop.pavilions.com/home.html')
            # return a record that says we could not find the record
            return [{ 'wine_store' : 'Vons', 'wine_name' : srchstring + ' - no results found', 'wine_price' : 0 }]
        else:
            # debugging
            print('pavillions_search:following found results:',  result_text)
    except  Exception as e:
        print ('pavillions_search:searchNrResults - not found for (' + srchstring + ') - result were found - error:', str(e))
        print ('pavillions_search:type:', type(e))
        print ('pavillions_search:args:', e.args)
        print ('pavillions_search:exit and debug why we did not get back searchNrResults')
        sys.exit()
        time.sleep(30)

    # get results back and look for the thing we are looking for - the list of things we are going to process
    titlelist = pavillions_driver.find_elements_by_class_name('product-title')
    pricelist = pavillions_driver.find_elements_by_class_name('product-price')

    # message we have a problem
    if len(titlelist) != len(pricelist):
        print('pavillions_search:price and name lists different length:',srchstring,':len(wine):',len(titlelist),':len(price):',len(pricelist))

    # debugging
    if verbose > 5:
        print ('pavillions_search:pricelist:', pricelist)
    
    # now loop through the wines we found
    for index in range(len(pricelist)):
        found_wines.append( pavillions_extract_wine_from_DOM(index,titlelist,pricelist) )

    # debugging
    if verbose > 5:
        print ('pavillions_search:found_wines:', found_wines)

    # return the wines we found
    return found_wines

# function to create a selenium driver for bevmo and get past the store selector
def create_pavillions_selenium_driver(defaultzip):
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

    
    # check to see if the zip code is selectable
    try:
        # see if the zipcode field is here
        if driver.find_element_by_xpath('//*[@id="zipcode"]'):
            # debugging
            print ('pavillions_driver:need to fill out the zipcode: ', defaultzip)

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
        print ('pavillions_driver:zipcode - not found for (' + srchstring + ') - results were found - error:', str(e))

    # debugging
    print('pavillions_driver:complete:---------------------------------------------------')
    
    # return the driver
    return driver


# ---------------------------------------------------------------------------

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

# srchstring - set at None - then we will look up the information from the file
srchstring_list = None

# uncommnet a line below if you want define the wines you are checking for
#srchstring_list = ['attune','groth','beringer','hewitt','crawford','foley']
#srchstring_list = ['groth']
#srchstring_list = ['foley']
#srchstring_list = ['macallan']
#srchstring_list = ['hewitt']
#srchstring_list = ['silver oak']
#srchstring_list = ['macallan']
#srchstring_list = ['attune']
#srchstring_list = ['richard']
#srchstring_list = ['arista','richard','richard cognac']

# if not user defined - generate the list if we don't have one predefined
if srchstring_list == None:
    print('wine.py:load list of wines from:',wineinputfile)
    srchstring_list = get_winelist_from_file( wineinputfile )
    remove_already_processed_wines( wineoutfile, srchstring_list )

# load in xlat file in to a global variable
store_wine_lookup = read_wine_xlat_file( winexlatfile )

# create the bevmo selenium driver
if 'bevmo' in storelist:
    bevmo_driver = create_bevmo_selenium_driver('Ladera Ranch')
if 'pavillions' in storelist:
    pavillions_driver = create_pavillions_selenium_driver('92688')
if 'wineclub' in storelist:
    wineclub_driver = create_wineclub_selenium_driver('92688')
if 'hitime' in storelist:
    hitime_driver = create_hitime_selenium_driver('92688')
if 'totalwine' in storelist:
    totalwine_driver = create_totalwine_selenium_driver('Laguna Hills')
if 'wally' in storelist:
    wally_driver = create_wally_selenium_driver('')
               
# dump out what we have done here
if verbose > 0:
    print ('------------------------------------------')
    print ('wine.py:version:',appversion)
    print ('wine.py:srchstring_list:', srchstring_list)
    print ('wine.py:storelist:', storelist)
    print ('------------------------------------------')
    
# step through the list
for srchstring in srchstring_list:
    # create the list of records for each search string
    found_wines = []
    # find the wines for this search string
    if 'bevmo' in storelist:
        found_wines.extend( bevmo_search( srchstring, bevmo_driver ) )
    if 'pavillions' in storelist:
        found_wines.extend( pavillions_search( srchstring, pavillions_driver ) )
    if 'wineclub' in storelist:
        found_wines.extend( wineclub_search( srchstring, wineclub_driver ) )
    if 'totalwine' in storelist:
        found_wines.extend( totalwine_search( srchstring, totalwine_driver ) )
    if 'hitime' in storelist:
        found_wines.extend( hitime_search( srchstring, hitime_driver ) )
    if 'wally' in storelist:
        found_wines.extend( wally_search( srchstring, wally_driver ) )
    # debugging
    print ('wine.py:', srchstring, ' count of wines found:', len(found_wines))
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

exit()

# eof
