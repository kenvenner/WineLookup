import sys
import re
import winerequest

inputfile = 'HiddenVine_debug20180925.html'

create_def = ['hiddenvine','napacab','webwine','wineconn','wineexchange','lawineco','acwine','johnpete','wine2020']

selenium_store  = ['winehouse']

custom = ['acwine'] # need to go into two pages for every wine - price is on a 2nd page

# full definition of a store
store_args = winerequest.store_definitions()


store='winex'
store='napacab'
store='webwine'
store='wineconn'
store='johnpete'
store='klwine'
store='nhliquor'
# store='wine2020' # not an option - requires selenium
    
srch_string_store = {
    'hiddenvine' : 'pride',
    'winex'      : 'cakebread',
    'winehouse'  : 'cakebread',
    'napacab'    : 'cakebread',
    'webwine'    : 'cakebread',
    'wineconn'   : 'cakebread',
    'wine2020'   : 'veuve',
    'johnpete'   : 'cakebread',
    'klwine'     : 'groth',
    'nhliquor'   : 'groth',
}

debuglocal = True

if store == 'nhliquor':
    results = winerequest.nhliquor_wine_searcher( srch_string_store[store], debug=True )
else:

    # full test of the generic features
    content = winerequest.generic_wine_content_searcher( srch_string_store[store], **store_args[store]['search_args'] )

    # debugging
    if False:
        print(type(content))
        print('-'*80)
        print(content)
        print('-'*80)
        print('-'*80)

    # debugging
    if debuglocal: print('content:\n', content)

    # bust the file into lines
    file_list = winerequest.generic_wine_splitter( content, **store_args[store]['splitter_args'] )

    # debugging
    if debuglocal: print('file_list:\n', file_list)

    if True:
        i=0
        for line in file_list:
            print('%04d:%s' % ( i, file_list[i] ) )
            i += 1
        print('#'*80)
    # sys.exit(1)

    results = winerequest.generic_wine_parser(file_list, **store_args[store]['parser_args'], debug=True)

# final results
print('store:', store, ':srch_string:', srch_string_store[store], ':results:\n', results)

# we are done here - get out
sys.exit()


