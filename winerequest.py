import kvutil

import re
import requests
#from bs4 import BeautifulSoup

# module global variables
glb_last_line_check=-1       # global variable to store the line number we just called
glb_last_line_count=0        # global variable to count number of times we called this line
glb_last_line_max  =3

# application variables
optiondictconfig = {
    'AppVersion' : {
        'value' : '1.13',
        'description' : 'defines the version number for the app',
    },
    'debug' : {
        'value' : False,
        'type'  : 'bool',
        'description' : 'defines if we are running in debug mode',
    },
    'srchstring' : {
        'value'  : 'cakebread',
        'description' : 'defines the wine to be searched',
    },
    'storelist' : {
        'description' : 'defines the store to be searched, if not set we search all stores',
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



def get_wines_from_stores( srchstring_list, storelist, debug=False ):
    # grab the store defintions
    store_args = store_definitions()

    # create the list of records for each search string
    found_wines = []

    # step through the search strings
    for srchstring in srchstring_list:
        # step through the store list
        for store in storelist:
            # processing logic
            if store == 'nhliquor':
                found_wines.extend(nhliquor_wine_searcher( srchstring, debug=debug ))
            else:
                found_wines.extend(generic_wine_searcher( srchstring, store, store_args, debug=debug ))

    # when done with all the loops return the results
    return found_wines

# capture the store definitions
def store_definitions():
    return {
        'hiddenvine' : {
            'search_args' : {
                'url_fmt'      : 'http://www.ahiddenvine.com/search.asp?search=SEARCH&keyword=%s',
                're_noresults' : [ re.compile('0 Records Found') ],
            },
            'splitter_args' : {},
            'parser_args' : {
                're_name_start'  : re.compile("<td><a href='[^']*'>([^<]*)<", re.IGNORECASE),
                're_name_end'    : None,
                're_price_start' : re.compile('<span class="price">([^<]*)<\/span>', re.IGNORECASE),
                're_price_end'   : re.compile('Add to Cart'),
                'label'          : 'Hidden',
            },
        },
        'winex' : {
            'search_args' : {
                'url_fmt'      : 'https://www.winex.com/searchwines.html',
                'payload'      : { 'keywords' :  'no-value-substitued' },
                'payload_fld'  : 'keywords',
                're_noresults' : [ re.compile('No Results were found') ],
            },
            'splitter_args' : {
                're_splitters' : [ (re.compile('<td'), '\n<td'), ]
            },
            'parser_args' : {
                'label'         : 'WineEx',
                're_name_start' : re.compile('<div class="product_items_list_title"><a href="[^"]*">([^<]*)<', re.IGNORECASE),
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
                're_name_skip'   : 1,
                're_names'       : [ re.compile('">([^<]*)<') ],
                're_price_start' : re.compile('data-product-price-without-tax'),
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
                're_name_end'    : None,
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
                're_name_end'    : None,
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
                're_name_end'    : None,
                're_names'       : [ re.compile('') ],
                're_price_start' : re.compile('div class="price"', re.IGNORECASE),
                're_price_end'   : re.compile('data-name="([^"]*)"'),
                're_prices'      : [ re.compile('>\$([^<]*)<', re.IGNORECASE), ],
                'label'          : 'WineCo-LA',
            },
        },
        'johnpete' : {
            'search_args' : {
                'url_fmt'      : 'http://www.johnandpetes.com/index.php/view-all-products-in-shop/Page-1-50?keyword=%s',
                're_noresults' : [ re.compile('No Products Found') ],
            },
            'splitter_args' : {
                're_splitters' : [ (re.compile('"productPrice">\s*\$', re.IGNORECASE), '"productPrice">\$'), ],
            },
            'parser_args' : {
                're_name_start'  : re.compile('a class="product_name" title="([^"]*)"', re.IGNORECASE),
                're_name_end'    : None,
                're_price_start' : re.compile('span class="productPrice">', re.IGNORECASE),
                're_price_end'   : re.compile('a class="product_name" title', re.IGNORECASE),
                're_prices'      : [ re.compile('.(\d*\.\d*)'), ],
                'label'          : 'JohnPete',
            },
        },
        'wine2020' : { # - looks like this needs to be ported to selenium 
            'search_args' : {
                'url_fmt'      : 'http://www.2020wines.com/catalogsearch/result/?x=0&y=0&q=%s',
                're_noresults' : [ re.compile('No items were found', re.IGNORECASE) ],
            },
            'splitter_args' : {
                're_splitters' : [ (re.compile('\s*\$'), '\$'), ],
            },
            'parser_args' : {
                're_name_start'  : re.compile('class="product_name"><a href="[^>]*>([^<]*)<', re.IGNORECASE),
                're_name_end'    : None,
                're_names'       : [ re.compile('">([^<]+)<\/a>') ],
                'label'          : '2020Wine-LA',
            },
        },
        'acwine' : { 
            'search_args' : {
                'url_fmt'      : 'https://www.accidentalwine.com/search?x=0&y=0&q=%s',
                're_noresults' : [ re.compile('No se') ],
            },
            'splitter_args' : {},
            'parser_args' : {
                're_name_start'  : re.compile('', re.IGNORECASE),
                're_name_end'    : None,
                're_names'       : [ re.compile('') ],
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
                'url_fmt'      : 'http://www.klwines.com/Products/r?d=0&r=0&p=0&o=-1&t=%s',
                're_noresults' : [ re.compile('produced no results') ],
            },
            'splitter_args' : {},
            'parser_args' : {
                're_name_start'  : re.compile('result-desc', re.IGNORECASE),
                're_name_end'    : None,
                're_name_skip'   : 1,
                're_names'       : [ re.compile('>([^<]*)<') ],
                're_price_start' : re.compile('span class="price"', re.IGNORECASE),
                're_price_end'   : re.compile('result-desc'),
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
                're_name_end'    : None,
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
                're_name_end'    : None,
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
        'zzTemplate' : { # (acwine custom)
            'search_args' : {
                'url_fmt'      : '',
                're_noresults' : [ re.compile('0 Records Found') ],
            },
            'splitter_args' : {},
            'parser_args' : {
                're_name_start'  : re.compile('', re.IGNORECASE),
                're_name_end'    : None,
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



###########################################################################################################
###
###    kev_html_stripper($string)  NOTUSED
###
###    Tool used to do simple HTML link stripping from a string.
###    Should be replaced with a real tool some time in the future.
###
###
def kev_html_stripper(string,nocommafilter=False):
    # regex to convert values
    string = string.replace('&amp;','&').replace('%quot;',' ').replace('&rsquo;',' ').replace('%nbsp;',' ')
    # .replace =~ s/<.+?>//sgi      # simple html replacer

    # special processing
    if not nocommafilter:
        string = string.replace(',','')

    return string


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
            if debug: print( "Reprocessed the line [%s] more than [%s] times" % (ptr, glb_last_line_max) )
            if debug: print( "Searching for [%s]" % search_re)
            if debug: print( 'file_aref:', file_aref )    
            return (0,0, None)

    else:
        # first time we see this lie
        glb_last_line_check = ptr
        glb_last_line_count = 0

    # define a displayable line number
    iptr = "%04d" % ptr

    # debugging
    if debug: print( "s%s:search for:%s" % (iptr,search_re) )
    if debug and not_find_1st_re: print( "n%s:not_first:%s" % (iptr,not_find_1st_re) )
    
    # step through records until we find the string or end of file (make this an re.search or re.search)
    while not search_re.search(file_aref[ ptr ]):

	# debugging
        if debug: print( "s%s:%s" % (iptr, file_aref[ptr]) )
            
	# next line
        ptr += 1
        
	# display version
        iptr = "%04d" % ptr
	
	# failed to find it if we have out run the array
        if ptr >= list_len:
            # debugging
            if debug: print( "f%s:FAILED-HIT-BOTTOM" % iptr )
            
            # reset flags and pointers
            match = 0
            ptr   = 0
            iptr  = "%04d" % ptr

            # if the no_bottom flag is set, don't return to zero but back to where we started
            if no_bottom: ptr = ptr_orig
        
            # we are done processing for now - send results back up
            break

	# check to see if we have matched the skip
        if not_find_1st_re:
            if not_find_1st_re.search(file_aref[ ptr ]):
                # this line is the list that we stop looking at
                # debugging
                if debug: print( "s%s:%s" % (iptr, file_aref[ptr]) )
                if debug: print( "f%s:FAILED-NOT-FIND-1ST\n" % (iptr) )

                # set the pointers as we did not find the desire string
                match = 0;
                ptr   = ptr_orig;
		
                # reset glb_last_line_count
                glb_last_line_count = 0;

                # we are done processing this loop for now
                break

    #wend
    
    # debugging
    if debug: print( 'search_list_for:end of wend loop:match:', match  )

    # check to see if we found what we were looking for
    if match:
        if debug: print( "m%s:%s" % (iptr, file_aref[ptr]) )
    else:
        if debug: print( "l%s:%s" % (iptr, file_aref[ptr]) )


    # reset glb_last_line_count, we found what we want
    glb_last_line_count = 0;

    # we must have found it, return the line number
    return (ptr, match, search_re.search( file_aref[ptr]))



# clean up a price field so it is pure numeric
def price_cleanup(price):
    return price.replace('$','').replace(',','').replace('>','').strip()


# generic parser with regex values passed in
# inputs:  (re_* - are all re.compile() statements except where documented below)
#    file_list - list of strings that make up the file
#    re_start - (opt) moves you to a starting area in the file that you can iterate on
#
#    re_name_start - finds the next wine name, and optionally extract out the name from the line (see re_names)
#    re_name_end - (opt) if you encounter this, stop looking for wine name
#    re_name_skip - (opt) NOT an re.compile - this is an INT - number of lines to move after you re_name_start find
#    re_name_multi - (opt) NOT an re.compile - this is True/False - when True - you look for name on multiple lines
#    re_names - (opt) - list of re.compile statements - used to extract the name from the file line containing the name
#                if not populated we use re_name_start to extract out the name as group(1)
#
#    # may be added in
#    re_size_start
#    re_size_end
#    re_sizes
#
#    re_price_start - finds the price for that wine
#    re_price_end - (opt) stops looking if finds this first (usually set to re_name_start)
#    re_price_skip - (opt) NOT an re.compile - this is an INT - number of lines to move after you re_price_start find
#    re_prices - (opt) - list of re.compile statements - used to extract the price from the file line containing the name
#                if not populated we use re_price_start to extract out the price as group(1)
#
def generic_wine_parser( file_list, label, re_name_start, re_name_end=None, re_name_skip=None, re_name_multi=None, re_name_groups=None, re_price_start=None, re_price_end=None, re_price_skip=None, re_start=None, re_names=None, re_prices=None, debug=False):

    # might need to add in logic to extract out the wine bottle size into this parser (2018-09-26)
    
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
            print('generic_wine_parser:did not find requested starting area - terminating:', re_start)
            return []

    # debugging
    print('searching store:', label)
    
    # loop through the lines in this file
    while i < list_len:
        # create the starting dict
        record = {
            'label' : label,
            'wine_store' : label,
            'wine_year'  : '',
        }
    
        # search for the name
        (i,match,found) = search_list_for( re_name_start, file_list, i, re_name_end, debug=debug )

        # action if we did not find a match
        if not match:
            # debugging
            if debug and not results: print('generic_wine_parser:did not find wine name')
            break

        # capture the name line we just saw
        last_i = i
        
        # if set to skip lines then skip lines
        if re_name_skip:
            i += re_name_skip
            # debugging
            if debug: print('re_name_skip:', re_name_skip, ':moved line counter to:', i)
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
            if debug: print('generic_wine_parser:i:', i, ':name:', record['wine_name'])
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
                    if debug: print('generic_wine_parser:i:', i, ':name:', record['wine_name'], ':re_name:', re_name)
                    break
            # check to see we found a name, and if not skip this section
            if 'wine_name' not in record:
                # move to next line
                i += 1
                # debugging
                if debug: print('generic_wine_parser:did not find a wine name - skipping and looking again at line:', i)
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
                    if debug: print('generic_wine_parser:i:', i, ':loading next line into name:', file_list[i])
                    # add this line (might want to trim the new line content)
                    record['wine_name'] = record['wine_name'] + ' ' + file_prt[i].replace('<br>', ' ')

                # and when done - remove the final <
                record['wine_name'] = record['wine_name'].replace('<', '')
            # WINECONN #
            
        # extract the wine year from the name if it exists
        record['wine_year'] = _extract_year_from_name( record['wine_name'] )

        # search for the wine price
        (i,match,found) = search_list_for( re_price_start, file_list, i, re_price_end, debug=debug )

        # did not find a match - so skip this record
        if not match:
            # move to next line
            i += 1
            # debugging
            if debug: print('generic_wine_parser:did not find wine price - skipping this record and continued search at line:', i)
            continue

        # if set to skip lines then skip lines
        if re_price_skip:
            i += re_price_skip
            # debugging
            if debug: print('re_price_skip:', re_price_skip, ':moved line counter to:', i)
            # check the counter
            if i >= list_len: continue

        # capture the found price
        if not re_prices:
            record['wine_price'] = found.group(1).replace('$','').replace(',','')
            # debugging
            if debug: print('generic_wine_parser:i:', i, ':price:', record['wine_price'])
        else:
            # search through the list of comparisons to find a match
            for re_price in re_prices:
                found = re_price.search( file_list[i] )
                if found:
                    record['wine_price'] = found.group(1).replace('$','').replace(',','')
                    # debugging
                    if debug: print('generic_wine_parser:i:', i, ':price:', record['wine_price'], ':re_price:', re_price)
                    break
                else:
                    if debug: print('wine_price-not-match:', re_price)
            # check to see we found a name, and if not skip this section
            if 'wine_price' not in record:
                i += 1
                if debug: print('generic_wine_parser:did not match any wine price regex - skipping and looking again at line:', i)
                continue
            
        # debugging
        if debug:
            print ('------------------------------')
            for name in ['wine_name', 'wine_year', 'wine_price']:
                if name in record:
                    print(name, ':', record[name])
                    print ('------------------------------')
                
        # save this record to results - if it is not already in there
        if record not in results:
            results.append(record)
        else:
            if debug:
                print('duplicate record not saved')
    
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
            if debug: print('generic_wine_parser:all information on the same line - increment the line counter:', i)

        
    # looped through the file return the results
    return results

# generic utility used to convert a string into a list of lines
# performing a number of regex operations to the string before splitting
# and in the list of lines, remove all blank lines
def generic_wine_splitter( content, re_splitters=None, debug=False ):
    if re_splitters:
        for (re_splitter, replacement) in re_splitters:
            if debug: print('len(content):before:', len(content))
            content = re_splitter.sub(replacement, content)
            if debug: print('len(content):after:', len(content))

    # split up the content and only keep non-blank lines
    return [x for x in content.splitlines() if x]

# generic utility used to go to a page, enter search, parse results and return list of vlaues
def generic_wine_searcher( srchstring, store, store_args, debug=False ):
    
    # full test of the generic features
    content = generic_wine_content_searcher( srchstring, **store_args[store]['search_args'] )

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
def generic_wine_content_searcher( srch_string, url_fmt, payload=None, payload_fld = None, re_noresults=None ):

    # action based on the type of information provided
    if payload:
        # POST a form transaction
        #
        # validate that the payload_fld is populated
        if not payload_fld:
            print('generic_wine_content_searcher:payload-populated:payload_fld-NOT-populated-ERROR')
            raise
        else:
            # put the search string into the payload
            payload[payload_fld] = srch_string

        # just create the url in the right string point
        url_final = url_fmt
        
        # now we create the post request
        session = requests.session()
        r = requests.post( url_final, payload )
    else:
        # GET a page transaction
        #
        # calculate the final url
        url_final = url_fmt % srch_string

        # get the page
        r = requests.get( url_final )

    # check the status code - if invalid raise error
    if r.status_code != 200:
        print('generic_wine_content_searcher:not 200:url_final:', url_final, ':status_code:', r.status_code)
        raise

    # check to see if there were any results
    if re_noresults:
        for re_noresult in re_noresults:
            if re_noresult.search( r.text ):
                print('generic_wine_content_searcher:no_results:url_final:', url_final, ':no_result:', re_noresult)
                return None

    # return the ASCII web page content
    return r.content.decode('ascii', 'ignore')


#---------------------------------------------------------------------------

def nhliquor_wine_searcher( srch_string, debug=False ):

    # first - get the starting page that lists out all the wines that match the srch_string
    url_fmt = 'http://www.liquorandwineoutlets.com/products?page=%s&search=%s'
    re_noresults = [ re.compile('no products that match'), ]

    # local variables
    results = []
    
    # loop through all the pages that might have results
    for page in range(1,5):
        # GET a page transaction
        #
        # calculate the final url
        url_final = url_fmt % (page, srch_string)

        # debugging
        if debug: print('url_final:', url_final)
        
        # get the page
        r = requests.get( url_final )
        
        # check the status code - if invalid raise error
        if r.status_code != 200:
            print('nhliquor_wine_searcher:url_final:', url_final, ':status_code:', r.status_code)
            raise
        
        # check to see if there were any results
        if re_noresults:
            for re_noresult in re_noresults:
                if re_noresult.search( r.text ):
                    print('nhliquor_wine_searcher:url_final:', url_final, ':no_result:', re_noresult)
                    return None

        # return the ASCII web page content
        results.extend(nhliquor_main_parser(r.content.decode('ascii', 'ignore'), debug=debug))

        # check to see if we are done - does page have a link to this next page 
        new_url = 'page=%s&search=%s' % (page+1, srch_string)
        re_done = re.compile( new_url )
        if not re_done.search( r.content.decode('ascii', 'ignore') ):
            # link does not exist - we are done
            break

    # return the results
    return results


# parse an HTML page with table data to get back wine results from NHLiquor store
def nhliquor_main_parser( html, debug=False ):
    # capture the place that we pull out the wine information from
    results = []
    
    return results

    # We now have the source of the page, let's ask BeaultifulSoup
    # to parse it for us.
#    soup = BeautifulSoup(html, 'html.parser')

    # find the start of the table
    data = soup.find('table', class_ = 'product_table')

    # pull out the section that is the header for the table and the body of the table
    header = data.find('thead')
    body = data.find('tbody')

    # from the header - pull out the column headers
    keys = [i.text.strip() for i in header.find_all('th')]

    # debugging
    if debug:
        print('nhliquor_main_parser:keys:', keys)

    # for each row in the body
    for row in body.find_all('tr'):
        # pull out the values in this row in the table
        vals = [i.text.strip() for i in row.find_all('td')]

        # create a dictionary that is combination of these
        my_dict = dict(zip(keys, vals))

        # update/convert fields of interest
        if my_dict['Sale Price'] != '-':
            # take sale price if not populated
            my_dict['Reg. Price'] = my_dict['Sale Price']
        # update price to remove unwanted characters ($ and ,)
        my_dict['Reg. Price'] = my_dict['Reg. Price'].replace('$', '').replace(',','')
        # add size to name if not 750mL
        if my_dict['Size'] !=  '750mL':
            my_dict['Name'] = ' '.join( (my_dict['Name'], my_dict['Size']) )
        # get the wine_year
        my_dict['wine_year'] = _extract_year_from_name( my_dict['Name'], debug=debug )

        # build the final dictionary
        record = {
            'wine_store' : 'NHLiq',
            'label'      : 'NHLiq',
            'wine_name'  : my_dict['Name'],
            'wine_price' : my_dict['Reg. Price'],
            'wine_year'  : my_dict['wine_year'],
        }
        # add this new row to teh results
        results.append(record)

        # debugging
        if debug:
            print('my_dict:', my_dict)
            print('record:', record)

    # done return the results
    return results

        
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
            if debug: print ('_extract_year_from_name:winename:', winename, ':wine_year:', found.group(1))
            # return back the value we found
            return found.group(1)
    # all loops performed nothing found
    return None


if __name__ == '__main__':

    # capture the command line
    optiondict = kvutil.kv_parse_command_line( optiondictconfig, debug=False )

    # extract the values and put into variables
    debug    = optiondict['debug']
    AppVersion = optiondict['AppVersion']
    srchstring = optiondict['srchstring']

    if storelist in optiondict:
        winereq_storelist = [optiondict['storelist']]
    else:
        # (winerequest) request stores
        winereq_storelist = [
            'winex',
            'napacab',
            'webwine',
            'wineconn',
            'johnpete',
            'klwine',
            'nhliquor',
            'rolf',
        ]

    # read in the wines defined
    wines = get_wines_from_stores( [srchstring], winereq_storelist, debug=debug )

    # display what we read
    print('winerequest:wines:', wines)
    

#eof
