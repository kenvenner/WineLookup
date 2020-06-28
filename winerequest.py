'''
@author:   Ken Venner
@contact:  ken@venerllc.com
@version:  1.19

Using python requests - screen scrape wine websites to draw
down wine pricing and availiability information

'''

import kvutil
import kvlogger


import wineselenium

import datetime
import re
import requests
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

# module global variables
glb_last_line_check=-1       # global variable to store the line number we just called
glb_last_line_count=0        # global variable to count number of times we called this line
glb_last_line_max  =3

# cause print statements that are not debugging statements to print out
pmsg          = False

# application variables
optiondictconfig = {
    'AppVersion' : {
        'value' : '1.19',
        'description' : 'defines the version number for the app',
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
    'test' : {
        'value' : False,
        'type'  : 'bool',
        'description' : 'defines if we are running in test mode',
    },
    'srchstring' : {
        'value'  : None,
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
        'value' : 'winerequest.csv',
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

# capture the store definitions
def store_definitions():
    return {
        'binnys' : {
            'search_args' : {
                'url_fmt'      : 'https://www.binnys.com/catalogsearch/result/?q=%s',
                're_noresults' : [ re.compile('0 Results for "noresults"') ],
            },
            'splitter_args'    : {},
            'parser_args' : {
                're_name_start'  : re.compile('class="product-item-link"', re.IGNORECASE),
                're_name_end'    : re.compile('\/body>', re.IGNORECASE),
                're_name_skip'   : 2,
                're_names'       : [ re.compile('\s*(.*\S)\s*<') ],
                're_size_start'  : re.compile('class="size-pack-attr"'),
                're_size_skip'   : 1,
                're_sizes'       : [ re.compile('\s*(.*\S)\s*<') ],
                're_size_end'    : re.compile('<span class="price"'),
                're_price_start' : re.compile('<span class="price">([^<]*)<\/span>', re.IGNORECASE),
                're_price_end'   : re.compile('Add to Cart'),
                'label'          : 'Binnys',
            },
        },
        'hiddenvine' : {
            'search_args' : {
                'url_fmt'      : 'http://www.ahiddenvine.com/search.asp?search=SEARCH&keyword=%s',
                're_noresults' : [ re.compile('0 Records Found') ],
            },
            'splitter_args' : {},
            'parser_args' : {
                're_name_start'  : re.compile("<td><a href='[^']*'>([^<]*)<", re.IGNORECASE),
                're_name_end'    : re.compile('\/body>', re.IGNORECASE),
                're_price_start' : re.compile('<span class="price">([^<]*)<\/span>', re.IGNORECASE),
                're_price_end'   : re.compile('Add to Cart'),
                'label'          : 'Hidden',
            },
        },
        'winex' : {
            'search_args' : {
                'url_fmt'      : 'https://www.winex.com/catalogsearch/result/?q=%s',
#                'payload'      : { 'keywords' :  'no-value-substitued' },
#                'payload_fld'  : 'keywords',
                're_noresults' : [ re.compile('Your search returned no results.') ],
            },
            'splitter_args' : {
                're_splitters' : [ (re.compile('<td'), '\n<td'), ]
            },
            'parser_args' : {
                'label'         : 'WineEx',
                're_name_start' : re.compile('<div class="product_items_list_title"><a href="[^"]*">([^<]*)<', re.IGNORECASE),
                're_name_end'    : re.compile('\/body>', re.IGNORECASE),
                're_price_start': re.compile('<div class="listing_price">([^<]*)<', re.IGNORECASE),
            },
        },
        'napacab' : {
            'search_args' : {
                'url_fmt'      : 'http://www.napacabs.com/search.php?search_query=%s&section=product',
                're_noresults' : [ re.compile('No products match your search criteria', re.IGNORECASE) ],
            },
            'splitter_args' : {
                're_splitters' : [ (re.compile('<p'), '\n<p'), (re.compile('<li'), '\n<li'), (re.compile('<span'), '\n<span') ]
            },
            'parser_args' : {
                're_name_start'  : re.compile('class="card-title"', re.IGNORECASE),
                're_name_end'    : re.compile('\/body>', re.IGNORECASE),
                're_name_skip'   : 1,
                're_names'       : [ re.compile('">([^<]*)<') ],
                're_price_start' : re.compile('class="price price--withoutTax price--main"'),
                're_price_end'   : re.compile('\/body>', re.IGNORECASE),
                're_prices'      : [ re.compile('price">([^<]*)<'),
                                     re.compile('\s\$(\d*,?\d+\.\d\d)'),
                                     re.compile('\s\$(\d*,?\d+\..*)$'),
                                     re.compile('>\$(\d*,?\d+\.\d+)<') ],
                'label'          : 'NapaCab',
            },
        },
        'webwine' : {
            'search_args' : {
                'url_fmt'      : 'http://www.webwine.com/results',
                'payload'      : { 'term' :  'no-value-substitued' },
                'payload_fld'  : 'term',
                're_noresults' : [ re.compile('no matches were found', re.IGNORECASE) ],
            },
            'splitter_args' : {
                're_splitters' : [ (re.compile('<div class="itemResultsRow"'), '\n<div class="itemResultsRow"'), ]
            },
            'parser_args' : {
                're_start'       : re.compile('div class="results"', re.IGNORECASE),
                're_name_start'  : re.compile('class="itemTitle"', re.IGNORECASE),
                're_name_end'    : re.compile('\/body>', re.IGNORECASE),
                're_name_groups' : [1,2,3],
                're_names'       : [ re.compile('<span class="brand">([^<]*)<\/span>\s*<span class="title">([^<]*)<\/span>\s*<span class="vintageAge">(\d+)<\/span>') ],
                're_price_start' : re.compile('table class="priceTable"', re.IGNORECASE),
                're_price_end'   : re.compile('class="itemTitle"', re.IGNORECASE),
                're_prices'      : [ re.compile('<span class="priceRetail">\$(\d[^\.]*\.\d+)<', re.IGNORECASE),
                                     re.compile('class="priceSale">\$(\d[^\.]*\.\d+)<', re.IGNORECASE),
                                     re.compile('<span class="priceSale">On&nbsp;Sale\s*\$(\d[^\.]*\.\d+)<', re.IGNORECASE)],
                'label'          : 'Webwine',
            },
        },
        'wineconn' : {
            'search_args' : {
                'url_fmt'      : 'http://www.thewineconnection.com/search/search.php?imageField.x=0&imageField.y=0&searchtxt=%s',
                're_noresults' : [ re.compile('no results') ],
            },
            'splitter_args' : {
                're_splitters' : [ (re.compile('&nbsp;'), ' '), (re.compile('<br />\n'), ' '), (re.compile('</a><br>'), ' '), (re.compile('<td'), '\n<td') ]
            },
            'parser_args' : {
                're_name_start'  : re.compile('class="p_desc"\s?><a href="[^"]*">([^<]*)<', re.IGNORECASE),
                're_name_end'    : re.compile('\/body>', re.IGNORECASE),
                're_price_start' : re.compile('sale_price">\$([^<]*)<|reg_price">\$([^<]*)<', re.IGNORECASE),
                're_price_end'   : re.compile('class="p_desc"\s?><a href="[^"]*">([^<]*)<', re.IGNORECASE),
                're_prices'      : [ re.compile('sale_price">\$([^<]*)<', re.IGNORECASE),
                                     re.compile('reg_price">\$([^<]*)<', re.IGNORECASE) ],
                'label'          : 'WineConn',
            },
        },
        'lawineco' : {
            'search_args' : {
                'url_fmt'      : 'https://lawineco.com/advanced_search_result?search_in_description=1&keyword=%s',
                're_noresults' : [ re.compile('no product that matches') ],
            },
            'splitter_args' : {},
            'parser_args' : {
                're_name_start'  : re.compile('data-name="([^"]*)"', re.IGNORECASE),
                're_name_end'    : re.compile('\/body>', re.IGNORECASE),
                're_price_start' : re.compile('div class="price"', re.IGNORECASE),
                're_price_end'   : re.compile('data-name="([^"]*)"'),
                're_prices'      : [ re.compile('class="productSpecialPrice">\$([^<]*)<', re.IGNORECASE), re.compile('>\$([^<]*)<', re.IGNORECASE), ],
                'label'          : 'WineCo-LA',
            },
        },
        'johnpete' : {
            'search_args' : {
                'url_fmt'      : 'https://www.johnandpetes.com/component/virtuemart/?keyword=%s&limitstart=0&option=com_virtuemart&view=category&virtuemart_category_id=0',
                're_noresults' : [ re.compile('No result:') ],
                'UserAgent'    : 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:66.0) Gecko/20100101 Firefox/66.0', # 'MyAgent' + datetime.datetime.now().strftime('%Y%m%d'),
            },
            'splitter_args' : {},
            'parser_args' : {
                're_name_start'  : re.compile('"h-pr-title"><a[^>]*>([^<]*)', re.IGNORECASE),
                're_name_end'    : re.compile('\/body>', re.IGNORECASE),
                're_names'       : [ re.compile('<a[^>]*>([^<]*)<\/a', re.IGNORECASE), re.compile('<a[^>]*>([^<]*)$', re.IGNORECASE), ],
                're_price_start' : re.compile('span class="PricesalesPrice">', re.IGNORECASE),
                're_price_end'   : re.compile('"h-pr-title">', re.IGNORECASE),
                're_prices'      : [ re.compile('\$(\d*\.\d*)'), ],
                'label'          : 'JohnPete',
            },
        },
        'wine2020' : { # - looks like this needs to be ported to selenium - not getting expected results back
            'search_args' : {
                'url_fmt'      : 'http://www.2020wines.com/catalogsearch/result/?q=%s',
                're_noresults' : [ re.compile('Your search returns no results', re.IGNORECASE) ],
            },
            'splitter_args' : {
                're_splitters' : [ (re.compile('\s*\$'), '\$'), ],
            },
            'parser_args' : {
                're_name_start'  : re.compile('class="product_name"><a href="[^>]*>([^<]*)<', re.IGNORECASE),
                're_name_end'    : re.compile('\/body>', re.IGNORECASE),
                're_names'       : [ re.compile('">([^<]+)<\/a>') ],
                're_price_start' : re.compile('class="price"', re.IGNORECASE),
                're_price_end'   : re.compile('class="product_name">', re.IGNORECASE),
                're_prices'      : [ re.compile('$(\d*\.\d*)') ],
                'label'          : '2020Wine-LA',
            },
        },
        'acwine' : {  #too much work and not enough value - not building out this solution
            'search_args' : {
                'url_fmt'      : 'https://www.accidentalwine.com/search?x=0&y=0&q=%s',
                're_noresults' : [ re.compile('No search results') ],
            },
            'splitter_args' : {},
            'parser_args' : {
                're_name_start'  : re.compile('<h3><a href="\/products', re.IGNORECASE),
                're_name_end'    : re.compile('\/body>', re.IGNORECASE),
                're_names'       : [ re.compile('title="">(.*)<\/a></h3>', re.IGNORECASE) ],
                're_price_start' : re.compile('', re.IGNORECASE),
                're_price_end'   : re.compile(''),
                're_prices'      : [ re.compile('', re.IGNORECASE),
                                     re.compile('', re.IGNORECASE),
                                     re.compile('', re.IGNORECASE),
                                     re.compile('', re.IGNORECASE)],
                'label'          : 'AC-LA',
            },
        },
        'klwine' : {
            'search_args' : {
                'url_fmt'      : 'https://www.klwines.com/Products?searchText=%s',
                're_noresults' : [ re.compile('returned 0 results') ],
            },
            'splitter_args' : {},
            'parser_args' : {
                're_name_start'  : re.compile('class="tf-product-header"', re.IGNORECASE),
                're_name_end'    : re.compile('\/body>', re.IGNORECASE),
                're_name_skip'   : 7,
                're_names'       : [ re.compile('\s*(\S.*)') ],
                're_price_start' : re.compile('class="tf-price"', re.IGNORECASE),
                're_price_end'   : re.compile('tf-product-header'),
                're_price_skip'  : 1,
                're_prices'      : [ re.compile('Price:[^\$]*\$([^<]*)<', re.IGNORECASE), ],
                'label'          : 'KLWine',
            },
        },
        'nhliquor' : {
            'search_args' : {
                'url_fmt'      : 'https://www.liquorandwineoutlets.com/products?search=%s',
                're_noresults' : [ re.compile('are no products that match your search') ],
            },
            'splitter_args' : {},
            'parser_args' : {
                're_name_start'  : re.compile('product_row_(\d+)', re.IGNORECASE),
                're_name_end'    : re.compile('\/body>', re.IGNORECASE),
                're_name_skip'   : 4,
                're_names'       : [ re.compile('<td><a href="[^"]*">([^<]*)<'), ],
                're_price_start' : re.compile('\$(\d+\.\d+)', re.IGNORECASE),
                're_price_end'   : re.compile('product_row_(\d+)'),
                #            're_prices'      : [ re.compile('', re.IGNORECASE),
                #                                 re.compile('', re.IGNORECASE),
                #                                 re.compile('', re.IGNORECASE),
                #                                 re.compile('', re.IGNORECASE)],
                'label'          : 'NHLiq',
            },
        },
        'rolf' : {
            'search_args' : {
                'url_fmt'      : 'https://ssl.spectrumwine.com/retail/wine.aspx?Keyword=%s',
                're_noresults' : [ re.compile('There were no retail items found') ],
            },
            'splitter_args' : {},
            'parser_args' : {
                're_name_start'  : re.compile('class="rgRow"|class="rgAltRow"', re.IGNORECASE),
                're_name_end'    : re.compile('\/body>', re.IGNORECASE),
                're_name_skip'   : 4,
                're_names'       : [ re.compile('<a href="[^"]*">([^<]*)<', re.IGNORECASE), ],
                're_price_start' : re.compile('Price:', re.IGNORECASE),
                're_price_end'   : re.compile('\/tr>'),
                're_prices'      : [ re.compile('\$([^<]*)<', re.IGNORECASE),],
                                     #re.compile('', re.IGNORECASE),
                                     #re.compile('', re.IGNORECASE),
                                     #re.compile('', re.IGNORECASE)],
                'label'          : 'Rolf',
            },
        },
        'winezap' : {   ## runs way to slow - not worth asking questions.
            'search_args' : {
                'url_fmt'      : 'http://www.winezap.com/search/searchResults.cfm?searchText=%s&bottlesize=750&countSearch=',
                're_noresults' : [ re.compile('0 retailer items found') ],
            },
            'splitter_args' : {},
            'parser_args' : {
                're_name_start'  : re.compile('click.cfm', re.IGNORECASE),
                're_name_end'    : re.compile('\/body>', re.IGNORECASE),
                're_names'       : [ re.compile('this\)"><b>([^<]*)<') ],
                're_price_start' : re.compile('>$(\d*\.\d+)<', re.IGNORECASE),
                're_price_end'   : re.compile(''),
                'label'          : 'WineZap',
            },
        },
        'zzTemplate' : { # (acwine custom)
            'search_args' : {
                'url_fmt'      : '',
                're_noresults' : [ re.compile('0 Records Found') ],
            },
            'splitter_args' : {},
            'parser_args' : {
                're_name_start'  : re.compile('', re.IGNORECASE),
                're_name_end'    : re.compile('\/body>', re.IGNORECASE),
                're_names'       : [ re.compile('') ],
                're_price_start' : re.compile('', re.IGNORECASE),
                're_price_end'   : re.compile(''),
                're_prices'      : [ re.compile('', re.IGNORECASE),
                                     re.compile('', re.IGNORECASE),
                                     re.compile('', re.IGNORECASE),
                                     re.compile('', re.IGNORECASE)],
                'label'          : '',
            },
        },
    }




# routine takes the list of wines to search for and list of stores to search and builds up the array of wines
def get_wines_from_stores( srchstring_list, storelist, wineoutfile=None, debug=False ):
    # grab the store defintions
    store_args = store_definitions()

    # create the list of records for each search string
    found_wines = []

    # debugging
    if debug: print('winerequest:get_wines_from_stores')
    logger.debug('srchstring_list:%s', srchstring_list)
    logger.debug('storelist:%s',storelist)

    # step through the search strings
    for srchstring in srchstring_list:
        # step through the store list
        winelist=[]
        for store in storelist:
            # debugging
            if debug: print('winerequest.py:get_wines_from_stores:store:',store)
            logger.debug('store:%s', store)
            try:
                # processing logic
                if store == 'nhliquor':
                    winelist.extend(nhliquor_wine_searcher( srchstring, debug=debug ))
                elif store == 'ken': # 'johnpete':
                    # this is not working right now
                    if pmsg: print('winerequest:get_wines_from_stores:', store, ':SKIPPING store - not working')
                    logger.info('SKIPPING store - not working:%s', store)
                elif store in store_args:
                    winelist.extend(generic_wine_searcher( srchstring, store, store_args, debug=debug ))
                else:
                    if pmsg: print('winerequest.py:get_wines_from_stores:store not in store_definition:SKIPPING')
                    logger.info('SKIPPING:store not in store_definition:%s', store)
                    break
            except Exception as e:
                if pmsg: print('winerequest:get_wines_from_stores:exception:', str(e))
                logger.error('store:%s:error:%s', store, str(e))
            
            # messaging on wines found
            if len(winelist)==1 and winelist[0] == wineselenium.returnNoWineFound( store ):
                if debug: print('winerequest.py:', store, ':', srchstring, ':returned records:', 0)
                logger.info('store:%s:returned records:%d', store, 0)
            else:
                if debug: print('winerequest.py:', store, ':', srchstring, ':returned records:', len(winelist))
                logger.info('store:%s:returned records:%d', store, len(winelist))

        # save this wine specific list into the overall list
        found_wines.extend(winelist)
        
        # for each wine - all stores - save to file
        if wineoutfile and winelist:
            logger.debug('saving list of wines to file:%s',wineoutfile)
            wineselenium.save_wines_to_file(wineoutfile, srchstring, winelist)


    # when done with all store/wine lookups return the results
    return found_wines



##################################################################################################
# search for a regex in an aref of strings
#
# search_re    - re.compile to search for
# file_aref    - list of lines to search
# ptr          - starting point in this list
# not_find_1st - re.compile that we should stop looking at and make a next step or None
# no_bottom    - flag when set, return ptr if we don't find the regex
#
def search_list_for(search_re, file_aref, ptr, not_find_1st_re=None, no_bottom=False, debug=False):

    # globals need to defined?
    global glb_last_line_check
    global glb_last_line_count
    global glb_last_line_max

    # Assume we will match, and reset if we don't
    match = 1;

    # define the list length
    list_len = len(file_aref)

    # capture the original pointer
    ptr_orig = ptr

    # check pointer counter to see if we are processing the same line again
    if ptr == glb_last_line_check:
        # we are processing the same line again

	# increment the counter, for the number of times we have run this line again
        glb_last_line_count += 1
	
	# check this to the max
        if glb_last_line_count > glb_last_line_max:
            if debug: print( "winerequest:search_list_for:Reprocessed the line [%s] more than [%s] times" % (ptr, glb_last_line_max) )
            if debug: print( "winerequest:search_list_for:Searching for [%s]" % search_re)
            if debug: print( 'winerequest:search_list_for:file_aref:', file_aref )
            logger.debug('Searching for:%s', search_re)
            logger.debug('Reprocessed the line:%d:more than:%d:times:return None', ptr, glb_last_line_max)
            return (0,0, None)

    else:
        # first time we see this lie
        glb_last_line_check = ptr
        glb_last_line_count = 0

    # define a displayable line number
    iptr = "%04d" % ptr

    # debugging
    if debug: print( "s%s:search for:%s" % (iptr,search_re) )
    logger.debug( 's%s:search for:%s',iptr,search_re )
    if not_find_1st_re:
        if debug: print( "n%s:not_first:%s" % (iptr,not_find_1st_re) )
        logger.debug( "n%s:not_first:%s", iptr,not_find_1st_re )

    
    # step through records until we find the string or end of file (make this an re.search or re.search)
    while not search_re.search(file_aref[ ptr ]):

	# debugging
        if debug: print( "s%s:%s" % (iptr, file_aref[ptr]) )
        logger.debug( "s%s:%s", iptr, file_aref[ptr] )
            
	# failed to find it if we have out run the array
        if ptr >= list_len:
            # debugging
            if debug: print( "f%s:FAILED-HIT-BOTTOM" % iptr )
            logger.debug( "f%s:FAILED-HIT-BOTTOM", iptr )
            
            # reset flags and pointers
            match = 0
            ptr   = 0

            # if the no_bottom flag is set, don't return to zero but back to where we started
            if no_bottom: ptr = ptr_orig
        
            # make it a string
            iptr  = "%04d" % ptr

            # debugging
            if debug: print( "r%s:%s" % (iptr, file_aref[ptr])  )
            logger.debug( "r%s:%s", iptr, file_aref[ptr]  )

            # we are done processing for now - send results back up
            break

	# check to see if we have matched the skip
        if not_find_1st_re:
            if not_find_1st_re.search(file_aref[ ptr ]):
                # this line is the list that we stop looking at
                # debugging
                if debug: print( "s%s:%s" % (iptr, file_aref[ptr]) )
                if debug: print( "f%s:FAILED-NOT-FIND-1ST" % (iptr) )
                logger.debug( "s%s:%s", iptr, file_aref[ptr]  )
                logger.debug( "f%s:FAILED-NOT-FIND-1ST", (iptr) )
                
                # set the pointers as we did not find the desire string
                match = 0;
                ptr   = ptr_orig;
		
                # make it a string
                iptr  = "%04d" % ptr

                # debugging
                if debug: print( "r%s:%s" % (iptr, file_aref[ptr])  )
                logger.debug( "r%s:%s", iptr, file_aref[ptr]  )

                # reset glb_last_line_count
                glb_last_line_count = 0;

                # we are done processing this loop for now
                break

	# next line
        ptr += 1
        
	# display version
        iptr = "%04d" % ptr
	
    #wend
    
    # debugging
    if debug: print( 'search_list_for:end of wend loop:match:', match  )
    logger.debug( 'end of wend loop:match:%s', match  )

    # check to see if we found what we were looking for
    if match:
        if debug: print( "m%s:%s" % (iptr, file_aref[ptr]) )
        logger.debug( "m%s:%s", iptr, file_aref[ptr] )
    else:
        if debug: print( "l%s:%s" % (iptr, file_aref[ptr]) )
        logger.debug( "l%s:%s", iptr, file_aref[ptr] )


    # reset glb_last_line_count, we found what we want
    glb_last_line_count = 0;

    # we must have found it, return the line number
    return (ptr, match, search_re.search( file_aref[ptr]))



# clean up a price field so it is pure numeric
def price_cleanup(price):
    newprice =  price.replace('$','').replace(',','').replace('>','')
    rePrice = re.compile('(\d*\.\d*)')
    m = rePrice.search(newprice)
    if m:
        return m.group(1)
    else:
        return newprice


# generic parser with regex values passed in
# inputs:  (re_* - are all re.compile() statements except where documented below)
#    file_list - list of strings that make up the file
#    label - the label to add to records as they are created
#    re_start - (opt) moves you to a starting area in the file that you can iterate on
#
#    re_name_start - finds the next wine name, and optionally extract out the name from the line (see re_names)
#    re_name_end - (opt) if you encounter this, stop looking for wine name
#    re_name_skip - (opt) NOT an re.compile - this is an INT - number of lines to move after you re_name_start find
#    re_name_multi - (opt) NOT an re.compile - this is True/False - when True - you look for name on multiple lines
#    re_name_groups - (opt) NOT an re.compile - this is an array that defines the order in which re.group(#) from re_name_start
#                      are concatenated to make wine_name
#                         - when this is set - re_names can NOT be set.
#    re_names - (opt) - list of re.compile statements - used to extract the name from the file line containing the name
#                if not populated we use re_name_start to extract out the name as group(1)
#
#    re_size_start (opt) - finds the size after finding the name
#    re_size_end - (opt) if you encounter this, stop looking for winesize
#    re_size_skip - (opt) NOT an re.compile - an INTEGER - number of lines to move after you find re_size_start
#    re_sizes - (opt) list of rec.compile statements used to extract the name from the fil eline containing the size
#
#    re_price_start - finds the price for that wine
#    re_price_end - (opt) stops looking if finds this first (usually set to re_name_start)
#    re_price_skip - (opt) NOT an re.compile - this is an INT - number of lines to move after you re_price_start find
#    re_prices - (opt) - list of re.compile statements - used to extract the price from the file line containing the name
#                if not populated we use re_price_start to extract out the price as group(1)
#
def generic_wine_parser( file_list, label, re_name_start, re_name_end=None, re_name_skip=None, re_name_multi=None, re_name_groups=None, re_names=None, re_size_start=None, re_size_skip=None, re_sizes=None, re_size_end=None, re_price_start=None, re_price_end=None, re_price_skip=None, re_start=None, re_prices=None, debug=False):

    # might need to add in logic to extract out the wine bottle size into this parser (2018-09-26) - done 2020-05-13
    
    i=0
    list_len = len(file_list)
    last_i = 0

    results = []
    
    #if we were given a start, then move through the file until we find that record
    if re_start:
        (i,match,found) = search_list_for( re_start, file_list, i, debug=debug )
        if match:
            last_i = i
        else:
            if pmsg: print('winerequest:generic_wine_parser:did not find requested starting area - terminating:', re_start)
            logger.warning('did not find requested starting area - terminating:%s', re_start)
            return []

    # debugging
    if debug: print('winerequest:generic_wine_parser:searching store:', label)
    logger.debug('searching store:%s', label)
    
    # loop through the lines in this file
    while i < list_len:
        # create the starting dict
        record = {
            'label' : label,
            'wine_store' : label,
            'wine_year'  : '',
        }
    

        ####  WINE NAME #####
        
        # search for the name
        (i,match,found) = search_list_for( re_name_start, file_list, i, re_name_end, debug=debug )

        # action if we did not find a match
        if not match:
            # debugging
            if not results:
                if debug:  print('winerequest:generic_wine_parser:did not find wine name')
                logger.debug('did not find wine name')
            break

        # capture the name line we just saw
        last_i = i
        
        # if set to skip lines then skip lines
        if re_name_skip:
            i += re_name_skip
            # debugging
            if debug: print('re_name_skip:', re_name_skip, ':moved line counter to:', i)
            logger.debug('re_name_skip:%d:moved line counter to:%d', re_name_skip, i)
            logger.debug('%d:%s', i, file_list[i])
            
            # check the counter
            if i >= list_len: continue

        # save this in the record
        if not re_names:
            # check to see if we read in multiple values
            if re_name_groups:
                # create the key in the dictionary and then fill in each of the pulled records
                record['wine_name'] = ''
                for grpnum in re_name_groups:
                    record['wine_name'] = record['wine_name'] + ' ' + found.group(grpnum)
            else:
                # just pull in the first one
                record['wine_name'] = found.group(1)
            # debugging
            if debug: print('i:', i, ':name:', record['wine_name'])
            logger.debug('i:%d:name:%s', i, record['wine_name'])
        else:
            # search through the list of comparisons to find a match
            for re_name in re_names:
                found = re_name.search( file_list[i] )
                if found:
                    # check to see if we read in multiple values
                    if re_name_groups:
                        # create the key in the dictionary and then fill in each of the pulled records
                        record['wine_name'] = ''
                        for grpnum in re_name_groups:
                            record['wine_name'] = record['wine_name'] + ' ' + found.group(grpnum)
                    else:
                        # just pull the first entry
                        record['wine_name'] = found.group(1)
                    # debugging
                    if debug: print('i:', i, ':name:', record['wine_name'], ':re_name:', re_name)
                    logger.debug('i:%d:name:%s:re_name:%s', i, record['wine_name'], re_name)
                    if debug: print('wine_name:', record['wine_name'])
                    logger.debug('wine_name:%s', record['wine_name'])
                    break
            # check to see we found a name, and if not skip this section
            if 'wine_name' not in record:
                # move to next line
                i += 1
                # debugging
                if debug: print('winerequest:generic_wine_parser:did not find a wine name - skipping and looking again at line:', i)
                logger.debug('did not find a wine name - skipping and looking again at line:%d', i)
                # continue the search
                continue

            # WINECONN #
            # this is wineconn logic and we might wnat to remove it - i think it creates undo complications
            # if the multi flag is set then we have additoinal logic - clean up and find more input
            if re_name_multi:
                # remove any <br> from this string
                record['wine_name'] = record['wine_name'].replace('<br>', ' ')
                # keep processing until we find the <
                while( record['wine_name'].find('<') == -1 ):
                    # get next line
                    i += 1
                    # debugging
                    if debug: print('i:', i, ':loading next line into name:', file_list[i])
                    logger.debug('i:%d:loading next line into name:', i, file_list[i])
                    # add this line (might want to trim the new line content)
                    record['wine_name'] = record['wine_name'] + ' ' + file_prt[i].replace('<br>', ' ')

                # and when done - remove the final <
                record['wine_name'] = record['wine_name'].replace('<', '')
            # WINECONN #
            
        # make sure the name is trimmed
        record['wine_name'] = record['wine_name'].strip()

        # extract the wine year from the name if it exists
        record['wine_year'] = _extract_year_from_name( record['wine_name'] )

        # move one line to then look for sign
        i += 1

        
        ### WINE SIZE ###
        if re_size_start:
            # search for the name
            (i,match,found) = search_list_for( re_size_start, file_list, i, re_size_end, debug=debug )

            # action if we did not find a match
            if not match:
                # debugging
                if not results:
                    if debug: print('winerequest:generic_wine_parser:did not find wine size')
                    logger.debug('did not find wine size')
                break

            # capture the name line we just saw
            last_i = i
        
            # if set to skip lines then skip lines
            if re_size_skip:
                i += re_size_skip
                # debugging
                if debug: print('re_size_skip:', re_size_skip, ':moved line counter to:', i)
                logger.debug('re_size_skip:%d:moved line counter to:%d', re_size_skip, i)
                logger.debug('%d:%s', i, file_list[i])
                
                # check the counter
                if i >= list_len: continue

            # save this in the record
            if re_sizes:
                # search through the list of comparisons to find a match
                for re_size in re_sizes:
                    found = re_size.search( file_list[i] )
                    if found:
                        record['wine_name'] += ' ' + found.group(1)

                        # debugging
                        if debug: print('i:', i, ':name:', record['wine_name'], ':re_size:', re_size)
                        logger.debug('i:%d:name:%s:re_size:%s', i, record['wine_name'], re_size)
                        break
                
        ### WINE PRICE ####

        # search for the wine price
        (i,match,found) = search_list_for( re_price_start, file_list, i, re_price_end, debug=debug )

        # did not find a match - so skip this record
        if not match:
            # move to next line
            i += 1
            # debugging
            if debug: print('winerequest:generic_wine_parser:did not find wine price - skipping this record and continued search at line:', i)
            logger.debug('did not find wine price - skipping this record and continued search at line:%d', i)
            continue

        # if set to skip lines then skip lines
        if re_price_skip:
            i += re_price_skip
            # debugging
            if debug:
                print('re_price_skip:%d', re_price_skip, ':moved line counter to:', i)
                print(i, ':', file_list[i])
            logger.debug('re_price_skip:%d:moved line counter to:%d', re_price_skip, i)
            logger.debug('%d:%s', i, file_list[i])
            # check the counter
            if i >= list_len: continue

        # capture the found price
        if not re_prices:
            record['wine_price'] = price_cleanup( found.group(1) )
            # debugging
            if debug: print('i:', i, ':price:', record['wine_price'])
            logger.debug('i:%d:price:%s', i, record['wine_price'])
        else:
            # search through the list of comparisons to find a match
            for re_price in re_prices:
                found = re_price.search( file_list[i] )
                if found:
                    record['wine_price'] = price_cleanup( found.group(1) )
                    # debugging
                    if debug: print('i:', i, ':price:', record['wine_price'], ':re_price:', re_price)
                    logger.debug('i:%d:price:%s:re_price:%s', i, record['wine_price'], re_price)
                    break
                else:
                    if debug: print('winerequest:generic_wine_parser:wine_price-not-match:', re_price)
                    logger.debug('wine_price-not-match:%s', re_price)
            # check to see we found a name, and if not skip this section
            if 'wine_price' not in record:
                i += 1
                if debug: print('winerequest:generic_wine_parser:did not match any wine price regex - skipping and looking again at line:', i)
                logger.debug('did not match any wine price regex - skipping and looking again at line:%d', i)
                continue
            
        # debugging
        if debug:
            print('------------------------------')
            for name in ['wine_name', 'wine_year', 'wine_price']:
                if name in record:
                    print(name, ':', record[name])
            print('------------------------------')
        logger.debug('------------------------------')
        for name in ['wine_name', 'wine_year', 'wine_price']:
            if name in record:
                logger.debug('%s:%s', name, record[name])
        logger.debug('------------------------------')
                
        # save this record to results - if it is not already in there
        if record not in results:
            results.append(record)
        else:
            if debug:
                print('winerequest:generic_wine_parser:duplicate record not saved')
            logger.debug('duplicate record not saved:%s', record)
    
        # need to determine if want to increment here or not - we could just use the following
        # logic, that says if we are on the same line we found the wine_name on - then increment - otherwise don't
        #
        # earlier logic was just to increment the line no matter what - get rid of this if logic here.
        # not sure what is the right thing to do - we will need to experiment
        if i == last_i:
            # all information was on one line, and we don't want to find this line again so increment
            # increment line counter past price line
            i += 1
            # debugging
            if debug: print('winerequest:generic_wine_parser:all information on the same line - increment the line counter:', i)
            logger.debug('all information on the same line - increment the line counter:%d', i)

    # check to see if we got any results
    if not results:
        return wineselenium.returnNoWineFound( label )
        
    # looped through the file return the results
    return results

# generic utility used to convert a string into a list of lines
# performing a number of regex operations to the string before splitting
# and in the list of lines, remove all blank lines
def generic_wine_splitter( content, re_splitters=None, debug=False ):
    if re_splitters:
        for (re_splitter, replacement) in re_splitters:
            if debug: print('winerequest:generic_wine_splitter:len(content):before:', len(content))
            content = re_splitter.sub(replacement, content)
            if debug: print('winerequest:generic_wine_splitter:len(content):after:', len(content))

    # split up the content and only keep non-blank lines
    return [x for x in content.splitlines() if x]



# generic utility used to go to a page, enter search, parse results and return list of vlaues
def generic_wine_searcher( srchstring, store, store_args, debug=False ):
    
    # full test of the generic features
    if False:
        try:
            content = generic_wine_content_searcher( srchstring, **store_args[store]['search_args'], debug=debug )
        except:
            return []
    else:
        # debugging
        if debug:
            print('winerequest:generic_wine_searcher:store:', store)
        # want it to fail here so we can see the error
        content = generic_wine_content_searcher( srchstring, **store_args[store]['search_args'], debug=debug )

    # check the content - there may be nothing here - if so return blank array
    if not content:
        return []
    
    # bust the file into lines
    file_list = generic_wine_splitter( content, **store_args[store]['splitter_args'] )
    
    # pull out the the results
    return generic_wine_parser(file_list, **store_args[store]['parser_args'], debug=debug)

# generic utility used to take in a search string, and a url formatter that will place this
# string into the URL and then use requests to get that URL
# optionally, use the list of re_noresults to determine if no results were found
# return back the content that will then be split and parsed
#
def generic_wine_content_searcher( srch_string, url_fmt, payload=None, payload_fld = None, re_noresults=None, UserAgent = None, debug=False ):

    # create headers if we need to
    headers = None
    if UserAgent:
        headers = {'User-agent' : UserAgent}

    # action based on the type of information provided
    if payload:
        # POST a form transaction
        #
        # validate that the payload_fld is populated
        if not payload_fld:
            if pmsg: print('winerequest:generic_wine_content_searcher:payload-populated:payload_fld-NOT-populated-ERROR')
            logger.error('payload-populated:payload_fld-NOT-populated-ERROR')
            raise Exception('payload_fld not populated')
        else:
            # put the search string into the payload
            payload[payload_fld] = srch_string

        # just create the url in the right string point
        url_final = url_fmt
        
        # debugging
        if debug:
            print('winerequest:generic_wine_content_searcher:payload:post_url:', url_final)
            print('winerequest:generic_wine_content_searcher:payload:post_payload:', payload)
        logger.debug('payload-post_url:%s', url_final)
        logger.debug('payload-payload:%s', payload)

        # now we create the post request
        session = requests.session()
        r = requests.post( url_final, payload, headers=headers )
    else:
        # GET a page transaction
        #
        # calculate the final url
        url_final = url_fmt % srch_string

        # debugging
        if debug:
            print('winerequest:generic_wine_content_searcher:get_url:', url_final)
        logger.debug('get_url:%s', url_final)

        # get the page
        r = requests.get( url_final, headers=headers )

    # check the status code - if invalid raise error
    if r.status_code != 200:
        if pmsg: print('winerequest:generic_wine_content_searcher:not 200:url_final:', url_final, ':status_code:', r.status_code)
        if pmsg: print('winerequest:generic_wine_content_searcher:content:', r.content)
        logger.error('not 200:url_final:%s:status_code:%s', url_final, r.status_code)
        logger.error('content:', r.content)
        raise Exception(r.content)

    # check to see if there were any results
    if re_noresults:
        for re_noresult in re_noresults:
            if re_noresult.search( r.text ):
                if pmsg: print('winerequest:generic_wine_content_searcher:no_results:url_final:', url_final, ':no_result:', re_noresult)
                logger.debug('no_results:url_final:%s:re_noresult:%s', url_final, re_noresult)
                return None

    # return the ASCII web page content
    return r.content.decode('ascii', 'ignore')


#---------------------------------------------------------------------------

def nhliquor_wine_searcher( srchstring, debug=False ):

    label = 'NHLiq'

    # first - get the starting page that lists out all the wines that match the srchstring
    url_fmt = 'http://www.liquorandwineoutlets.com/products?page=%s&search=%s'
    re_noresults = [ re.compile('no products that match'), ]

    # local variables
    results = []
    
    # loop through all the pages that might have results
    for page in range(1,5):
        # GET a page transaction
        #
        # calculate the final url
        url_final = url_fmt % (page, srchstring)

        # debugging
        if debug: print('nhliquor_wine_searcher:url_final:', url_final)
        

        # get the page
        r = requests.get( url_final )
        
        # check the status code - if invalid raise error
        if r.status_code != 200:
            if pmsg: print('nhliquor_wine_searcher:url_final:', url_final, ':status_code:', r.status_code)
            logger.warning('nhliquor_wine_searcher:url_final:%s:status_code:%s', url_final, r.status_code)
            raise
        
        # check to see if there were any results
        if re_noresults:
            for re_noresult in re_noresults:
                if re_noresult.search( r.text ):
                    if debug: print('nhliquor_wine_searcher:url_final:', url_final, ':no_result:', re_noresult)
                    logger.debug('nhliquor_wine_searcher:url_final:%s:no_result:%s', url_final, re_noresult)
                    return wineselenium.returnNoWineFound( label )

        # return the ASCII web page content
        results.extend(nhliquor_main_parser(r.content.decode('ascii', 'ignore'), label, debug=debug))

        # check to see if we are done - does page have a link to this next page 
        new_url = 'page=%s&search=%s' % (page+1, srchstring)
        re_done = re.compile( new_url )
        if not re_done.search( r.content.decode('ascii', 'ignore') ):
            # link does not exist - we are done
            break
        else:
            if pmsg: print('nhliquor_wine_searcher:',srchstring,':retreiving page:',page+1)
            logger.info('%s:retreiving page:%d',srchstring, page+1)

    # return the results
    return results


# parse an HTML page with table data to get back wine results from NHLiquor store
def nhliquor_main_parser( html, label, debug=False ):

    # capture the place that we pull out the wine information from
    results = []

    # we needed to build a CUSTOM HTML table parser
    # tried to use lxml and BeautifulSoup to do this 
    # and could not get it to work - UGH!


    # split this up into lines and trim those lines to remove white space
    htmllist = generic_wine_splitter( html )
    htmlstrip = [line.strip() for line in htmllist]

    # loop through and remove blocks of comments 
    # but only remove HTML comments that exist inside the 
    # table structure - leave in place comments that are line inline
    intable=False
    comment=False
    htmllist=[]
    for line in htmlstrip:
        if '<table' in line:



            intable=True
            
        if not intable:
            htmllist.append(line)
            continue
        
        if line.startswith('<!--') and not line.endswith('-->'):
            comment=True
        if not comment:
            htmllist.append(line)
        if line.startswith('-->'):
            comment=False

        if '</table>' in line:
            intable = False

    # debugging
    if debug:
        print('-'*40)
        print('\n'.join(htmllist))
        print('-'*40)
        print('len-htmlstrip:', len(htmlstrip))
        print('len-htmllist.:', len(htmllist))

        
    # where we put the header of what we parse
    header = []

    # set up to step through the file
    i=0
    list_len = len(htmllist)
    last_i=0

    # find table - re_start
    (i,match,found) = search_list_for( re.compile('<table'), htmllist, i, debug=debug )
    if not match:
        logger.warning('did not find the table - stopped processing')
        if pmsg: print('winerequest:nhliquor_main_parser:did not find the table - stopped processing')
        return []


    #### HEADER #####
    # extract the table header
    #
    # 1)find the first row
    (i,match,found) = search_list_for( re.compile('<tr'), htmllist, i, debug=debug )
    if not match:
        logger.warning('did not find the first row in table - stopped processing')
        if pmsg: print('winerequest:nhliquor_main_parser:did not find the first row in table - stopped processing')
        return []

    # 2) pull each <th out unless we encounter the end of table row
    while i < list_len:
        (i,match,found) = search_list_for( re.compile('<th'), htmllist, i, re.compile('\/tr>'), debug=debug )
        # move to the next line no matter what
        if not match:
            # hit the end of the table row - so increement and break out
            break
        # found the table header and look at next line
        while not kev_html_stripper( htmllist[i] ):
            if debug:  print('B:{:04d}:{}'.format(i, htmllist[i]))
            logger.debug('B:{:04d}:{}'.format(i, htmllist[i]))
            # blank line - get next line
            i += 1
        # got a non blank line - put this in the header array
        if debug:  print('X:{:04d}:{}'.format(i, htmllist[i]))
        logger.debug('X:{:04d}:{}'.format(i, htmllist[i]))
        header.append( kev_html_stripper( htmllist[i] ).strip() )
        # move past this processed line
        i += 1
        
    # done with header
    if debug:
        print(i, ':file:', htmllist[i])
        print(i, ':header:', header)
    logger.debug('%d:file:%s', i, htmllist[i])
    logger.debug('%d:header:%s', i, header)

    ### ROWS ######
    while i < list_len:
        row = []
        # 1) find the next row until you get to the end of the table
        (i,match,found) = search_list_for( re.compile('<tr'), htmllist, i, re.compile('\/table>'), debug=debug )
        if not match:
            if debug:  print(i,':table complete')
            logger.debug('%d:table complete', i )
            break

        ### COLUMNS ####
        # 2) get all the columns for this row - end if we get to the row end html
        while i < list_len:
            (i,match,found) = search_list_for( re.compile('<td'), htmllist, i, re.compile('\/tr>'), debug=debug )
            if not match:
                if debug:  print(i,':row complete')
                logger.debug('%d:row complete',i)
                break
            # go through lines until we find the one with data
            while not kev_html_stripper( htmllist[i] ):
                if debug:  print('B:{:04d}:{}'.format(i, htmllist[i]))
                logger.debug('B:{:04d}:{}'.format(i, htmllist[i]))
                # blank line - get next line
                i += 1
            if debug:  print('X:{:04d}:{}'.format(i, htmllist[i]))
            logger.debug('X:{:04d}:{}'.format(i, htmllist[i]))
            row.append( kev_html_stripper( htmllist[i] ).strip() )
            i += 1
            

        # done with row - make the dict and hten make the wine record we want
        if debug:
            print('row:', row)
            print('len-row:', len(row), '\n\n')
        logger.debug('row:%s', row)
        logger.debug('len-row:%d', len(row))
                  
        # validate we got enough columns in this row
        if len(row) >= 7:
            rawrec = (dict(zip(header, row)))
            rec = {
                'label'      : label,
                'wine_store' : label,
                'wine_name'  : ' '.join([rawrec['Name'], rawrec['Size']]),
                'wine_year'  : '',
            }
            if rawrec['Sale Price'] == '-':
                rec['wine_price'] = price_cleanup(rawrec['Reg. Price'])
            else:
                rec['wine_price'] = price_cleanup(rawrec['Sale Price'])

            # pull out and save
            if debug:
                print('header:', header)
                print(i, ':row:', row)
                print('rawrec:', rawrec)
                print('rec:', rec)
            logger.debug('header:%s', header)
            logger.debug('%i:row:%s', i, row)
            logger.debug('rawrec:%s', rawrec)
            logger.debug('rec:%s', rec)
            
            # add what we found to the results array
            results.append(rec)

    # debugging
    if debug:  print('results:', results)
    logger.debug('results:%s', results)

    if not results:
        return wineselenium.returnNoWineFound( label )
    
    # done return the results
    return results

        
#########################################################################################
###
###    kev_html_stripper($string)
###
###    Tool used to do simple HTML link stripping from a string.
###    Should be replaced with a real tool some time in the future.
###
###
def kev_html_stripper(string,nocommafilter=False):
    # strip out hmtl
    string = re.sub('<[^>]*>','',string)

    # regex to convert values
    string = string.replace('&amp;','&').replace('%quot;',' ').replace('&rsquo;',' ').replace('%nbsp;',' ')

    # special processing
    if not nocommafilter:
        string = string.replace(',','')

    return string

# this utility is used to pull the name from a string (wine_name)
def _extract_year_from_name( winename, debug=False ):
    # define the list of regex in order to find a year in a string
    re_dates = [
        re.compile('\s(\d\d\d\d)\s'),
        re.compile('(\d\d\d\d)\s'),
        re.compile('\s(\d\d\d\d)'),
        re.compile('\s\'(\d\d)\s'),
        re.compile('\s(\d\d)\s')
    ]

    # loop through the list of regex used to find a date
    for date_match in re_dates:
        found = date_match.search( winename )
        if found:
            # debugging
            if debug: print('winerequest:_extract_year_from_name:winename:', winename, ':wine_year:', found.group(1))
            logger.debug('winename:%s:wine_year:%s', winename, found.group(1))
            # return back the value we found
            return found.group(1)
    # all loops performed nothing found
    return None

#####################################################################################

if __name__ == '__main__':

    # capture the command line
    optiondict = kvutil.kv_parse_command_line( optiondictconfig, debug=False )

    # extract the values and put into variables
    debug    = optiondict['debug']
    AppVersion = optiondict['AppVersion']

    ### STORE LIST ####

    # pick the store we are going to check
    if 'storelist' in optiondict and optiondict['storelist']:
        # passed in on the command line
        winereq_storelist = [optiondict['storelist']]
    else:
        # (winerequest) request stores
        winereq_storelist = [
            'binnys',
            'hiddenvine',
#            'winex',  # done in wineselenium
            'napacab',
#            'webwine',  #05/15/2020 - not working - commented out - run with findwine.pl it works there
            'lawineco',
            'wineconn',
            'johnpete',
#            'wine2020', #05/15/2020 - not working - commented out - port to wineselenium.py
#            'acwine',   #05/15/2020 - too much work to make work - ignoring this wine site.
            'klwine', 
            'nhliquor',
            'rolf',
#            'winezap',
#           'winehouse', # needs to be implemented
#           'winecom', # needs to be implemented
#           'bestwine', # needs to be implemented
        ]

    # dump out what we have done here
    if optiondict['test']:
        if pmsg: print('---------------TEST FLAG ENABLED---------------------------')
        logger.info('---------------TEST FLAG ENABLED---------------------------')


    # check to see if we passed in srchlist instead of srchstring
    if optiondict['srchlist'] and not optiondict['srchstring']:
        if pmsg: print('srchlist was passed in INSTEAD of srchstring - substituting')
        logger.info('srchlist was passed in INSTEAD of srchstring - substituting')
        optiondict['srchstring'] = optiondict['srchlist']
    

    # debugging
    if optiondict['verbose'] > 0:
        if pmsg: print('---------------STARTUP(v', optiondictconfig['AppVersion']['value'], ')-(', datetime.datetime.now().strftime('%Y%m%d:%T'), ')---------------------------')
    logger.info('STARTUP(v%s)%s', optiondictconfig['AppVersion']['value'], '-'*40)



    ### WINE_XLAT ###
    # load in xlat file in to a module level variable
    wineselenium.read_wine_xlat_file( optiondict['winexlatfile'], debug=debug )



    ### SEARCH LIST ####

    # srchstring - set at None - then we will look up the information from the file
    srchstring_list = None

    # uncommnet a line below if you want define the wines you are checking for
    #srchstring_list = ['attune','groth','beringer','hewitt','crawford','foley']
    if optiondict['test']:
        srchstring_list = ['groth','cakebread','foley']
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
        srchstring_list = wineselenium.get_winelist_from_file( optiondict['wineinputfile'], debug=debug )
        wineselenium.remove_already_processed_wines( optiondict['wineoutfile'], srchstring_list, debug=debug )
        if not srchstring_list:
            if pmsg: print('main:no wines to search for - ending program')
            logger.info('main:no wines to search for - ending program')
            sys.exit()

        
    # debugging
    if debug:
        print('debug:', debug)
        print('storelist:', winereq_storelist)
        print('srchstring_list:', srchstring_list)
    logger.debug('debug:%s', debug)
    logger.debug('storelist:%s', winereq_storelist)
    logger.debug('srchstring_list:%s', srchstring_list)

    
    # read in the wines defined
    wines = get_wines_from_stores( srchstring_list, winereq_storelist, optiondict['wineoutfile'], debug=debug )


    # display what we read
    if debug:  print('winerequest:wines:', wines)
    logger.debug('wines:%s', wines)

#eof
