'''
@author:   Ken Venner
@contact:  ken@venerllc.com
@version:  1.13

Read in a file of wine names and create consistent wine descriptions 
from these names.

'''


import kvutil
import kvcsv

import re
import sys
import shutil

# may comment out in the future
import pprint
pp = pprint.PrettyPrinter(indent=4)
ppFlag = False

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
    'verbose' : {
        'value' : 1,
        'type'  : 'int',
        'description' : 'defines the display level for print messages',
    },
    'setup_check' : {
        'value' : False,
        'type'  : 'bool',
        'description' : 'defines if we checking out setup',
    },
    'pprint' : {
        'value' : False,
        'type'  : 'bool',
        'description' : 'defines if we output with pretty print when debugging',
    },
    'csvfile_master_in' : {
        'value' : 'wine_xref.csv',
        'description' : 'defines the name of the master data input file',
    },
    'csvfile_update_in' : {
        'value' : 'wineref.csv',
        'description' : 'defines the name of the input file to updated',
    },
    'csvfile_update_out' : {
        'value' : 'wineref2.csv',
        'description' : 'defines the name of the updated output file',
    },
    'fldWine' : {
        'value' : 'wine',
        'description' : 'defines the name of the field that holds the Wine ',
    },
    'fldWineDescr' : {
        'value' : 'winedescr',
        'description' : 'defines the name of the field holding the wine description',
    },
    'fldWineDescrNew' : {
        'value' : 'winedescrnew',
        'description' : 'defines the name of the NEW field holding the new description ',
    },
    'fldWineDescrMatch' : {
        'value' : None,
        'description' : 'defines the name of the NEW field holding the results of comparison existing to new description ',
    },
    'fldWineMaster' : {
        'value' : None,
        'description' : 'defines the name of the field that holds the Wine when reading the master file ',
    },
    'fldWineDescrMaster' : {
        'value' : None,
        'description' : 'defines the name of the field holding the wine description when reading the master file',
    },
    'backupfile_ext' : {
        'value' : '.bak',
        'description' : 'defines the extension to use to copy the update input file to if we are replacing it with output',
    },
    'defaultnew' : {
        'value' : None,
        'description' : 'defines if we should take field fldWineDescrNew and set to a value if not set',
    },
}

### GLOBAL VARIABLES / LOOKUPS  ########################################

# regex search for vintage in wine name
vintageLookup = (
    re.compile('\d\d\d\d\s+\d\d(\d\d)'),   # two years together - get this one over early
    re.compile('^\d\d(\d\d)'),  # four position start of line
    re.compile('\s\d\d(\d\d)$'),  # four position end of line
    re.compile('\s\d\d(\d\d)\s'),  # four position middle of line
    re.compile('XX\d\d(\d\d)\s'),  # four position middle of line
    re.compile('\s\d\d(\d\d)\/'),  # four position split
    re.compile('\s\'?(\d\d)\'?$|\s\'?(\d\d)\'?\s'),  #  two position date with optional apostrophe front or back
)

# regex search for case in wine name
reCase = re.compile(r'12\s*X\s*750\s*ML|\bcase\b|12\/750\s*ML',re.IGNORECASE)

# regex to pick up qualifiers from the wine
reQualLookup = (
    (None, re.compile(r'\bWithout\s+Gift\b|\bNo\s+Gift', re.IGNORECASE)),  # the none gift do them first
    ('Gift', re.compile(r'\bGift\b', re.IGNORECASE)),
    ('VAP', re.compile(r'\bVAP\b', re.IGNORECASE)),
    ('VAP', re.compile(r'\bGlassVAP\b', re.IGNORECASE)),
    ('Glass', re.compile(r'\bGlass\b', re.IGNORECASE)),
    ('Glass', re.compile(r'\bGlasses\b', re.IGNORECASE)),
    ('Etch', re.compile(r'\bEtch\b', re.IGNORECASE)),
    ('Basket', re.compile(r'\bBasket\b', re.IGNORECASE)),
)


# regex search to define the size of the wine bottle
sizeLookup = (
    ('1.75L', re.compile(r'\b1\.75\s*Li?|\b1\.75$', re.IGNORECASE)),
    ('1.5L', re.compile(r'\b1\.5\s*L?\b|\bMagnum\b', re.IGNORECASE)),
    ('375mL', re.compile(r'Half\s+Bottle|375ml', re.IGNORECASE)),
    ('200mL', re.compile(r'\b200\s*ML|\(200\s*ML', re.IGNORECASE)),
    ('50mL', re.compile(r'\b50\s*ML|\(50\s*ML', re.IGNORECASE)),
    ('500mL', re.compile(r'\b500\s*ML|\(500\s*ML', re.IGNORECASE)),
    ('3L', re.compile(r'\b3\s*Li?', re.IGNORECASE)),
    ('6L', re.compile(r'\b6\s*Li?', re.IGNORECASE)),
    ('9L', re.compile(r'\b9\s*Li?', re.IGNORECASE)),
    ('1L', re.compile(r'\b1L\b|\b1\s+L$|\b1.0\s*L\b|\b1\s+Liter\b|\bOne\s+Liter\b|\bLITER\b|\b1\s*LTR', re.IGNORECASE)),
)


# regex extract winery names from the wine field
wineryLookup = (
    ('Alban', re.compile(r'\bAlban\b', re.IGNORECASE)),
    ('Arrowood', re.compile(r'\bArrowood\b', re.IGNORECASE)),
    ('Atalon', re.compile(r'\bAtalon\b', re.IGNORECASE)),
    ('Attune', re.compile(r'\bAttune\b', re.IGNORECASE)),
    ('Auteur', re.compile(r'\bAuteur\b', re.IGNORECASE)),
    ('Austin Hope', re.compile(r'\bAustin\s+Hope\b', re.IGNORECASE)),
    ('Badge', re.compile(r'\bBadge\b', re.IGNORECASE)),
    ('Balletto', re.compile(r'\bBalletto\b', re.IGNORECASE)),
    ('Bell', re.compile(r'\bBell\s+Cellar', re.IGNORECASE)),
    ('BR Cohn', re.compile(r'\bB\.?\s?R\.?\s+Cohn\b', re.IGNORECASE)),
    ('Bremer', re.compile(r'\bBremer\b', re.IGNORECASE)),
    ('Brewer-Clifton', re.compile(r'\bBrewer[\s\-]Clifton\b', re.IGNORECASE)),
    ('BV', re.compile(r'\bBeaulieu\s+V|\bBV\b', re.IGNORECASE)),
    ('Belle Glos', re.compile(r'\bBelle\s+Glos\b', re.IGNORECASE)),
    ('Bennett Ln', re.compile(r'\bBennet+\sLane\b', re.IGNORECASE)),
    ('Benovia', re.compile(r'\bBenovia\b', re.IGNORECASE)),
    ('Beringer', re.compile(r'\bBeringer\b', re.IGNORECASE)),
    ('Blackstone', re.compile(r'\bBlackstone\b', re.IGNORECASE)),
    ('Brancott', re.compile(r'\bBrancott\b', re.IGNORECASE)),
    ('Cade', re.compile(r'\bCade\b', re.IGNORECASE)),
    ('Cain Five', re.compile(r'\bCain\s+Five\b|\bCain\s-\sFive\b|\bCain\s5\b|\bCainFive\b', re.IGNORECASE)),
    ('Cakebread', re.compile(r'\bCakebread\b', re.IGNORECASE)),
    ('Cardinale', re.compile(r'\bCardinale\b', re.IGNORECASE)),
    ('Caymus', re.compile(r'\bCaymus\b', re.IGNORECASE)),
    ('Chappellet', re.compile(r'\bChappellet\b', re.IGNORECASE)),
    ('Chalk Hill', re.compile(r'\bChalk\s+Hill\b', re.IGNORECASE)),
    ('Clos Du Bois', re.compile(r'\bClos\s+Du\s+Bois\b', re.IGNORECASE)),
    ('ClosDuVal', re.compile(r'\bClos\s+du\s+Val\b', re.IGNORECASE)),
    ('Colgin', re.compile(r'\bColgin\b', re.IGNORECASE)),
    ('Concha Don Melchor', re.compile(r'\bConcha\s.*Don\s+Melchor\b|Don\s+Melchor\b', re.IGNORECASE)),
    ('Continuum', re.compile(r'\bContinuum\b', re.IGNORECASE)),
    ('Corison', re.compile(r'\bCorison\b', re.IGNORECASE)),
    ('Cristal', re.compile(r'Roederer\s?.*Cristal\b|\bCristal\b.+Brut', re.IGNORECASE)),
    ('Curran', re.compile(r'\bCurran\b', re.IGNORECASE)),
    ('Darioush', re.compile(r'\bDarioush\b', re.IGNORECASE)),
    ('Darioush', re.compile(r'\bCaravan\b', re.IGNORECASE)),
    ('David Arthur', re.compile(r'\bDavid\s+Arthur\b', re.IGNORECASE)),
    ('David Bruce', re.compile(r'\bDavid\s+Bruce\b', re.IGNORECASE)),
    ('Davis Family', re.compile(r'\bDavis\s+Family\b', re.IGNORECASE)),
    ('Del Dotto', re.compile(r'\bDel\s+Dotto\b', re.IGNORECASE)),
    ('Dominus', re.compile(r'\bDominus\b', re.IGNORECASE)),
    ('Goldeneye', re.compile(r'\bGoldeneye\b', re.IGNORECASE)),  # before duckhorn
    ('Paraduxx', re.compile(r'\bParaduxx\b', re.IGNORECASE)),  # before duckhorn
    ('Domaine Carneros', re.compile(r'\bDomaine\s+Carneros\b', re.IGNORECASE)),
    ('Dominus', re.compile(r'\Dominus\b', re.IGNORECASE)),
    ('Drappier', re.compile(r'\bDrappier\b', re.IGNORECASE)),
    ('Duckhorn', re.compile(r'\bDuckhorn\b', re.IGNORECASE)),
    ('Dumol', re.compile(r'\bDumol\b', re.IGNORECASE)),
    ('Dunn', re.compile(r'\bDunn\b', re.IGNORECASE)),
    ('Ehlers', re.compile(r'\bEhlers\b', re.IGNORECASE)),
    ('Etude', re.compile(r'\bEtude\b', re.IGNORECASE)),
    ('Far Niente', re.compile(r'\bFar Niente\b', re.IGNORECASE)),
    ('Flora', re.compile(r'\bFlora\s+Springs\b', re.IGNORECASE)),
    ('Flowers', re.compile(r'\bFlowers\b', re.IGNORECASE)), 
    ('Robert Foley', re.compile(r'\bRobert\s+\bFoley\b', re.IGNORECASE)),   #before Foley
    ('Foley', re.compile(r'\bFoley\b', re.IGNORECASE)), 
    ('Foxen', re.compile(r'\bFoxen\b', re.IGNORECASE)),
    ('Franciscan', re.compile(r'\bFranciscan\b', re.IGNORECASE)),
    ('Frank Family', re.compile(r'\bFrank Family\b', re.IGNORECASE)),
    ('Gary Farrell', re.compile(r'\bGary\s+Farrel+\b', re.IGNORECASE)),
    ('Ghost Block', re.compile(r'\bGhost\s+Block\b', re.IGNORECASE)),
    ('Grgich', re.compile(r'\bGrgich\b', re.IGNORECASE)),
    ('Groth', re.compile(r'\bGroth\b', re.IGNORECASE)),
    ('Gundlach', re.compile(r'\bGundlach\b', re.IGNORECASE)),
    ('Hansel', re.compile(r'\bHansel\b', re.IGNORECASE)),
    ('Hanzell', re.compile(r'\bHanzell\b', re.IGNORECASE)),
    ('Hess', re.compile(r'\bHess\b', re.IGNORECASE)),
    ('Hewitt', re.compile(r'\bHewitt\b', re.IGNORECASE)),
    ('Hobbs', re.compile(r'\bHobbs\b|\bcrossbarn\b', re.IGNORECASE)),
    ('Hundred Acre', re.compile(r'\bHundred\s+Acre\b', re.IGNORECASE)),
    ('Jordan', re.compile(r'\bJordan\b', re.IGNORECASE)),
    ('Justin', re.compile(r'\bJustin\b', re.IGNORECASE)),
    ('Kim Crawford', re.compile(r'\bKim\s+Crawford\b', re.IGNORECASE)),
    ('Kistler', re.compile(r'\bKistler\b', re.IGNORECASE)),
    ('Kosta', re.compile(r'\bKosta\s+Browne?\b', re.IGNORECASE)),
    ('Krug', re.compile(r'\bKrug\b', re.IGNORECASE)),
    ('Kunde', re.compile(r'\bKunde\b', re.IGNORECASE)),
    ('LaCrema', re.compile(r'\bLa\s?Crema\b', re.IGNORECASE)),
    ('Lewis', re.compile(r'\bLewis\b', re.IGNORECASE)),
    ('Lokoya', re.compile(r'\bLokoya\b', re.IGNORECASE)),
    ('Meiomi', re.compile(r'\bMeiomi\b', re.IGNORECASE)),
    ('Melville', re.compile(r'\bMelville\b', re.IGNORECASE)),
    ('Momento Mori', re.compile(r'\bMomento\s+Mori\b', re.IGNORECASE)),
    ('Mondavi', re.compile(r'\bMondavi\b', re.IGNORECASE)),
    ('Montelena', re.compile(r'\bMontelena\b', re.IGNORECASE)),
    ('Mt Veeder', re.compile(r'^Mount\s+Veeder\b|^Mt\.? Veeder\b|\d+\s+M[^t]*t\s+Veeder\b', re.IGNORECASE)),
    ('Newton', re.compile(r'\bNewton\b', re.IGNORECASE)),
    ('Nickel', re.compile(r'\bNickel\b', re.IGNORECASE)),
    ('Opus One', re.compile(r'\bOpus\s+One\b', re.IGNORECASE)),
    ('P Togni', re.compile(r'\bTogni\b', re.IGNORECASE)),
    ('Pahlmeyer Jayson', re.compile(r'\bJayson\b', re.IGNORECASE)),  # this before pahlmeyer
    ('Pahlmeyer', re.compile(r'\bPahlmeyer\b(?!\s*Jay)', re.IGNORECASE)),
    ('Papillon', re.compile(r'\bPapillon\b', re.IGNORECASE)),
    ('Patz', re.compile(r'\bPatz\b', re.IGNORECASE)),
    ('Phelps', re.compile(r'\bPhelps\b', re.IGNORECASE)),
    ('Plumpjack', re.compile(r'\bPlumpjack\b', re.IGNORECASE)),
    ('Pride', re.compile(r'\bPride\b', re.IGNORECASE)),
    ('Prisoner', re.compile(r'\bPrisoner\b', re.IGNORECASE)),
    ('Provenance', re.compile(r'\bProvenance\b', re.IGNORECASE)),
    ('R Sinskey', re.compile(r'\bSinskey\b', re.IGNORECASE)),
    ('Ramey', re.compile(r'\bRamey\b', re.IGNORECASE)),
    ('Revana', re.compile(r'\bRevana\b', re.IGNORECASE)),
    ('Raptor', re.compile(r'\bRaptor\s+Ridge\b', re.IGNORECASE)),
    ('Revana', re.compile(r'\bRevana\b', re.IGNORECASE)),
    ('Ridge', re.compile(r'\bRidge\b', re.IGNORECASE)),
    ('Robert Foley', re.compile(r'\bRobert\s+Foley\b', re.IGNORECASE)),
    ('Rombauer', re.compile(r'\bRombauer\b', re.IGNORECASE)),
    ('Rudd', re.compile(r'\bRudd\b', re.IGNORECASE)),
    ('Scarecrow', re.compile(r'\bScarecrow\b', re.IGNORECASE)),
    ('Sea Smoke', re.compile(r'\bSea\s+Smoke\b', re.IGNORECASE)),
    ('Seghesio', re.compile(r'\bSeghesio\b', re.IGNORECASE)),
    ('Shafer', re.compile(r'\bShafer\b', re.IGNORECASE)),
    ('Sherwin', re.compile(r'\bSherwin\b', re.IGNORECASE)),
    ('Silver Oak', re.compile(r'\bSilver\s+Oak\b', re.IGNORECASE)),
    ('Silverado', re.compile(r'\bSilverado\b', re.IGNORECASE)),
    ('Simi', re.compile(r'\bSimi\b', re.IGNORECASE)),
    ('Sonoma Cutrer', re.compile(r'\bCutrer\b', re.IGNORECASE)),
    ('Spottswoode', re.compile(r'\bSpottswoode\b', re.IGNORECASE)),
    ('Stag Leap', re.compile(r'\bStag.*\sLeap\b', re.IGNORECASE)),
    ('Sullivan', re.compile(r'\bSullivan\b', re.IGNORECASE)),
    ('Summerland', re.compile(r'\bSummerland\b', re.IGNORECASE)),
    ('Summers', re.compile(r'\bSummers\b', re.IGNORECASE)),
    ('Tantara', re.compile(r'\bTantara\b', re.IGNORECASE)),
    ('Turnbull', re.compile(r'\bTurnbull\b', re.IGNORECASE)),
    ('Veuve', re.compile(r'\bVeuve\b', re.IGNORECASE)),
    ('Viader', re.compile(r'\bViader\b', re.IGNORECASE)),
    ('Waterstone', re.compile(r'\bWaterstone\b', re.IGNORECASE)),
    ('Whitehall', re.compile(r'\bWhitehall\b', re.IGNORECASE)),
    ('Wm Selyem', re.compile(r'\bWilliams\s*\-?Selyem\b', re.IGNORECASE)),
    ('ZD', re.compile(r'\bZD\b', re.IGNORECASE)),
    ('Zaca', re.compile(r'\bZaca\b', re.IGNORECASE)),

    
    ('zBourbon Woodford Res', re.compile(r'\bWoodford\s+Reserve\b', re.IGNORECASE)),
    ('zBourbon Woodford Res', re.compile(r'\bWoodford\s+Rsv\b', re.IGNORECASE)),
    ('zCognac Courvoisier', re.compile(r'\bCourvoisier\b', re.IGNORECASE)),
    ('zCognac Hennessy', re.compile(r'\bHennesse?y\b', re.IGNORECASE)),
    ('zCognac Remy', re.compile(r'\bRemy\s+Martin\b|\bRemy\s+Louis', re.IGNORECASE)),
    ('zCointreau', re.compile(r'\bCointreau\b', re.IGNORECASE)),
    ('zGin Hendrick', re.compile(r'\bHendrick', re.IGNORECASE)),
    ('zGin Tanqueray', re.compile(r'\bTanqueray\b', re.IGNORECASE)),
    ('zRum Mt Gay', re.compile(r'\bMount\s+Gay\b|\bMt\s+Gay', re.IGNORECASE)),
    ('zRum Ron Zacapa', re.compile(r'\bRon\s+Zacapa\b', re.IGNORECASE)),
    ('zRye Hayden', re.compile(r'\bBasil\s+Hayden\b', re.IGNORECASE)),
    ('zSambuca', re.compile(r'\bSambuca\b', re.IGNORECASE)),
    ('zScotch Glenmorangie', re.compile(r'\bGlenmorangie\b', re.IGNORECASE)),
    ('zScotch Hibiki Harmony', re.compile(r'\bHibiki\s.*Harmony\b', re.IGNORECASE)),
    ('zScotch Hibiki', re.compile(r'\bHibiki\b(?!\s*Har)', re.IGNORECASE)),
    ('zScotch Macallan', re.compile(r'\bMacallan\b', re.IGNORECASE)),
    ('zTeq Campo Azul', re.compile(r'\bCampo\s+Azul\b', re.IGNORECASE)),
    ('zTeq Casamigos', re.compile(r'\bCasamigos\b', re.IGNORECASE)),
    ('zTeq Casino Azul', re.compile(r'\bCasino\s+Azul\b', re.IGNORECASE)),
    ('zTeq Clase Azul', re.compile(r'\bClase\s+Azul\b', re.IGNORECASE)),
    ('zTeq Cuervo', re.compile(r'\bJose\s+Cuervo\b|^Cuervo\b', re.IGNORECASE)),
    ('zTeq Don Julio', re.compile(r'\bDon\s+Julio\b', re.IGNORECASE)),
    ('zTeq Dos Artes', re.compile(r'\bDos\s+Artes\b|^Cuervo\b', re.IGNORECASE)),
    ('zTeq Gran Cava', re.compile(r'\bGran\s+Cava\b', re.IGNORECASE)),
    ('zTeq Herradura', re.compile(r'\bHerradura\b', re.IGNORECASE)),
    ('zTeq Loma Azul', re.compile(r'\bLoma\s+Azul\b', re.IGNORECASE)),
    ('zTeq Padre Azul', re.compile(r'\bPadre\s+Azul\b', re.IGNORECASE)),
    ('zTeq Partida', re.compile(r'\bPartida\b', re.IGNORECASE)),
    ('zTeq Patron', re.compile(r'\bPatron\b', re.IGNORECASE)),
    ('zTripleSec Gr Marnier', re.compile(r'\bGrand\s+Marnier\b', re.IGNORECASE)),
    ('zTripleSec Dekuyper', re.compile(r'\bDekuyper\b', re.IGNORECASE)),
    ('zTripleSec Hiram', re.compile(r'\bHiram\b', re.IGNORECASE)),
    ('zVodka Absolut', re.compile(r'\bAbsolut\b', re.IGNORECASE)),
    ('zVodka Skyy', re.compile(r'\bSkyy\b', re.IGNORECASE)),
    ('zVodka Tito', re.compile(r'\bTito', re.IGNORECASE)),
    ('zWhiskey Balvenie', re.compile(r'\bBalvenie\b', re.IGNORECASE)),
    ('zWhiskey J Walker', re.compile(r'\bJohn+ie\s+Walker\b', re.IGNORECASE)),
#    ('', re.compile(r'\b\b', re.IGNORECASE)),
)

# regex extract the grape from the wine fld
grapeLookup = (
    ('Cab Franc', re.compile(r'\bCabernet\s+Franc|\bCab\s+Franc', re.IGNORECASE)),  # before cab
    ('Cab', re.compile(r'\bCabernet\b|\sCS\s|\sCS$|\bCab\b', re.IGNORECASE)),
    ('Claret', re.compile(r'\bClaret\b', re.IGNORECASE)),
    ('Rose Pinot', re.compile(r'\bRose\b.*\bPinot\b|\bPinot\b.*\bRose\b', re.IGNORECASE)),
    ('Pinot', re.compile(r'\bPinot\b|\bPN\b|\bP\s+Noir\b', re.IGNORECASE)),
    ('Merlot', re.compile(r'\bMerlot\b|\bME\b', re.IGNORECASE)),
    ('Sauv Blanc', re.compile(r'\bSauvignon\s+Blanc\b|\bSB\b', re.IGNORECASE)),
    ('Sauv Blanc', re.compile(r'\bSauvignon\/Fume\s+Blanc\b', re.IGNORECASE)),
    ('Meritage', re.compile(r'\bMeritage\b', re.IGNORECASE)),
    ('Fume', re.compile(r'\bFume\b|\bFum&#233;', re.IGNORECASE)),
    ('Champagne', re.compile(r'\bChampagne\b', re.IGNORECASE)),
    ('Chard', re.compile(r'\bChar+d|\bCH\b', re.IGNORECASE)),
    ('Shiraz', re.compile(r'\bShiraz\b', re.IGNORECASE)),
    ('Syrah', re.compile(r'\bSyrah\b|\bSY\b',re.IGNORECASE)),
    ('Zin', re.compile(r'\bZinfandel\b|\bZIN\b|\bZN\b', re.IGNORECASE)),
    ('Rose', re.compile(r'\bRose\b|\bRos&#233;', re.IGNORECASE)),
    ('Sangiovese', re.compile(r'\Sangiovese\b', re.IGNORECASE)),
#    ('Brandy', re.compile(r'\bBrandy\b', re.IGNORECASE)),
    ('Gewurzt', re.compile(r'\bGew.rztraminer\b|\bGew&#252;rzt', re.IGNORECASE)),
    ('Malbec', re.compile(r'\bMalbec\b', re.IGNORECASE)),
    ('Viognier', re.compile(r'\bViognier\b', re.IGNORECASE)),
    ('Roussanne', re.compile(r'\bRoussanne\b', re.IGNORECASE)),
    ('Charbono', re.compile(r'\bCharbono\b', re.IGNORECASE)),
    ('PSirah', re.compile(r'\bPetite Sirah\b', re.IGNORECASE)),
    ('Cuvee', re.compile(r'\bCuvee\b', re.IGNORECASE)),
    ('Red', re.compile(r'\bRed\b|\bBordeaux\s+Blend\b', re.IGNORECASE)),
    ('Syrah-Cab', re.compile(r'\bSyrcab\b|\bsyrah[-\s\/]+cab', re.IGNORECASE)),
    ('Grenache', re.compile(r'\bGrenache\b', re.IGNORECASE)),   
    ('Tempranillo', re.compile(r'\bTempranillo\b', re.IGNORECASE)),
)

# wineries that we don't want to look up the grape on
ignoreGrapeLookup = {
    'Cristal' : ['Rose', None],
    'Domaine Carneros' : ['Brut', None],
    'Dominus' : [None],
    'Papillon' : None,
    'Paraduxx' : None,
    'Veuve' : None,
    'zCointreau' : None,
    'zGin Hendrick' : None,
    'zGin Tanqueray' : ['Ten', None],
    'zTripleSec Gr Marnier' : ['1880', '100th', 'Cent', 'Quin', None],
    'zTripleSec Dekuyper' : None,
    'zTripleSec Hiram' : None,
    'zVodka Skyy' : ['Citrus', None],
    'zVodka Tito' : None,
#    'Prisoner' : ['Cuttings', 'Red', 'Derange', 'Saldo', 'Blindfold', None],
}

# winery to wine lookup when no grape is found in the wine name
#
# extract the wine name from a winery - when a field does not have a grape lookup for the row
# the name looked up and found will be the name used
noGrapeLookup = {
    'Ehlers' : ['120-80'],  # matches an abbreviations - and matches fldWineDescr
    'Alban' : ['Pandora'],
    'BV' : ['Tapestry', 'Latour'],
    'Bennett Ln' : ['Maximus'],
    'Bremer' : ['Austintatious'],
    'Cain Five' : None,
    'Colgin' : ['Cariad', 'IX'],
    'Concha Don Melchor' : None,
    'Continuum' : None,
    'Darioush' : ['Duel', 'Darius'],
    'Duckhorn' : ['Discussion'],
    'Far Niente' : ['Dolce'],
    'Flora' : ['Trilogy'],
    'Franciscan' : ['Magnificat'],
    'Grgich' : ['Violetta'],
    'Gundlach' : ['Vintage Reserve'],
    'Justin' : ['Isosceles'],
    'Krug' : ['Generations'],
    'Mondavi' : ['Maestro'],
    'Newton' : ['Puzzle'],
    'Opus One' : None,
    'Phelps' : ['Insignia'],
    'Prisoner' : ['Cuttings', 'Derange', 'Saldo', 'Blindfold'],
    'Ridge' : ['Monte Bello'],
    'Robert Foley' : ['Griffin'],
    'Sullivan' : ['Coeur de Vigne'],
    'Zaca' : ['ZThree', 'ZCuvee'],
    'zCognac Courvoisier' : ['Napolean', 'VS', 'VSOP', 'XO'],
    'zCognac Hennessy' : ['Paradis', 'Richard', 'VS', 'VSOP', 'XO', 'Master'],
    'zCognac Remy' : ['1738', 'Louis XIII', 'VSOP', 'XO', 'VS'],
    'zRum Ron Zacapa' : ['23', 'Negra', 'XO'],
    'zRye Hayden' : ['Dark', 'Caribbean'],
    'zScotch Hibiki Harmony' : None,
#    'zScotch Hibiki' : ['Toki', '12', '17', '21', '30'],
    'zTeq Campo Azul' : ['Extra Anejo', 'Anejo', 'Blanco', 'Reposado'],
    'zTeq Casamigos' : ['Extra Anejo', 'Anejo', 'Blanco', 'Reposado'],
    'zTeq Casino Azul' : ['Extra Anejo', 'Anejo', 'Blanco', 'Reposado', 'Silver'],
    'zTeq Clase Azul' : ['Ultra', 'Extra Anejo', 'Anejo', 'Blanco', 'Reposado', 'Mezcal', 'Plata', 'Platino'],
    'zTeq Dos Artes' : ['Extra Anejo'],
    'zTeq Gran Cava' : ['Extra Anejo'],
    'zTeq Loma Azul' : ['Extra Anejo', 'Anejo', 'Blanco', 'Reposado'],
#    'zTeq Padre Azul' : ['Extra Anejo', 'Anejo', 'Blanco', 'Reposado'],
    'zTeq Partida' : ['Blanco', 'Elegante'],
    'zVodka Absolut' : ['Citron', 'Mandarin', 'Mandrin', 'Mango', 'Ruby', 'Vanilia', 'Raspberri', 'Grapevine', None],
    'zWhiskey J Walker' : ['Double Black', 'Black', 'Blue', 'Gold', 'Green', 'Platinum', 'Red','Swing', 'White', '18', '21'],
}


# regex to use to determine if this is a liquor not a wine
#
# winery -> [ liquor, regex ]
# if there is no grape, and no noGrapeLookup found, but the winery has a liquorLookup
# use the list of lookups to find the additional infomratoin to add to the winery
#
liquorLookup = {
    'zRum Mt Gay' : [
        ('1703 Mst', re.compile(r'\b1703\b', re.IGNORECASE)),
        ('BB', re.compile(r'\bBlack Barrel\b', re.IGNORECASE)),
        ('Eclipse Silver', re.compile(r'\bEclipse\s+Silver\b', re.IGNORECASE)),
        ('Eclipse', re.compile(r'\bEclipse\b', re.IGNORECASE)),
        ('Old Peat', re.compile(r'\bOld Peat', re.IGNORECASE)),
        ('Old Pot', re.compile(r'\bPot\s+Still\b', re.IGNORECASE)),
        ('Old', re.compile(r'\bOld\b', re.IGNORECASE)),
        ('Silver', re.compile(r'\bSilver\b', re.IGNORECASE)),
        ('XO Peat', re.compile(r'\bXO\b', re.IGNORECASE)),
    ],
    'zScotch Glenmorangie' : [
        ('10', re.compile(r'\b10(YR)?\b', re.IGNORECASE)),
        ('14 Port', re.compile(r'14.+\bQuinta\b|14.+\bPort\b|\bQuinta\b.+14|\bPort\b.+14', re.IGNORECASE)),
        ('12 Bacalta', re.compile(r'\bBacalta\b', re.IGNORECASE)),
        ('12 Burgundy', re.compile(r'\bBurgundy\b', re.IGNORECASE)),
        ('12 Nectar', re.compile(r'\bNectar\b', re.IGNORECASE)),
        ('12 Port', re.compile(r'\bQuinta\b|\bPort\b', re.IGNORECASE)),
        ('12 Sherry', re.compile(r'\bLa\s?Santa\b|\bSherry\b', re.IGNORECASE)),
        ('12 Signet', re.compile(r'\bSignet\b', re.IGNORECASE)),
        ('15 Cadboll', re.compile(r'\bCadboll', re.IGNORECASE)),
        ('15', re.compile(r'\b15(YR)?\b', re.IGNORECASE)),
        ('18', re.compile(r'\b18(YR)?\b|\b18YEAR\b', re.IGNORECASE)),
        ('25 Astar', re.compile(r'\bAstar\b', re.IGNORECASE)),
        ('25', re.compile(r'\b25(YR)?\b', re.IGNORECASE)),
        ('Companta', re.compile(r'\bCompanta\b', re.IGNORECASE)),
        ('Finealta', re.compile(r'\bFinealta\b', re.IGNORECASE)),
        ('Milsean', re.compile(r'\bMilsean\b', re.IGNORECASE)),
        ('Sonnalta', re.compile(r'\bSonnalta\b', re.IGNORECASE)),
    ],
    'zScotch Macallan' : [
        ('10 Fine', re.compile(r'\bFine.*\b10\b|\b10.*Fine')),
        ('10', re.compile(r'\b10\b')),
        ('12 Double Gold', re.compile(r'\bDbl\b.*Gold|\bDouble\b.*Gold', re.IGNORECASE)),
        ('12 Double', re.compile(r'\bDouble\s.*12(YR)?\b', re.IGNORECASE)),
        ('12 Double', re.compile(r'\b12\s.*Double\b', re.IGNORECASE)),
        ('12 Double', re.compile(r'\bDbl\b|\bDouble\b', re.IGNORECASE)),
        ('12 Edition 1', re.compile(r'\bEdition\s.*1\b', re.IGNORECASE)),
        ('12 Edition 2', re.compile(r'\bEdition\s.*2\b', re.IGNORECASE)),
        ('12 Edition 3', re.compile(r'\bEdition\s.*3\b', re.IGNORECASE)),
        ('12 Edition 4', re.compile(r'\bEdition\s.*4\b', re.IGNORECASE)),
        ('12 Sherry', re.compile(r'\b12\s.*Sherry\b|\bSherry\b\s.*\b12', re.IGNORECASE)),
        ('12 Triple', re.compile(r'\b12(YR)?\s.*Triple\b', re.IGNORECASE)),
        ('12 Triple', re.compile(r'\bTriple\s.*12\b', re.IGNORECASE)),
        ('12', re.compile(r'\b12(YR)?\b', re.IGNORECASE)),
        ('15 Triple', re.compile(r'\b15(YR)?\s.*Triple\b|Triple.+\b15(YR)?\b', re.IGNORECASE)),
        ('15 Fine', re.compile(r'\b15(YR)?\b.*\bFine\b', re.IGNORECASE)),
        ('15', re.compile(r'\b15(YR)?\b', re.IGNORECASE)),
        ('17 Sherry', re.compile(r'\b17(YR)?\s.*Sherry\b', re.IGNORECASE)),
        ('17 Fine', re.compile(r'\b17(YR)?\b.*\bFine\b', re.IGNORECASE)),
        ('17', re.compile(r'\b17(YR)?\b', re.IGNORECASE)),
        ('18 Sherry', re.compile(r'\b18(YR)?\s.*Sherry\b|Sherry\b.*18', re.IGNORECASE)),
        ('18 Triple', re.compile(r'\b18(YR)?\s.*Triple\b|Triple.+\b18(YR)?\b', re.IGNORECASE)),
        ('18 Fine', re.compile(r'\b18(YR)?\b.*\bFine\b', re.IGNORECASE)),
        ('18 Gran', re.compile(r'Gran\b.*\b18', re.IGNORECASE)),
        ('18', re.compile(r'\b18(YR)?\b', re.IGNORECASE)),
        ('21 Fine', re.compile(r'\b21.*Fine\b', re.IGNORECASE)),
        ('21', re.compile(r'\b21(YR)?\b', re.IGNORECASE)),
        ('25 Sherry', re.compile(r'\b25\s.*Sherry\b', re.IGNORECASE)),
        ('25', re.compile(r'\b25(YR)?\b')),
        ('30 Sherry', re.compile(r'\b30\s.*Sherry', re.IGNORECASE)),
        ('30 Triple', re.compile(r'\b30(YR)?\s.*Triple\b|Triple.+\b30(YR)?\b', re.IGNORECASE)),
        ('30 Fine', re.compile(r'\b30(YR)?\b.*\bFine\b|Fine.*30', re.IGNORECASE)),
        ('30', re.compile(r'\b30(YR)?\b')),
        ('Rare', re.compile(r'\bRare\b', re.IGNORECASE)),
    ],
    'zTeq Cuervo' : [
        ('Especial Gold', re.compile(r'\bEspecial\b.*Gold\b|Gold.*Especial', re.IGNORECASE)),
        ('Especial Blue', re.compile(r'\bEspecial\b.*Blue\b', re.IGNORECASE)),
        ('Especial', re.compile(r'\bEspecial\b', re.IGNORECASE)),
        ('Familia Platino', re.compile(r'\bPlatino\b', re.IGNORECASE)),
        ('Familia Anejo', re.compile(r'\bFamilia\b|\bReserva\b', re.IGNORECASE)),
        ('Gold', re.compile(r'\bGold\b', re.IGNORECASE)),
        ('Reposado Lagavulin', re.compile(r'\bReposado.*Lagavulin', re.IGNORECASE)),
        ('Tradicional Anejo', re.compile(r'Tradicional.*Anejo|Anejo.*Tradicional', re.IGNORECASE)),
        ('Tradicional Reposado', re.compile(r'Tradicional.*Reposado|Reposado.*Tradicional', re.IGNORECASE)),
        ('Tradicional Silver', re.compile(r'\bTradicional\b', re.IGNORECASE)),
        ('Tradicional Silver', re.compile(r'\bTraditional\b', re.IGNORECASE)),
        ('Reposado', re.compile(r'\bReposado\b', re.IGNORECASE)),
        ('Silver', re.compile(r'\bSilver\b', re.IGNORECASE)),
    ],
    'zTeq Don Julio' : [
        ('1942', re.compile(r'\b1942\b', re.IGNORECASE)),
        ('Real', re.compile(r'\bReal\b', re.IGNORECASE)),
        ('Anejo Claro 70th', re.compile(r'\b70th\b', re.IGNORECASE)),
        ('Anejo Claro', re.compile(r'\bAnejo\b\s*Claro\b', re.IGNORECASE)),
        ('Anejo', re.compile(r'\bAnejo\b', re.IGNORECASE)),
        ('Blanco', re.compile(r'\bBlanco\b', re.IGNORECASE)),
        ('Reposado Lagavulin', re.compile(r'\bRepo.+Lagvulin\b', re.IGNORECASE)),
        ('Reposado Dbl', re.compile(r'\bReposado.+Double\b', re.IGNORECASE)),
        ('Reposado Dbl', re.compile(r'\bReposado.+Dbl\b', re.IGNORECASE)),
        ('Reposado Dbl', re.compile(r'\bDouble.+Reposado\b', re.IGNORECASE)),
        ('Reposado Private', re.compile(r'\bReposado.+Private\b', re.IGNORECASE)),
        ('Reposado', re.compile(r'\bReposado\b', re.IGNORECASE)),
        ('Silver', re.compile(r'\bSilver\b', re.IGNORECASE)),
    ],
    'zTeq Herradura' : [
        ('Ultra', re.compile(r'\bUltra\b', re.IGNORECASE)),
        ('Suprema', re.compile(r'\bSuprema\b', re.IGNORECASE)),
        ('Anejo', re.compile(r'\bAnejo\b', re.IGNORECASE)),
        ('Blanco', re.compile(r'\bBlanco\b', re.IGNORECASE)),
        ('Reposado Gold', re.compile(r'\bReposado\s+Gold\b|\bGold\s+Reposado\b', re.IGNORECASE)),
        ('Reposado Scotch', re.compile(r'\bReposado.+Scotch\b|\bScotch.+Reposado\b', re.IGNORECASE)),
        ('Reposado Port', re.compile(r'\bPort.+Reposado\b|\bReposado.+Port\b', re.IGNORECASE)),
        ('Reposado', re.compile(r'\bReposado\b', re.IGNORECASE)),
        ('Silver', re.compile(r'\bSilver\b', re.IGNORECASE)),
    ],
    'zTeq Patron' : [
        ('Gran Piedra', re.compile(r'\bPiedra\b', re.IGNORECASE)),
        ('DELETE Roca DELETE', re.compile(r'\bRoca\b', re.IGNORECASE)),
        ('Anejo Extra Lalique', re.compile(r'\bLalique\b', re.IGNORECASE)),
        ('Anejo Extra 7yr', re.compile(r'\b7YR\b|\b7 anos\b|\b7 year\b', re.IGNORECASE)),
        ('Anejo Extra 5yr', re.compile(r'\b5YR\b|\b5 anos\b|\b5 year\b', re.IGNORECASE)),
        ('Anejo Extra 10yr', re.compile(r'\b10\b.+\bExtra\b|\bExtra\b.+10', re.IGNORECASE)),
        ('Anejo Extra', re.compile(r'\bExtra\s+Anejo\b', re.IGNORECASE)),
        ('Gran Anejo', re.compile(r'\bGran\s+Anejo\b', re.IGNORECASE)),
        ('Gran Anejo', re.compile(r'\bBurdeos\b', re.IGNORECASE)),
        ('Gran Smoky', re.compile(r'\bGran\s+.*Smoky\b', re.IGNORECASE)),
        ('Anejo', re.compile(r'\bAnejo\b', re.IGNORECASE)),
        ('Gran Platinum', re.compile(r'\bPlatinum\b', re.IGNORECASE)),
        ('Reposado', re.compile(r'\bReposado\b', re.IGNORECASE)),
        ('Silver LTD', re.compile(r'\bSilver.*Limited\b|\bLimited.*Silver\b', re.IGNORECASE)),
        ('Silver Estate', re.compile(r'\bEstate.*Silver\b|\bSilver.*Estate\b', re.IGNORECASE)),
        ('Silver', re.compile(r'\bSilver\b', re.IGNORECASE)),
        ('Blanco', re.compile(r'\bBlanco\b', re.IGNORECASE)),
#        ('', re.compile(r'\b\b', re.IGNORECASE)),
    ],
    'zTeq Padre Azul' : [
        ('Blanco', re.compile(r'\bsilver\b', re.IGNORECASE)),
    ],
    'zWhiskey Balvenie' : [
        ('12 Double', re.compile(r'\bDouble.*12(YR)?\b', re.IGNORECASE)),
        ('12 Double', re.compile(r'\b12(YR)?\s.*Double', re.IGNORECASE)),
        ('12 First', re.compile(r'\b12(YR)?\s.*First', re.IGNORECASE)),
        ('12 USA', re.compile(r'\b12.*American|American.*12', re.IGNORECASE)),
        ('12 Toast', re.compile(r'\b12(YR)?\s.*Toast', re.IGNORECASE)),
        ('12', re.compile(r'\b12(YR)?\b', re.IGNORECASE)),
        ('14 Carib', re.compile(r'\b14(YR)?\s.*Carib', re.IGNORECASE)),
        ('14 Carib', re.compile(r'\b14(YR)?\s.*CB\s+Cask', re.IGNORECASE)),
        ('14 Carib', re.compile(r'\bCarr?ib', re.IGNORECASE)),
        ('14 Peat', re.compile(r'\b14(YR)?\s.*Peat', re.IGNORECASE)),
        ('15 Sherry', re.compile(r'\b15(YR)?\s.*Sherry\b', re.IGNORECASE)),
        ('15 Sherry', re.compile(r'\bSherry\s+.*15(YR)?\b', re.IGNORECASE)),
        ('15', re.compile(r'\b15(YR)?\b', re.IGNORECASE)),
        ('16 Triple', re.compile(r'\b16(YR)?\s.*Triple\b', re.IGNORECASE)),
        ('17 Sherry Double', re.compile(r'\b17(YR)?\s.*Sherry\s+Doub', re.IGNORECASE)),
        ('17 Sherry', re.compile(r'\b17(YR)?\s.*Sherry', re.IGNORECASE)),
        ('17 Double', re.compile(r'\b17(YR)?\s.*Double', re.IGNORECASE)),
        ('17 Double', re.compile(r'\bDouble.*17(YR)?\b', re.IGNORECASE)),
# 17 Double Sherry
# 17 Islay
# 17 New Oak
        ('17 Peat', re.compile(r'\b17(YR)?\s.*Peat', re.IGNORECASE)),
        ('17 Peat', re.compile(r'\bPeat.*17(YR)?\b', re.IGNORECASE)),
        ('17', re.compile(r'\b17(YR)?\b', re.IGNORECASE)),
        ('21 Port', re.compile(r'\b21.*Port', re.IGNORECASE)),
        ('21 Port', re.compile(r'\bPort.*21\b', re.IGNORECASE)),
        ('21', re.compile(r'21', re.IGNORECASE)),
        ('25', re.compile(r'\b25(YR)?\b', re.IGNORECASE)),
        ('30', re.compile(r'\b30(YR)?\b', re.IGNORECASE)),
        ('40', re.compile(r'\b40(YR)?\b', re.IGNORECASE)),
    ],
    'zBourbon Woodford Res' : [
        ('Dbl', re.compile(r'\bDouble\b', re.IGNORECASE)),
        ('Derby', re.compile(r'\bDerby\b', re.IGNORECASE)),
        ('Rye Choc', re.compile(r'\bChocolate.*Rye\b', re.IGNORECASE)),
        ('Rye', re.compile(r'\bRye\b', re.IGNORECASE)),
        ('Brandy', re.compile(r'\bBrandy\b', re.IGNORECASE)),
        ('Batch', re.compile(r'\bBatch\b', re.IGNORECASE)),
        ('Barrel', re.compile(r'\bBarrel\b', re.IGNORECASE)),
        ('Master', re.compile(r'\bMasters?\b', re.IGNORECASE)),
        ('Malt', re.compile(r'\bMalt\b', re.IGNORECASE)),
        ('Maple', re.compile(r'\bMaple\b', re.IGNORECASE)),
        ('Wheat', re.compile(r'\bWheat\b', re.IGNORECASE)),
        ('', re.compile(r'\bWoodford\b', re.IGNORECASE)),
    ],
    'zSambuca' : [
        ('Romana Black', re.compile(r'\bRomana.*\bBlack\b|\bBlack\s+Romana\b', re.IGNORECASE)),
        ('Romana', re.compile(r'\bRomana\b', re.IGNORECASE)),
        ('Di Amore', re.compile(r'\bdi Amore\b', re.IGNORECASE)),
    ],
    'zScotch Hibiki' : [
        ('12', re.compile(r'\b12\s*YE?A?R\b', re.IGNORECASE)),
        ('17 Limited', re.compile(r'\b17\s*YE?A?R\b.+Limited', re.IGNORECASE)),
        ('17', re.compile(r'\b17\s*YE?A?R\b', re.IGNORECASE)),
        ('21 Limited', re.compile(r'\b21\s*YE?A?R\b.+Limited', re.IGNORECASE)),
        ('21', re.compile(r'\b21\s*YE?A?R\b', re.IGNORECASE)),
        ('30', re.compile(r'\b30\s*YE?A?R\b', re.IGNORECASE)),
    ]
}
# regex to expand out optional values in the optoinal values to find a match against wine fld
wineAbbrLookup = {
    '120-80' : r'\bOne\s+Twenty\s+Over\s+Eighty\b',
    '3Amigos' : r'\bThree\s+Amigos\b',
    '3Palms' : r'\bThree\s+Palms\b',
    '3Sister' : r'\bThree\s+Sisters?\b',
    '4Barrell' : r'\b4[\-\s]Barrels?\b',
    'Alex' : r'\bAlexander\b',
    'And' : r'\bAnderson\b',
    'Car' : r'\bCarneros\b',
    'Carries' : r'\bCarrie',
    'CC' : r'\bC\.?C\.?\s+Ranch\b',
    'Clone4' : r'\bClone\s+4\b',
    'Clone6' : r'\bClone\s+6\b',
    'Crossbarn' : r'\bCross\s+Barn\b',
    'Donna' : r'\bDonna',
    'Est' : r'\bEstate\b',
    'Estate' : r'\bEst\b',
    'Gap' : r'\bGap|\s%27Gap',
    'Gary' : r'\bGary',
    'Julia' : r'\bJulia',
    'Knights' : r'\bKnight',
    'KistlerVnyd' : r'\bKistler (Vineyard|VYD|EST)\b',
    'LP' : r'\bLes Pierres\b',
    'Lyn' : r'\bLyndenhur?st\b',
    'Mont' : r'\bMonterey\b',
    'Mt'  : r'\bMount\b|\bMt\.\b',
    'Napa/Son' : r'\bNapa.*Son',
    'Oak' : r'\bOakville\b',
    'One-Pt-5' : r'\bOne\s+Point\s+Five\b',
    'Pomm' : r'\bPommeraie\b',
    'Priv' : r'\bPrivate\b',
    'RR' : r'\bRussian\s+Rivers?\b|RRV',
    'RRR' : r'\bRussian\s+Rivers?\b|RRV',
    'Res' : r'\bReserve\b|\bRsv\b|\bResrv\b|\bReserv\b|\bReserve$',
    'Rose' : r'\bRos&#233;|\bROS&EACUTE;|\bRos%E9',
    'Ruth' : r'\bRutherford\b',
    'Sandy' : r'\bSandy',
    'Samanthas' : r'\bSamantha',
    'SC' : r'\bSanta\s+Cruz\b',
    'SLD' : r'\bStag.*Leap\b',
    'SLH' : r'\bSanta\s+Lucia\b',
    'SMV' : r'\bSanta\s+Maria|\bS\s+Maria',
    'SRH' : r'\bSTA\.?|\bSANTA\s+Rita\b|\bSTA\sRITA\sHILLS|\bS\s+RITA\b',
    'SS' : r'\bSpecial\s+\Selection\b',
    'Stage' : r'\bStagecoach\b',
    'Son' : r'\bSonoma\b',
    'SYV' : r'\bSanta\s+Ynez\s+Valley\b',
    'TD9' : r'\bTD\s+9\b|\bTD-9\b',
    'Terraces' : r'\bTerrace',
    'TheCutrer' : r'\bThe Cutrer\b|nnay Cutrer\b',
    'Tok' : r'\bTo[\s\-]?Kolan|\bTo[\s\-]?Kalon',
    'Turn4' : r'\bTurn\s+4\b',
    'Vernas' : r'\bVerna',
    'Vine' : r'\bVines\b',
    'Yount' : r'\bYountville\b',
    'ZThree' : r'\bZ.*\bThree\b',
    'ZCuvee' : r'\bZ.*\bCuvee\b|\bCuvee Z\b',    

    # misspellings
    'Agustina' : r'\bAugustina\b',
    'Durell' : r'\bDurrell\b',
    'Benchland' : r'\bBenchlands\b',
    'Pritchard' : r'\bPitchard\b',
}

# regex search - set the ships as
reShipsAs = re.compile(r'\(ships?\s', re.IGNORECASE)

# the order in which we pull multiple single match attributes 
defaultorderlist=[['Tok'], ['Oak'], ['Res'], ['RR'], ['Landslide'], ['Yount'], ['RRR'], ['Son'], ['Ruth'], ['Napa'], ['Helena'], ['SRH'], ['SLH'], ['SMV'], ['SLD'], ['Paso'], ['Alex'], ['Single'], ['Estate']]
    
### FUNCTIONS ############################################

#########################################################################################
def globalVariableCheck( debug=False ):
    # check for liquor definitions that are in noGrapeLookup
    # these will never execute
    for liquor in liquorLookup:
        if liquor in noGrapeLookup:
            print('WARNING:liquorLookup regexs will never execute - they are in noGrapeLookup:', liquor)
        if liquor in ignoreGrapeLookup:
            print('WARNING:liquorLookup regexs will never execute - they are in ignoreGrapeLookup:', liquor)
    for winery in ignoreGrapeLookup:
        if winery in noGrapeLookup:
            print('WARNING:ignoreGrapeLookup regexs will never execute - they are in noGrapeLookup:', winery)
            
#########################################################################################
def setOptionDictMasterFldValues( optiondict, debug=False ):
    # default these fields to the fld values if they are not set
    # otherwise leave them alone
    for fld in ('fldWine', 'fldWineDescr'):
        if not optiondict[fld+'Master']:
            optiondict[fld+'Master'] = optiondict[fld]
            

#########################################################################################
# having a list of names to look at and match on - see if this record has a match
#     nameLookup - list of names could have 'None' as the last value, or just the value of None
#     lookupStr - string to be searched
#     other - array of strings that will have the matching name removed from
#     msg - string defining who called this function
#
# returns:  string - if a matching string is found
#           None - did not find a match
#           '' - valid match with "None"
#
def wineLookupByName( nameLookup, lookupStr, other, msg, wineAbbrLookup=None, debug=False ):

    # string for debugging messages
    funcname = 'wineLookupByName:' + msg + ':'

    # debugging
    if debug:  print(funcname + 'nameLookup:', nameLookup)
    
    # if the value for this winery is None - than there is no additiona work we are done
    if nameLookup is None:
        # no additional processing
        # debugging
        if debug:  print(funcname + 'match: value is none - continue on')
        # return empty string
        return ''

    
    # there are additional lookups for this winery - not using grape as part of the description
    # check each of the things to look up
    for name in nameLookup:
        # debugging
        if debug:  print(funcname + 'match-name:', name)
        
        # special processing of a lookup value of none
        if name is None:
            # Lookup on none - means just use what we found
            # debugging
            if debug:  print(funcname + 'name-matched:  value is none - continue on:pass back blank')
            # stop iterating on nameLookup - by returning empty string
            return ''

        # we have not encountered 'None' - so build the regex based on the text provided
        reName = re.compile( r'\b'+name+r'\b', re.IGNORECASE)

        # check to see if we have a match with this regex
        if reName.search(lookupStr):
            # we have a match - so this is the additional attribute we are looking for
            # debugging
            if debug:  print(funcname+'name-MATCHED:', name)
            # remove from other if it is in there
            for val in other:
                if reName.search(val):
                    other.remove(val)
                    # debugging
                    if debug: print(funcname + 'name-remove-from-other:', val)
            # stop iterating on nameLookup - return what we found
            return name

        # 2nd check see if have a translation and this name is translatable
        if wineAbbrLookup and name in wineAbbrLookup:
            # build the regex with the look up value
            reName = re.compile(wineAbbrLookup[name], re.IGNORECASE)
            # debugging
            if debug:  print(funcname + 'Abbr-match-name:', name)
            # check to see if we have a match with this regext
            if reName.search(lookupStr):
                # we have a match - so this is the additional attribute we are looking for
                # debugging
                if debug:  print(funcname+'Abbr-name-MATCHED:', wineAbbrLookup[name])
                # remove from other if it is in there
                for val in other:
                    if reName.search(val):
                        other.remove(val)
                        # debugging
                        if debug: print(funcname + 'name-remove-from-other:', val)
                # stop iterating on nameLookup - return what we found
                return name

    # checked all the namelookupd - and did not find any matches
    # debuging
    if debug:  print(funcname + 'name match not found:set to blank')
    # return none meaning we did not find a match
    return None


#########################################################################################
# find the qualifer like gift, etch, glass tied to this string
#
#     
#
#     returns:  first qualifier or None
#
def findQualifier( wine, debug=False ):
    for (val, reSearch) in reQualLookup:
        if reSearch.search(wine):
            if debug:  print('findQualifier:matched-returning:', val)
            return val

    if debug:  print('findQualifier:no-match-returning:', None)
    return None


#########################################################################################
# find the winery tied to the rec
#
#     Global Variable Used:  wineryLookup (an array of regex that define the winery)
#
#     returns:  (winery, reWinery)
#
def findWinery( rec, lastWinery, lastReWinery, fldWine, debug=False ):
    # if we had a prior winery - test for this match first
    if lastWinery:
        # debugging
        if debug:
            try:
                print('fw:new winery:', rec[fldWine])
            except Exception as e:
                print('debug error8-continuing:', str(e))
                print('rec[fldWine]:type:', type(rec[fldWine]))
                # print('fw:new winery:', rec[fldWine].decode('windows-1252'))
            print('fw:checking if this is lastWinery:', lastWinery)
        
        # check to see if the winery is a match again for this record
        if lastReWinery.search(rec[fldWine]):
            # debugging
            if debug:  print('fw:this matches the last winery')
            # match again - return values
            return(lastWinery, lastReWinery)
        else:
            # not match - debugging
            if debug:  print('fw:not last winery')

    # if we did not match lastWinery - lets look through the list
    # go through the list of wineries (global variable),
    # each row contains wineryName, wineryRegex
    # pulling out the tuple from the lookup
    for (winery, reWinery) in wineryLookup:
        # debugging
        if debug:  print('fw:not lastWinery-checking winery:', winery)

        if fldWine not in rec:
            print('not a column in this record fldWine:', fldWine)
            print('rec:', rec)
            
        # check to see if this winery is a match
        if reWinery.search(rec[fldWine]):
            # debugging
            if debug:  print('fw:winery match found:', winery)
            # this is a match - set the variables
            return (winery, reWinery)

    # for loop ends without a match
    # did not find a matching winery in the for loop - clear values
    return (None, None)

#########################################################################################
# find the liquor tied to the rec, leveraging the winery
#     Global Variable Used:  liquorLookup
#
#     returns:  (liquor, reLiquor)
#
def findLiquor( rec, winery, fldWine, debug=False ):

    # go through the list of liquors (global variable), pulling out the tuple from the lookup
    for (liquor, reLiquor) in liquorLookup[winery]:
        # debugging
        if debug:  print('fl:checking liquor:', liquor)

        # check to see if this liquor is a match
        if reLiquor.search(rec[fldWine]):
            # debugging
            if debug:  print('fl:liquor match found:', liquor)
            # this is a match - set the variables
            return (liquor, reLiquor)

    # for loop ends without a match
    # did not find a matching liquor in the for loop - clear values
    return (None, None)

#########################################################################################
# find the grape tied to the rec by regex evaluation
#
#     Global Variable Used:  grapeLookup
#
#     returns:  (grape, reGrape)
#
def findGrapeByRegex( rec, fldWine, debug=False ):

    # go through the list of liquors (global variable), pulling out the tuple from the lookup
    for (grape, reGrape) in grapeLookup:
        # debugging
        if debug:  print('fgbr:grape:', grape)

        # check to see if this liquor is a match
        if grape is not None and reGrape.search(rec[fldWine]):
            # debugging
            if debug:  print('fgbr:grape match found:', grape)
            # this is a match - set the variables
            return (grape, reGrape)

    # for loop ends without a match
    # did not find a matching grape in the for loop - clear values
    return (None, None)

#########################################################################################
# find a string in a field of a record using string match and 
# on match, return that it matched and the remainder of the string as an array
#
#    returns:  (findStr, other)
#
def findStrInRecReturnOther( rec, fldWineDescr, findStr, debug=False ):
    # find where in the string this findStr is positioned
    matchLoc = rec[fldWineDescr].find(findStr)
    # if we found a location
    if matchLoc > -1:
        # then strip everthing to the left of the findStr value and then split this to create other attributes
        other = rec[fldWineDescr][matchLoc+len(findStr)+1:].split()
        
        # debugging
        if debug:  print('fsirro:findStr matched:', findStr)
        if debug:  print('fsirro:findStr other:', other)
        
        # return what we found
        return (findStr, other)
    
    #no match found -  debugging
    if debug:  print('fsirro:findStr did not match using:', findStr)
    # did not find a matching findStr - return that fact
    return (None, [])
    
#########################################################################################
# find the grape tied to the rec and the list of other attributes
# to the right of the grape in that description
#
#     Global Variable Used:  grapeLookup
#
#     returns: (grape, other)
#
def findGrapeByStr( rec, fldWineDescr, debug=False ):
    # find the grape and strip everything right of that from the fldWineDescr field
    for (grape,reGrape) in grapeLookup:
        # debugging
        if debug:  print('fg:grape:', grape)

        # find where in the string this grape is positioned
        (grape, other) = findStrInRecReturnOther( rec, fldWineDescr, grape, debug=debug)

        # if we have a match return that match
        if grape:
            return (grape, other)
    
    # did not find a matching grape - return that fact
    return (None, [])
                    
#########################################################################################
# find the vintage tied to the rec
#
#     Global Variable Used:  vintageLookup
#
#     returns:  vintage
#
def findVintage( rec, fldWine, debug=False ):
    # loop through the vintage lookup records
    for reVintage in vintageLookup:
        # search for match
        m = reVintage.search(rec[fldWine])
        # if there is a match
        if m:
            # extract the vlaue from the first regex group with a value
            if m.group(1):
                vintage = m.group(1)
                if debug:  print('fv:vintage-match:', reVintage,':group1')
            elif m.group(2):
                vintage = m.group(2)
                if debug:  print('fv:vintage-match:', reVintage,':group2')
            elif m.group(3):
                vintage = m.group(3)
                if debug:  print('fv:vintage-match:', reVintage,':group3')
            else:
                vintage = m.group(4)
                if debug:  print('fv:vintage-match:', reVintage,':group4')
            # return what we vound
            return vintage

    # did not find it
    return None
        
#########################################################################################
# Create the winery/grape-wine-liquour conversion table based on the
# array of records passed in
#
# this routine takes the already read in list of definitions and parses them up
# in order to create a winery-wine-attributes file - that will be used
# later to take new records from searching the internet and properly assign
# an aligned/consistent wine description to that wine string
#
# we expect the wines array to have attributes:  fldWineDescr (winedescr), and fldWine (wine_name)
#
# returns:  wgLookup - dictionary - which is built from parsing winedescr NOT wine_name
#
#   wgLookup[winery][grape] = list of lists of attributes to perform lookups with
#
def buildWineryGrapeLookup( wines, fldWineDescr='winedescr', fldWine='wine', debug=False ):

    # local variables
    wgLookup = {}
    lastWinery = None
    lastReWinery = None


    # step through the records read in
    for rec in wines:
        # debugging
        if debug: print('bwgl:new rec:', rec[fldWineDescr])

        # set the variable
        if not fldWineDescr in rec:
            print('creating-field:', fldWineDescr)
            rec[fldWineDescr] = ''
            
        # local loop variables
        winery = grape = wine = liquor = None
        other = []
    
        ### WINERY
        (lastWinery, lastReWinery) = (winery, reWinery) = findWinery( rec, lastWinery, lastReWinery, fldWine, debug=debug )
        
        # if we did not find the winery - skipt this record
        if not winery:
            # debugging
            if debug:  print('bwgl:did not find winery-skipping:', rec[fldWine])
            # don't process this record - get the next record to process
            continue

        ### IGNOREGRAPE and NOGRAPE and LIQUOR

        # if this winery has a noGrapeLookup option - use that to split up the record
        if winery in ignoreGrapeLookup:
            ### BLANK WINE
        
            # don't get the grape for this winery
            # set wine to blank
            wine = ''
            # debugging
            if debug:  print('bwgl:wine check ignoreGrapeLookup on winery:', winery)
        elif winery in noGrapeLookup:
            ### NO GRAPE WINE  -- fldWineDescr
            
            # debugging
            if debug:  print('bwgl:wine check noGrapeLookup on winery:', winery)
            
            # find which wine is a match from the noGrapeLookup
            wine = wineLookupByName( noGrapeLookup[winery], rec[fldWineDescr], [], 'noGrapeLookup',  debug=debug )

            # not getting a match - we want to continue to have the wine as blank
            if False and wine == '':
                # debugging
                if debug:  print('bwgl:nograpelookup:no-match:set wine to None')
                wine = None
        elif winery in liquorLookup:
            ### LIQUOR  ---- fldWine
            # debugging
            if debug:  print('bwgl:liquor check on winery:', winery)
            # see if a liquor matches
            (liquor, reLiquor) = findLiquor( rec, winery, fldWine, debug=debug )
            # if we found match - populate wine so we don't look for grape
            if liquor is not None:
                wine = liquor
                # debugging
                if debug: print('bwgl:liquor found and put in wine:', wine)

                
        ### GRAPE (if we have not filled in wine) --- fldWineDescr
        if wine is None:
            # debugging
            if debug: print('bwgl:grape check because wine is None')
            # determine if there is a grape in this string
            # if ther
            (grape,other) = findGrapeByStr( rec, fldWineDescr )
            # debugging
            if debug: print('bwgl:grape:', grape, ':other:', other)
        else:
            # debugging
            if debug: print('bwgl:grape check skipped - we have a wine')

        ### Skip this record if we don't have a wine or a grape
        if wine is None and grape is None:
            # debugging
            if debug: print('bwgl:record skipped - no grape or wine defined')
            continue

        ### OTHER (if not already created by grape lookup) ---- fldWineDescr
        #
        # if we did not find the grape in the string
        # so other was not populated
        # we need to look up other using 'winery' as the filter
        if grape is None:
            # debugging
            if debug: print('bwgl:build other from winery')
            # find where in the string this grape is positioned
            (wineryFind, other) = findStrInRecReturnOther( rec, fldWineDescr, winery, debug=debug)

            
        ### OTHER Additional Processing

        # remove CASE - the keyword case if it exists
        if 'case' in other:
            other.remove('case')
            # debugging
            if debug:  print('bwgl:remove case from other')
        
        # remove VINTAGE and/or BOTTLESIZE and/or other QUALIFIERS
        # the last element will either be the vintage (no bottle size)
        # or will be the bottle size and then next is the vintage
        # if the last position is not vintage, attempt to remove the bottle size
        # then remove vintage - this should be the vintage (validated by isdigit lookup)
        if other:
            if debug:  print('bwgl:looking at other for quals, bottlesize and vintage')
            # remove qualifiers if exist
            if not other[-1].isdigit():
                # first we check to see if there is a qualifier appended
                # we are not vintage as the position posiition - see if it is size
                for qual,reQual in reQualLookup:
                    if qual == other[-1]:
                        if debug:  print('bwgl:remove qualifier from other:', qual)
                        del other[-1]
                        break
                
            # remove bottle size if exist
            if other and not other[-1].isdigit():
                # we are not vintage as the position posiition - see if it is size
                for size,reSize in sizeLookup:
                    if size == other[-1]:
                        if debug:  print('bwgl:remove bottlesize from other:', size)
                        del other[-1]
                        break

            # remove vintage if it is there
            if other and other[-1].isdigit():
                # first check to see if this is part of the ignore grape solution
                if winery in ignoreGrapeLookup and ignoreGrapeLookup[winery]and other[-1] in ignoreGrapeLookup[winery]:
                    if debug:  print('bwgl:value is in ignoreLookupGrape - keeping it:', other[-1])
                else:
                    # debugging
                    if debug:  print('bwgl:remove vintage from other:', other[-1])
                    del other[-1]

        # remove WINE - the element if the element is the same as the wine
        if wine and wine in other:
            other.remove(wine)
            # debugging
            if debug:  print('bwgl:remove wine from other:', wine)

        # debugging
        if debug:
            try:
                print('bwgl:Final-Build:', winery, ':', grape, ':', wine, ':', liquor, ':', other, ':', rec[fldWineDescr], ':', rec[fldWine])
            except Exception as e:
                print('debug error2-continuing:', str(e))
                print('fldWine:', fldWine)

        ### BUILD LOOKUP FOR CONVERSION (we use the grape attribute to build the dictionary)

        # move liquor value into grape because we did not find the
        if grape is None and wine is not None:
            grape = wine
            # debugging
            if debug:  print('bwgl:set-grape-to-wine:', grape)
        

        ### WINERY:GRAPE-WINE-LIQOUR Dictionary creation

        # debugging
        if debug:  print('bwgl:create wgLookup for winery:', winery, ':grape:', grape)
    
        # validate we have an entry for this winery in the lookup dict
        if winery not in wgLookup:
            # one does not create - so create a stub for winery:grape
            wgLookup[winery] = { grape : [] }
        else:
            # one DOES exist - check to see if the grape is already here
            if grape not in wgLookup[winery]:
                # grape is not here - so create an empty list to stuff values into
                wgLookup[winery][grape] = []

        # check to see if we have OTHER attributes
        # and if we do - check to see that this list of attributes
        # is not already in the wineLookup array
        # and if this list does not exist - then append this list
        if other and other not in wgLookup[winery][grape]:
            # add this list of other to this entry
            wgLookup[winery][grape].append(other)
            # debugging
            if debug:  print('bwgl:appending to wgLookup:other:', other)
    
    # end loop on wines

    ### SORTED WINERY:GRAPE lookup - most optional attributes first in the list

    # debbuging
    if debug:  print('bwgl:complete-read-of-master-file:sort wgLookup')

    # now sort the list of lookups from most specific (greatest number of attributes) to least
    for winery in wgLookup:
        for grape in wgLookup[winery]:
            wgLookup[winery][grape] = sorted(wgLookup[winery][grape], key=len, reverse=True)
            

    # debugging
    if debug:
        print('\n'*5)
        print('START WGLOOKUP DUMPED')
        print('#'*80)
        if ppFlag:
            pp.pprint(wgLookup)
        else:
            print('bwgl:final-wgLookup:\n', wgLookup)
        print('#'*80)

        
    # done with for loop - return the lookup
    return wgLookup

#########################################################################################
# find the matching set of additional attributes that match this record
# from the global lookup.
#
# we assume that we have already tested that winery and value exist in wgLookup prior to calling this routine
#
# the special paramaters here are:
#    value - this is either "wine" or "grape" - this routine allows you to lookup on different attributes
#    valueDescr - passed in string for debugging telling us which value was passed in
#
#    defaultorderlist = array of array of string - gives the default order of singlematch looks to determine which of
#                       many matches is the one we will select
#
# Global Variable Used:  wgLookup
#
# returns:  valuematchset array selected
#
def findAddAttribWgLookup( rec, winery, value, fldWine, AbbrLookup=[], defaultorderlist=None, valueDescr='', debug=False ):

    # local variable - capture all the entries that are single match entries
    singlematch=[]

    # debugging
    if debug:
        try:
            print('faawl:value:', valueDescr, ':match-wgLookup:', rec[fldWine], ':', wgLookup[winery][value])
        except Exception as e:
            print('debug error7-continuing:', str(e))
            print('fldWine:', fldWine)

    # for each set of values that could be a match
    for valuematchset in wgLookup[winery][value]:
        # debugging
        if debug:  print('faawl:testing valuematchset:', valuematchset, ':length:', len(valuematchset))
        # set the flag to start
        allmatch = True
        # loop through the set of values that make up this set
        for valuematch in valuematchset:
            # for each entry - build a regex and test it and add it up
            # we need all values in this valueset to be true for this valueset to be match
            reMatch1 = re.compile(r'\b'+valuematch+r'\b', re.IGNORECASE)
            reMatch2 = re.compile(r'\s'+valuematch+r'\s', re.IGNORECASE)
            # check to see if this regex is a match
            m1 = reMatch1.search(rec[fldWine])
            m2 = reMatch2.search(rec[fldWine])
            if m1 or m2:
                # this regex is a match
                allmatch = True and allmatch
            elif valuematch in AbbrLookup:
                # this regex was not a match - but we want to check if the value also has
                # a translation - and if it has a translation - then we test the translation also
                # the value did not work but there is an alternate value to check
                # debugging
                if debug: print('faawl:valuematch-abbr:', valuematch, ':', wineAbbrLookup[valuematch])
                # create the regex
                reMatch = re.compile(wineAbbrLookup[valuematch], re.IGNORECASE)
                # test the regex and attach the results to allmatch
                allmatch = reMatch.search(rec[fldWine]) and allmatch
            else:
                # not a match - update allmatch
                allmatch = False and allmatch
                        
            # debugging
            if debug:  print('faawl:valuematch:', valuematch, ':allmatch:', allmatch)

        # check to see if all matched
        if allmatch:
            # all matched - so this is a match - so break out of the valuematchset group
            # debugging
            if debug:  print('faawl:value matched:', valuematchset)
            # different action based on # of items being match
            if len(valuematchset) == 1:
                # debugging
                if debug: print('faawl:single-valuematch-set-added-to-singlematch:', valuematchset)
                # single value matching - we don't stop when we find a match
                singlematch.append(valuematchset)
            else:
                # debugging
                if debug: print('faawl:multivalue-valuematch-set-found:done')
                # multi value match so we are done when we find a match - so return
                return valuematchset

    # did not find matchset in the for loop  - check to see if we have singlematch
    if not singlematch:
        # debugging
        if debug:  print('faawl:exit with singlematch NOT populated return blank')
        # did not have singlematch found - we are done - return empty
        return []
        

    # singlematch populated
    # debugging
    if debug:  print('faawl:exit with singlematch populated:', singlematch)
    # check to see how many matches we got
    if len(singlematch) == 1 or not defaultorderlist:
        # debugging
        if debug:  print('faawl:return first entry in singlematch:', singlematch[0])
        # if there is only one entry in here
        # or we don't have a default order so we pick the first found
        # and we set the value to this
        return singlematch[0]

    # we need to define which of the singlematch values we will return
    # the defaultorderlist will be used to set that ordering
    #
    # create a local copy of the list that can be changed in this routine
    defaultorder = defaultorderlist[:]
        
    # multiple singlematch values so lets find and pick the best one
    # debugging
    if debug:  print('faawl:multiple single match value-singlematch:', singlematch)


    # get the values from singlematch that are not in defaultorder
    # and put them at the start of defaultorder list
    # go in reverse order when doing this lookup
    for val in singlematch[::-1]:
        if val not in defaultorder:
            defaultorder.insert(0,val)
            
    ### HARDCODED ###
    # very short term fix - we need to prioritze these single tags (mondavi problem)
    if winery == 'Mondavi' and ['Tok'] in singlematch:
        if debug:  print('faawl:Change from:', valuematchset, ':to Tok for mondavi')
        return ['Tok']

    # find the first matching value from priority order list
    for val in defaultorder:
        if val in singlematch:
            # debugging
            if debug:  print('faawl:selected-singlematch-value:', val)
            # we found the first match - set it and break out
            return val

    # debugging
    if debug:  print('faawl:valuematchset-empty')

    # did not match - return empty
    return []



#########################################################################################
# create a consistent wine name for a list or records with store based wine descriptions
#
# the special paramaters here are:
#    wgLookup - dictionary of winery, wine, list of wines
#    wines - list of records to be processed
#
# Global Variable Used:  ignoreGrapeLookup, noGrapeLookup, wineAbbrLookup, liquorLookup
#                        reCase, sizeLookup
#
# returns:  [updated values in teh wines array]
#
#### Use the winery/grape-wine-liquour conversion table to define a wine description for the records
def setWineryDescrFromWineryGrapeLookup( wgLookup, wines, fldWineDescr = 'winedescr', fldWine = 'wine', fldWineDescrNew = 'winedescrnew', fldWineDescrMatch=False, debug=False ):

    if debug:
        print('\n'*10,'START WINEDESCR SETTING HERE ---------------------------------------------')
        
    # step through all the records passed in
    for rec in wines:

        # local variables
        winery = grape = wine = vintage = case = size = liquor = nongrape = qual = None
        winematchset = grapematchset = []
    
        # debugging
        if debug:
            try:
                print('setWinery:fldWine:', rec[fldWine])
            except Exception as e:
                print('debug error2-continuing:', str(e))
                print('fldWine:', fldWine)
    
        # make the field if it does not exist
        if fldWineDescrNew not in rec:
            rec[fldWineDescrNew] = rec[fldWineDescr]
        
        ### WINERY
        (winery, reWinery) = findWinery( rec, None, None, fldWine, debug=debug )
    
        # validate the winery
        if winery is None:
            ### WINERY NONE - go to next record
            # debugging
            if debug:  print('setWinery:winery not found-next record:' + rec[fldWine])
            # get the next record
            continue
        elif winery not in wgLookup:
            ### WINERY NOT IN LOOKUP
            # skip this record - nothing to process
            # debugging
            if debug:  print('setWinery:winery not in wgLookup:', winery)
            continue

        ### GRAPE
        # find the grape that is this record
        (grape, reGrape) = findGrapeByRegex( rec, fldWine, debug=debug )

        # debugging
        if debug:  print('setWinery:grape found:', grape)
        
        ### OVERRIDES
        if winery in ignoreGrapeLookup:
            ### IGNORE GRAPE
            
            # debugging
            if debug:  print('setWinery:winery-match-ignoreGrape:clear-wine:set-grape-to-None:set-nongrape-True:winery:', winery)
            
            # clear wine and grape
            wine = ''

            # clear the grape field
            grape = None
            
            # set the liquor flag to control processing
            nongrape = True
        
        if winery in noGrapeLookup:
            ### NOGRAPE - WINE

            # debugging
            if debug:  print('setWinery:noGrapeLookup wine check:', winery)

            # do the lookup and if a search is a match on None take appropriate action
            wine = wineLookupByName( noGrapeLookup[winery], rec[fldWine], [], 'noGrapeLookup', wineAbbrLookup, debug=debug )

            # debugging
            if debug:  print('setWinery:nogrape check:wine:', wine)
        
            # test the value we got back
            if wine == '':
                # debugging
                if debug:  print('setWinery:noGrapeLookup:matched:None::clear grape:set nongrape to True')
                # the lookup match None - so we want to ignore any grape found and we blank out the wine
                grape = None
                wine = ''
                nongrape = True
            elif wine:
                # matched a wine - so clear the grape value
                grape = None
                # debugging
                if debug:  print('setWinery:nograpeLookup:wine found - clear grape field') 

        if wine is None and winery in liquorLookup:
            ### LIQUOR
            # debugging
            if debug:  print('setWinery:liqourLookup:', winery)

            (liquor, reLiquor) = findLiquor( rec, winery, fldWine, debug=debug)
            # if we found something update wine to be what we found
            if liquor is not None:
                wine = liquor
                # debugging
                if debug:  print('setWinery:liquorLookup-match:', liquor)

        if not grape and not nongrape and not wine and liquor is None:
            # NO GRAPE - and not connected to noGrapeLookup or liquorLookkup
            # get the next record
            # debugging
            if debug:  print('setWinery:did not find grape-skipping record:', rec[fldWineDescr])
            continue

        # debugging
        if debug:  print('setWinery:pre-vintage found values for wine/liquor:', wine, ':grape:', grape)
    
        ### VINTAGE
        vintage = findVintage( rec, fldWine, debug=debug )

        # debugging
        if debug:  print('setWinery:vintage:', vintage)
    
        ### CASE information
        if reCase.search(rec[fldWine]):
            case = 'case'
        
        ### BOTTLE SIZE - get the size information
        for (size, reSize) in sizeLookup:
            # debugging
            if debug:  print('setWinery:sizeLookup:',size)
            if reSize.search(rec[fldWine]) and not reShipsAs.search(rec[fldWine]):
                # debugging
                if debug:  print('setWinery:sizeLookup:matched:',reSize)
                break
        else:
            size = None
            if debug:  print('setWinery:sizeLookup:None-found')

        ### QUAL for this wine
        qual = findQualifier(rec[fldWine], debug=debug)

        # debugging
        if debug:
            try:
                print('setWinery:FinalAttributes:', winery, ':', grape, ':', wine, ':', liquor, ':', vintage, ':', case, ':', size, ':', qual, ':', rec[fldWine])
            except Exception as e:
                print('debug error5-continuing:', str(e))
                print('fldWine:', fldWine)
                

        ### WINE - ADDITIONAL INFORMATION
        if liquor is not None:
            # debugging
            if debug:  print('setWinery:liquor flag set - no additional data needs to be collected')
        elif wine is not None:

            # debugging
            if debug:  print('setWinery:wine is not None - do additional lookups:wine:', wine) 
           
            # we found a wine / liquor - so see if there are additional attributes
            if wine in wgLookup[winery] and wgLookup[winery][wine]:
                # debugging
                if debug:  print('setWinery:lookup winematchset')
                # there is one or more additional lookups for this winery/wine
                winematchset = findAddAttribWgLookup( rec, winery, wine, fldWine, wineAbbrLookup, None, valueDescr='wine', debug=debug )
            else:
                # wine not in wgLookup so thing to work
                print('setWinery:unable to perform wgLookup on winery:', winery, ':wine:', wine, ':rec-wine:',  rec[fldWine])
                # debugging
                if debug:
                    try:
                        print('wgLookup[winery]:', wgLookup[winery])
                    except Exception as e:
                        print('debug error3-continuing:', str(e))
                        print('winery:', winery)
                
            # debugging - wine is not None - what is the final winematchset
            if debug: print('setWinery:winematchset:', winematchset)
        elif grape is not None:
            # debugging
            if debug:  print('setWinery:grape is not None - do additional lookups:', grape)

            # grape was returned (not wine) so do the lookup on grape
            if grape in wgLookup[winery] and wgLookup[winery][grape]:
                # see if we can create a match based on attributes and the grape
                grapematchset = findAddAttribWgLookup( rec, winery, grape, fldWine, wineAbbrLookup, defaultorderlist, valueDescr='grape', debug=debug )

            elif grape in wgLookup[winery]:
                # do nothing this is a empty set
                if debug: print('setWinery:grape match:  matching record set is blank - no action required')
            else:
                # wine not in wgLookup so thing to work
                # debugging
                print('setWinery:grape NONMATCH:', rec[fldWine])
                if debug: print('setWinery:liquor:', liquor, ':wine:', wine, ':grape:', grape, ':wgLookup[winery]:', wgLookup[winery])

            # debugging - wine is not None - what is the final grapematchset
            if debug: print('setWinery:grapematchset:', grapematchset)

        ### check the matchsets we got back - if any of them look like vintage values
        ### remove them from the string and look at up vintage again
        if vintage:
            newVintageLookupWine = rec[fldWine]
            for matchvalue in winematchset:
                if vintage in matchvalue:
                    newVintageLookupWine = newVintageLookupWine.replace(matchvalue,'')
                    if debug:  print('setWinery:2nd-vintage:winematchset:wine-name-removal:', matchvalue)
            for matchvalue in grapematchset:
                if vintage in matchvalue:
                    newVintageLookupWine = newVintageLookupWine.replace(matchvalue,'')
                    if debug:  print('setWinery:2nd-vintage:grapematchset:wine-name-removal:', matchvalue)
            if newVintageLookupWine != rec[fldWine]:
                if debug:  print('setWinery:2nd-vintage:newVintageLookupWine:', newVintageLookupWine)
                newVintage = findVintage( { fldWine : newVintageLookupWine}, fldWine, debug=debug )
                if debug:  print('setWinery:2nd-vintage:newVintage:', newVintage)
                vintage = newVintage

        ### FINAL WINEDESCR

        # create initial value
        wineDescr = ''


        # if winery starts with a z then we don't have a vintage
        if winery.startswith('z'):
            vintage = None
            # debugging
            if debug:  print('setWinery:winery starts with z: clear vintage')

        # quick test - does the wine and the winematchset the same
        if winematchset and ' '.join(winematchset) in wine:
            #debugging
            if debug:  print('setWinery:clearing-winematchset:', winematchset,':is-in-wine:', wine)
            winematchset = []
        if grapematchset and ' '.join(grapematchset) in grape:
            #TODO - work around for single letter matches
            if not (len(grapematchset)==1 and len(grapematchset[0])==1):
                #debugging
                if debug:  print('setWinery:clearing-grapematchset:',grapematchset,':is-in-grape:', grape)
                grapematchset = []
        if grapematchset and size and size in ' '.join(grapematchset):
            size = ''
        if winematchset and size and size in ' '.join(winematchset):
            size = ''

        if debug:
            print('setWinery:vallist1:', [winery, grape, wine] + grapematchset + winematchset + [vintage, size, qual, case])
            print('setWinery:vallist2:', [winery, grape, wine, *grapematchset, *winematchset, vintage, size, qual, case])
        
        # create a list
        wdList= []
        # step through the values
        for val in [winery, grape, wine] + grapematchset + winematchset + [vintage, size, qual, case]:
            # and if there is a value add to the list - otherwise skip
            if val:  wdList.append(val)

        # build the wine description by joining all these values together
        wineDescr = ' '.join(wdList)

        # debugging
        if False:
            if debug:  print('setWinery:wdList:', wdList)
            if debug:  print('setWinery:wineDescr:', wineDescr)
    
        # debugging
        if debug:
            try:
                print(':'.join(['setWinery:wineDescrList', wineDescr, rec[fldWineDescr], str(wineDescr==rec[fldWineDescr]), rec[fldWine]]) )
            except Exception as e:
                print('debug error6-continuing:', str(e))
                print('fldWine:', fldWine)

        # fill thew new value into the array
        rec[fldWineDescrNew] = wineDescr

        # fill in the matching field
        if fldWineDescrMatch:
            rec[fldWineDescrMatch] = (rec[fldWineDescr] == rec[fldWineDescrNew])
    

#########################################################################################
# set any digit only field to the word passed 
def setDigitFld2Value( wines, fld, value, debug=False ):
    for rec in wines:
        if rec[fld].isdigit():
            rec[fld] = value

#########################################################################################
# validate the field settings match the file we read in for update
def updateFileOptionDictCheck( optiondict, wines, header, debug=False ):
    # check to see if the description field is in the file we read in
    if optiondict['fldWineDescr'] not in wines[0]:
        if debug:  print('updateFileOptionDictCheck:fldWineDescr NOT in file read in:', optiondict['fldWineDescr'])
        # field needed is not in the record - see if we know what to do
        if 'cnt' in wines[0]:
            # the cnt field is in the file - so set to that structure
            # we will put the updated values into the 'cnt' field
            print('setting values fldWineDescr and fldWineDescrNew to: cnt')
            # change the field we are updating
            optiondict['fldWineDescr'] = optiondict['fldWineDescrNew'] = 'cnt'
        elif 'winedescr' in wines[0]:
            # the WineDescr field is in the file - so set to that structure
            print('setting values fldWineDescr to winedescr and fldWineDescrNew to winedescrnew')
            # change the field we are updating
            optiondict['fldWineDescr'] = 'winedescr'
            optiondict['fldWineDescrNew'] = 'winedescrnew'
        else:
            # no idea - we need to error out
            print('could not find fldWineDescr in wines[0]-aborting:', optiondict['fldWineDescr'], '\nwines[0]:', wines[0])
            # force the error
            error = wines[0][optiondict['fldWineDescr']]

    # determine if we should create the match column (may want ot remove this section later)
    # removed this logic - require the person to set this field - we will not set it for them.
    if False and optiondict['fldWineDescr'] == 'winedescr':
        # we are using the file format that is the xref file
        # so check to see if we have match enabled
        if not optiondict['fldWineDescrMatch']:
            # create the default value
            optiondict['fldWineDescrMatch'] = 'same'
            # provide message
            print('setting value fldWineDescrMatch to: same')

    # check to see if the input file is the same as the output file
    if optiondict['csvfile_update_in'] == optiondict['csvfile_update_out']:
        # they are the same file (in and out) - so we need to move the input file to a backup location
        (file_path, base_filename, file_ext) = kvutil.filename_split(optiondict['csvfile_update_in'])
        # create the new filename
        backupfile = kvutil.filename_proper( base_filename + optiondict['backupfile_ext'], file_path )
        # messaging
        print('copying ', optiondict['csvfile_update_in'], ' to ', backupfile)
        # copy the input file to the backup filename
        shutil.copyfile(optiondict['csvfile_update_in'], backupfile)

    # set the output keys we are going to assign
    if optiondict['fldWineDescrNew'] == 'cnt':
        # output matches the original ref file format with the "cnt" field
        optiondict['csvdictkeys'] = ['cnt','date','search','store','wine','winesrt']
    elif optiondict['fldWineDescrMatch']:
        # output is a modified xref format so you can look at old and new definitions
#        optiondict['csvdictkeys'] = [optiondict['fldWineDescr'],optiondict['fldWineDescrNew'],optiondict['fldWineDescrMatch'], 'date','search','company','wine','winesrt']
        optiondict['csvdictkeys'] = [optiondict['fldWineDescr'],optiondict['fldWineDescrNew'],optiondict['fldWineDescrMatch'], *header]
    else:
        # copy over the read in format
        optiondict['csvdictkeys'] = [optiondict['fldWineDescrNew']] + header[1:]
        # output matches expected input - should really change this to be the format of the read in file
        #optiondict['csvdictkeys'] = [optiondict['fldWineDescrNew'], 'date','search','company','wine','winesrt']

    print('updateFileOptionDictCheck:set csvdictkeys to:',optiondict['csvdictkeys'])

    
# ---------------------------------------------------------------------------
if __name__ == '__main__':

    # capture the command line
    optiondict = kvutil.kv_parse_command_line( optiondictconfig, debug=False )

    # set the global debug flag
    ppFlag = optiondict['pprint']

    # set master fields
    setOptionDictMasterFldValues( optiondict, debug=False )
    
    ### global variable checks ###
    if optiondict['setup_check']:
        print('Running global variable check')
        globalVariableCheck( debug = optiondict['debug'] )
        sys.exit()
    
    # messaging
    print('reading in master file:', optiondict['csvfile_master_in'])

    # read in the MASTER FILE INPUT file
    wines,header = kvcsv.readcsv2list_with_header(optiondict['csvfile_master_in'], headerlc=True)

    # build the wine lookup dictionary
    wgLookup = buildWineryGrapeLookup( wines, optiondict['fldWineDescrMaster'], optiondict['fldWineMaster'], debug=optiondict['debug'] )

    # read in the UPDATE FILE INPUT file - if not updating the master file
    if optiondict['csvfile_master_in'] != optiondict['csvfile_update_in']:
        # messaging
        print('reading in update file:', optiondict['csvfile_update_in'])
        # read in the INPUT file
        wines,header = kvcsv.readcsv2list_with_header(optiondict['csvfile_update_in'], headerlc=True)
        # check to see if we read in any records and if not just return
        if not wines:
            print('wineset.py - no records read in - no work to be done - exitting')
            sys.exit()
    

    # test to see if we should set the fields based on what we just read in
    updateFileOptionDictCheck( optiondict, wines, header, debug=optiondict['debug'] )


    # do the assignment of wines to records
    setWineryDescrFromWineryGrapeLookup( wgLookup, wines, optiondict['fldWineDescr'], optiondict['fldWine'], optiondict['fldWineDescrNew'], optiondict['fldWineDescrMatch'], debug=optiondict['debug'] )

    # if enabled - set all unassigned new descriptions the default value
    if optiondict['defaultnew'] is not None:
        # message
        print('Setting ', optiondict['fldWineDescrNew'], ' to ', optiondict['defaultnew'], 'if not set')
        # do the work
        setDigitFld2Value( wines, optiondict['fldWineDescrNew'], optiondict['defaultnew'], debug=optiondict['debug'] )

    # save the output to the file of interest
    kvcsv.writelist2csv( optiondict['csvfile_update_out'], wines, optiondict['csvdictkeys'] )

    # messaging
    print('Saved results to:', optiondict['csvfile_update_out'])

