'''
@author:   Ken Venner
@contact:  ken@venerllc.com
@version:  1.06

Tools used to process wine lookups via email
'''


import wineselenium
import winerequest
import kvcsv
import kvutil

import kvlogger
logger=kvlogger.getLogger(__name__)


from operator import itemgetter

# application variables
optiondictconfig = {
    'AppVersion' : {
        'value' : '1.05',
        'description' : 'defines the version number for the app',
    },
    'debug' : {
        'value' : False,
        'type'  : 'bool',
        'description' : 'defines if we are running in debug mode',
    },
    'subject_srchstring' : {
        'value' : 'cakebread chard res',
        'description' : 'defines the email subject line search string',
    },
}


# take in a list of dicts and output an HTML table (with or without header)
#     list2htmltbl - list of dicts
#     dictkeys - list - optional - the keys to extract and put into the table
#     tblheader - bool - optional - defines if table has a header (default: False)
#     hdrnames - list - optional - header names instead of keys to be used in the header
#
# returns a string that is the HTML table from <table> through to </table>
#
def list2htmltbl( list2convert, dictkeys=None, tblheader=False, hdrnames=None, debug=False ):
    
    # get the keys from the dictionary keys in the first value itself
    if not dictkeys:
        dictkeys = list( list2convert[0].keys() )

    # set up the array that holds the lines of the table
    htmllist = []
    htmllist.append('<table>')

    # set hdrnames to dictkeys if not set
    if not hdrnames:
        hdrnames = dictkeys
        
    
    # get the hdrnames to have the right number of columns
    if len(hdrnames) < len(dictkeys):
        for i in range(len(hdrnames),len(dictkeys)):
            hdrnames.append(dictkeys[i])
            
    # set up the HTML header
    if tblheader:
        tblrow = '<tr>'
        for col in hdrnames:
            tblrow += '<td>%s</td>' % col
        htmllist.append( tblrow + '</tr>' )

    #print('header:', htmllist)
    # now do the body
    for row in list2convert:
        tblrow = '<tr>'
        for col in dictkeys:
            tblrow += '<td>%s</td>' % row[col]
        htmllist.append( tblrow + '</tr>' )
    #print('header:', htmllist)

    # end the table
    htmllist.append('</table>')

    # make a single string by putting all lines together
    return '\n'.join(htmllist)

# create a ranking based on the number of string that matched in the return result
# use to sort the list - lowest ranking value is the closest match / lowest cost record
#
# we are weighting words 10 and digits 5
#
def rank_records( list2rank, srchstring, namefld='wine_name', rankfld='search_hits', pricefld='wine_price', debug=False ):

    srchwords = srchstring.lower().split()
    maxmatch = (len(srchwords)+1)*10
    for rec in list2rank:
        lowername = rec[namefld].lower()
        rec[rankfld] = maxmatch
        firstsearch = 2
        for srchword in srchwords:
            if srchword in lowername:
                if srchword.isdigit():
                    rec[rankfld] -= 5 * firstsearch
                else:
                    rec[rankfld] -= 10 * firstsearch
            # set this to 1 to de-weight it
            firstsearch=1

        if pricefld:
            rec[rankfld] = int(rec[rankfld] * 10000.0 + float(rec[pricefld]))

#    a) set up local variables
#    b) get first word from this string (srchstring)
#    c) pass into wineselenium.get_wines as a single value array from srchstring, get back results
#    d) pass into winereq.get_wines
#    e) rank the returned records tied to srch_full
#    f) sort this list by rank order
#    g) generate HTML string
#
def html_body_from_email_subject(subject_srchstring, winesel_storelist, winereq_storelist, debug=False):

    # set up - we are defining what we are putting in the email
    if debug:
        dictkeys = ['wine_store','wine_name','wine_price','search_hits']
        hdrnames = ['Store','Wine','Price','Rank']
    else:
        dictkeys = ['wine_store','wine_name','wine_price']
        hdrnames = ['Store','Wine','Price']
        
    htmlbodytop = '<html><body>\n'
    htmlbodytop = '''
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "https://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="https://www.w3.org/1999/xhtml">
<head>
<title>Wine Lookup</title>
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
<meta http-equiv="X-UA-Compatible" content="IE=edge" />
<meta name="viewport" content="width=device-width, initial-scale=1.0 " />
<style>
table {
  border-collapse: collapse;
}

table, td, th {
  border: 1px solid black;
}
</style>
</head>
<body>
'''

    htmlbodybtm = '</body></html>\n'
    
    # get the first word from the search string
    srchstring = subject_srchstring.split()[0]

    # debugging
    logger.info('subject:%s', subject_srchstring)
    logger.info('srchstring:%s', srchstring)
    logger.info('winesel_storelist:%s', winesel_storelist)
    logger.info('winereq_storelist:%s', winereq_storelist)

    # create array to hold the search results
    found_wines = []
    # get information from Selenium wineries
    logger.info('calling wineselenium')
    found_wines.extend( wineselenium.get_wines_from_stores( [srchstring], winesel_storelist, debug=debug ) )
    # get information from the request wineries
    logger.info('calling winerequest')
    found_wines.extend( winerequest.get_wines_from_stores( [srchstring], winereq_storelist, debug=debug ) )

    # debugging
    if debug:
        print('found_wines:', found_wines)
        print('-'*80)

    # messaging
    logger.info('wine count to be ranked:%d', len(found_wines))

    # add ranking to the found records
    rank_records( found_wines, subject_srchstring )

    # create a sorted list based on the ranking
    sorted_wines = sorted(found_wines, key=itemgetter('search_hits'))

    # debugging
    if debug:
        print('dictkeys:', dictkeys)
        print('-'*80)
        print('ranked_wines:', found_wines)
        print('-'*80)
        print('sorted_wines:', sorted_wines)
        print('-'*80)

        kvcsv.writelist2csv( 'email.csv', found_wines, ['wine_name','wine_store', 'wine_price'] )
        print('check out:email.csv')
        with open( 'ken.html', 'w' ) as f:
            f.write(htmlbodytop)
            f.write('<title>SORTED</title>\n')
            f.write(list2htmltbl( sorted_wines, dictkeys, tblheader=True, hdrnames=hdrnames) )
            f.write('\n')
            f.write(htmlbodybtm)
        print('check out:ken.html - sorted')
        with open( 'ken2.html', 'w' ) as f:
            f.write(htmlbodytop)
            f.write('<title>UNSorted</title>\n')
            f.write(list2htmltbl( found_wines, dictkeys, tblheader=True, hdrnames=hdrnames) )
            f.write('\n')
            f.write(htmlbodybtm)
        print('check out:ken2.html - UNsorted')

    logger.debug('htmlbodytop:%s', htmlbodytop)
    logger.debug('list2htmltbl:%s', list2htmltbl( sorted_wines, dictkeys, tblheader=True, hdrnames=hdrnames) )
    logger.debug('htmlbodybtm:%s', htmlbodybtm)

    # return the html body
    return htmlbodytop + list2htmltbl( sorted_wines, dictkeys, tblheader=True, hdrnames=hdrnames) + '\n' + htmlbodybtm
    
if __name__ == '__main__':

    # capture the command line
    optiondict = kvutil.kv_parse_command_line( optiondictconfig, debug=False )

    # extract the values and put into variables
    debug    = optiondict['debug']
    AppVersion = optiondict['AppVersion']
    subject_srchstring = optiondict['subject_srchstring']

    # (wine) selenium stores
    winesel_storelist = [
#        'bevmo',
        'hitime',
        'pavillions',
        'totalwine',
        'wineclub',
        'wally',
    ]

    # (winerequest) request stores
    winereq_storelist = [
        'winex',
        'napacab',
        'webwine',
        'wineconn',
        'johnpete',
        'klwine',
        'nhliquor',
    ]

    # extract out the HTML table for the wines found
    htmlbody = html_body_from_email_subject(subject_srchstring, winesel_storelist, winereq_storelist, debug=debug)


    # show the body
    print('htmlbody:', htmlbody)
    
