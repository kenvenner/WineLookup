'''
@author:   Ken Venner
@contact:  ken@venerllc.com
@version:  1.07

Read a series of CSV files created through Postgres SQL queries
and create the resulting output files

'''

import kvutil
import kvcsv
import kvgmailsend

import time
import re
import datetime
import sys
from socket import gethostname

# application variables
optiondictconfig = {
    'AppVersion' : {
        'value' : '1.07',
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
    'email_user' : {
        'value' : 'wines@vennerllc.com',
        'description' : 'defines the mail account we are sending from',
    },
    'email_password' : {
        'value' : None,
        'description' : 'defines the password for the mail account',
    },
    'email_type' : {
        'value' : 'text',
        'description' : 'defines the email type (text or html)',
    },
    'email_to' : {
        'value' : ['ken@vennerllc.com'],
        'type'  : 'liststr',
        'description' : 'defines the list of email accounts we send this report to',
    },
    'email_subject' : {
        'value' : None,
        'description' : 'defines the subject line of the email generated',
    },
    'nomail' : {
        'value' : False,
        'type'  : 'bool',
        'description' : 'defines if we should send out the email',
    },
    'winestoreproximity' : {
        'value' : None,
        'description' : 'defines the csv containing min winestore counts',
    },

}



def load_and_process_files_winetoday( in_stores='winerpt_stores.csv', in_base='winerpt_base.csv', in_collection='collection.csv', in_summary='winerpt_summary.csv', out_today='winetoday.csv', debug=False ):

    # stores - used to order the columns of the pivot
    storeRecs, storeHeader = kvcsv.readcsv2list_with_header( in_stores )

    # create the data entries in the pivot
    baseRecs, baseHeader = kvcsv.readcsv2list_with_header( in_base )
    collectionRecs, collectionHeader, collectionDupCount = kvcsv.readcsv2dict_with_header( in_collection, ['wine_xref'] )
    summaryRecs, summaryHeader, summaryDupCount = kvcsv.readcsv2dict_with_header( in_summary, ['winedescr'] )

    # the columns we are creating in this report - left to right
    columns = ['process_date', 'winedescr', 'own', 'minpaid'] + [x['wine_store'] for x in storeRecs] + ['vintagelowprice', 'vintagelowstore', 'vintagelowdate', 'overlow', 'todaylowprice', 'todaylowstore', 'nonvintagelowprice', 'nonvintagelowstore', 'nonvintagewinename', 'status']


    # step through the base records and build up the hash that is the the output record
    records=[]
    newrecord={}
    lastWineDescr = 'Never Seen'
    # step through the file that is record per winedescr/wine_store/wine_name/process_date
    for rec in baseRecs:
        # new winedescr - so we create a new row
        if lastWineDescr != rec[baseHeader[0]]:
            lastWineDescr = rec[baseHeader[0]]
            # save the last row if we had populated it
            if newrecord:
                records.append(newrecord)
            # create a new blank row
            newrecord={}
            newrecord['winedescr'] = lastWineDescr
            newrecord['process_date'] = rec[baseHeader[2]]
            # if we have matching record in collections pull that data in
            if lastWineDescr in collectionRecs:
                if collectionRecs[lastWineDescr]['in_inv']:
                    newrecord['own'] = collectionRecs[lastWineDescr]['cnt']
                    newrecord['minpaid'] = collectionRecs[lastWineDescr]['price_min']

            # if we have matching record in summary pull that data in
            if lastWineDescr in summaryRecs:
                for fld in ['vintagelowprice', 'vintagelowstore', 'vintagelowdate', 'todaylowprice', 'todaylowstore', 'nonvintagelowprice', 'nonvintagelowstore', 'nonvintagewinename']:
                    newrecord[fld] = summaryRecs[lastWineDescr][fld]
                newrecord['overlow'] = float(newrecord['todaylowprice']) - float(newrecord['vintagelowprice']) 
                newrecord['status'] = summaryRecs[lastWineDescr]['dailychange']
                for fld2 in ('alltimechangem1', 'nvalltimechangem1', 'collchange'):
                    if summaryRecs[lastWineDescr][fld2]:
                        newrecord['status'] += '('+summaryRecs[lastWineDescr][fld2]+')'

        # capture the data associated with this winedescr/store/price
        newrecord[rec[baseHeader[1]]] = rec[baseHeader[4]]

    # output the resultant table
    kvcsv.writelist2csv( out_today, records, columns )


def load_and_process_files_change( in_summary='winerpt_summary.csv', out_change_csv='winerpt_change.csv', out_change_txt='winerpt_change.txt', out_change_html='winerpt_change.html', debug=False ):

    # read in the daily change reports - records in summary with field "dailychange" populated
    summaryRecs, summaryHeader = kvcsv.readcsv2list_with_header( in_summary )

    # email wines we want to pull out the followoing fields
    # process_date, winedescr, wine_price,    wine_store,    lastdate,     lastprice,       status
    #                          todaylowprice, todaylowstore, lastseendate, lastseenlowprice
    #
    # Status:
    #    dailychange	alltimechangem1	nvalltimechangem1
    columns = ['dailychange', 'process_date', 'winedescr', 'todaylowprice', 'todaylowstore', 'lastseendate', 'lastseenlowprice']
    records=[]
    newrecord={}
    for rec in summaryRecs:
        if rec['dailychange']:
            newrecord={}
            for fld in columns:
                newrecord[fld] = rec[fld]
            newrecord['status'] = rec['dailychange']
            for fld2 in ('alltimechangem1', 'nvalltimechangem1', 'collchange'):
                if rec[fld2]:
                    newrecord['status'] += '('+rec[fld2]+')'
            records.append(newrecord)

    columns.append('status')
    
    kvcsv.writelist2csv( out_change_csv, records, columns )

    htmlString = create_change_html( records, columns )
    with open(out_change_html, 'w') as t:
        t.write(htmlString)

    textString = create_change_text( records, columns )
    with open(out_change_txt, 'w') as t:
        t.write(textString)

    
    
# generate the TEXT document for the changes
def create_change_text( records, columns ):
    textString=''
    lastdailychange = ''
    threeDots = '.'*3
    # put out the columns
    for rec in records:
        if not rec['dailychange']:
            next
            
        if lastdailychange != rec['dailychange']:
            if lastdailychange:
                textString += '\n\n'
            textString += rec['dailychange'] + '\n'
            lastdailychange =  rec['dailychange']

        if len( rec['winedescr']) > 30:
            rptWineDescr = rec['winedescr'][:27] + threeDots
        else:
            rptWineDescr = rec['winedescr']
        
        textString += '{:>10} {:<30} {:>9} {:<12} {:>10} {:>9} {:<15}\n'.format(rec['process_date'],rptWineDescr,rec['todaylowprice'],rec['todaylowstore'],rec['lastseendate'],rec['lastseenlowprice'],rec['status'])

    # print(textString)

    return textString


    
# generate the HTML document for the changes
def create_change_html( records, columns ):
    rightcolumns = ['todaylowprice', 'lastseenlowprice']
    nowrapcolumns = ['winedescr']
    headerstyle = ' style="height:50px"'
    headerformat = '<TR>\n<TD colspan="{}"{}>{}</TD>\n</TR>\n'
    # nowrapcolumns = []
    htmlString = '<TABLE>\n'

    #print('htmlString1:', htmlString)
    
    lastdailychange = ''
    # put out the columns
    for rec in records:
        if not rec['dailychange']:
            next
            
        if lastdailychange != rec['dailychange']:
            #if lastdailychange:
            lastdailychange =  rec['dailychange']
            htmlString += headerformat.format(len(columns)-1,headerstyle,rec['dailychange'])

            # header record for the table
            for col in columns:
                if col != 'dailychange':
                    htmlString += '<TH>'+col+'</TH>\n'
            htmlString += '</TR>\n'


        #print('htmlString2:', htmlString)

        # new row
        htmlString += '<TR>\n'
        for col in columns:
            if col != 'dailychange':
                if col in rightcolumns:
                    htmlString += '<TD style="text-align:right">'+rec[col]+'</TD>\n'
                elif col in nowrapcolumns:
                    htmlString += '<TD style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis">'+rec[col]+'</TD>\n'
                else:
                    htmlString += '<TD>'+rec[col]+'</TD>\n'
        htmlString += '</TR>\n'

    htmlString += '</TABLE>\n'
    
    # print(htmlString)

    return htmlString



def load_and_process_files_new( in_new='wineref.csv', out_new_txt='winerpt_new.txt', out_new_html='winerpt_new.html', debug=False ):

    # read in the list of new wines we have not categorized
    newRecs, newHeader = kvcsv.readcsv2list_with_header( in_new )

    # we get these fields
    # winedescr	date	search	company	wine	winesrt
    #
    # information we want to pull out the followoing fields
    # company	wine
    #

    # determine what fields we are using
    if newRecs:
        fldStore = fldWine = ''
        for fld in ('Store','company','wine_store'):
            if fld in newRecs[0].keys():
                fldStore = fld
                break
        if not fldStore:
            print('load_and_process_new:cannot determine the field for store:', newRecs[0].keys())
            sys.exit(1)

        for fld in ('Wine','wine','wine_name'):
            if fld in newRecs[0].keys():
                fldWine = fld
                break
        if not fldWine:
            print('load_and_process_new:cannot determine the field for name:', newRecs[0].keys())
            sys.exit(1)

    textFormat = '{:<12}|{}\n'
    textString = 'New Wines Found:\n'
    htmlFormat = '<TR>\n<TD>{}</TD>\n<TD>{}</TD>\n</TR>\n'
    htmlString = '''
New Wines Found:
'''
    # html table creation if there are records in the table
    if newRecs:
        htmlString += '''
<TABLE>
<TR><TH>Store</TH><TH>Wine</TH>
'''
    for rec in newRecs:
        textString += textFormat.format( rec[fldStore], rec[fldWine] )
        htmlString += htmlFormat.format( rec[fldStore], rec[fldWine] )

    # html table closure if there are records in the table
    if newRecs:
        htmlString += '</TABLE>\n'

    with open(out_new_html, 'w') as t:
        t.write(htmlString)

    with open(out_new_txt, 'w') as t:
        t.write(textString)



def load_and_process_files_notAvail( in_notAvail='winerpt_notavail.csv', out_notAvail_txt='winerpt_notavail.txt', out_notAvail_html='winerpt_notavail.html', debug=False ):

    # read in the list of notAvail wines we have not categorized
    notAvailRecs, notAvailHeader = kvcsv.readcsv2list_with_header( in_notAvail )

    # we get these fields
    # winedescr	process_date wine_price
    #
    # information we want to pull out the followoing fields
    # windescr, wine_price
    #

    textFormat = '{:<20}|{:>9}\n'
    textString = 'Wines No Longer Available:\n'
    htmlFormat = '<TR>\n<TD>{}</TD>\n<TD style="text-align:right">{}</TD>\n</TR>\n'
    htmlString = '''
Wines No Longer Available:
'''
    if notAvailRecs:
        htmlString += '''
<TABLE>
<TR><TH>Wine</TH><TH style="text-align:right">Prior-price</TH>
'''
    for rec in notAvailRecs:
        textString += textFormat.format( rec['winedescr'], rec['wine_price'] )
        htmlString += htmlFormat.format( rec['winedescr'], rec['wine_price'] )

    # html table closure if there are records in the table
    if notAvailRecs:
        htmlString += '</TABLE>\n'


    with open(out_notAvail_html, 'w') as t:
        t.write(htmlString)

    with open(out_notAvail_txt, 'w') as t:
        t.write(textString)



def load_and_process_files_missing_stores( in_store_cnt='winerpt_missing_stores.csv', in_store_reqts='winestoreproximity.csv', out_missingstores_txt='winerpt_missingstores.txt', out_missingstores_html='winerpt_missingstores.html', debug=False ):

    # read in the list of stores and count of found records
    inStoreCnt, inStoreCntHeader, inStoreDupCnt = kvcsv.readcsv2dict_with_header( in_store_cnt, ['wine_store'] )

    # read in the list of stores and minimum set of records
    inStoreReqt, inStoreRqtHeader = kvcsv.readcsv2list_with_header( in_store_reqts )

    # missing_store
    missing_store = []
    # step through the stores
    for store in inStoreReqt:
        if 'min_cnt' in store and store['min_cnt']:
            # if the store expects a minimum count - check to see if we got it
            if not store['wine_store'] in inStoreCnt or int(inStoreCnt[store['wine_store']]['count']) < int(store['min_cnt']):
                # no records, or insufficient records - so capture this as a missing store
                missing_store.append(store['wine_store'])

    # build up the strings that we will output
    textFormat = '{:<20}\n'
    textString = 'Wines Stores Missing:\n'
    htmlFormat = '<BR>{}\n'
    htmlString = '''
<B>Wines Stores Missing:</B>
'''
    for wine_store in missing_store:
        textString += textFormat.format( wine_store )
        htmlString += htmlFormat.format( wine_store )

    # html table closure if there are records in the table
    htmlString += '<BR><BR>\n'

    if not missing_store:
        textString = ''
        htmlString = ''
        
    with open(out_missingstores_html, 'w') as t:
        t.write(htmlString)

    with open(out_missingstores_txt, 'w') as t:
        t.write(textString)

        
        
def gen_email_body_html(in_change='winerpt_change.html', in_new='winerpt_new.html', in_notAvail='winerpt_notavail.html', in_missingstores='winerpt_missingstores.html'):
    # header
    email_body ='''
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "https://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="https://www.w3.org/1999/xhtml">
<head>
<title>Wine Report</title>
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
'''
    missing_stores = kvutil.slurp(in_missingstores)
    if missing_stores:
        email_body += missing_stores + '<BR><BR>\n'
    email_body += kvutil.slurp(in_change) + '<BR><BR>\n'
    email_body += kvutil.slurp(in_new) + '<BR><BR>\n'
    email_body += kvutil.slurp(in_notAvail)
    
    # close out
    email_body += '</BODY>\n</HTML>\n'

    return email_body


def gen_email_body_text(in_change='winerpt_change.txt', in_new='winerpt_new.txt', in_notAvail='winerpt_notavail.txt', in_missingstores='winerpt_missingstores.txt'):
    
    email_body = kvutil.slurp(in_missingstores)
    if email_body:
        email_body += '\n\n'
    email_body += kvutil.slurp(in_change)+ '\n\n'
    email_body += kvutil.slurp(in_new) + '\n\n'
    email_body += kvutil.slurp(in_notAvail)
    
    return email_body

# ---------------------------------------------------------------------------
if __name__ == '__main__':

    # capture the command line
    optiondict = kvutil.kv_parse_command_line( optiondictconfig, debug=False )

    # extract the values and put into variables
    test    = optiondict['test']
    AppVersion = optiondict['AppVersion']

    # test that we have email populated
    if not optiondict['nomail'] and not optiondict['email_password']:
        print('must provide email_password')
        sys.exit(1)
        
    # load and process the files
    results = load_and_process_files_winetoday( debug = False )

    # load and process the files
    results = load_and_process_files_change( debug = False )
    
    # load and process the files
    results = load_and_process_files_new( debug = False )
    
    # load and proces the files
    results = load_and_process_files_notAvail( debug = False )

    # load and proces the files
    results = load_and_process_files_missing_stores( debug = False )
    if optiondict['winestoreproximity']:
        results = load_and_process_files_missing_stores( in_store_reqts=optiondict['winestoreproximity'], debug = False )

    
    # final summary
    with open('email_body.html', 'w') as t:
        t.write(gen_email_body_html())
    
    # setup the email sender
    if not optiondict['nomail']:
        m = kvgmailsend.GmailSend(optiondict['email_user'], optiondict['email_password'])

        m.addRecipients(optiondict['email_to'])
        if optiondict['email_subject']:
            m.setSubject('wine_rpt.py (v' + optiondict['AppVersion'] + ') run at ' + str(datetime.datetime.now()) + ' from [' + str(gethostname()) + '] ' + optiondict['email_subject'])
        else:
            m.setSubject('wine_rpt.py (v' + optiondict['AppVersion'] + ') run at ' + str(datetime.datetime.now()) + ' from [' + str(gethostname()) + ']')
        #m.setTextBody(gen_email_body_text())
        m.setHtmlBody(gen_email_body_html())
        m.addAttachment('winetoday.csv')
        m.send()
    
    
