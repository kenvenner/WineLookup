import os
import sys

#### output file settings
output_path = 'dropbox/linuxshare/wine'

homedir = os.path.expanduser("~")
output_filename ='winehydrate.csv'
full_output_filename = output_filename

if output_path:
    full_output_filename = os.path.join(homedir, output_path, output_filename)

# now get the file opened
fpOut = open(full_output_filename, 'w')

# max columns we are importing into SQL
maxCols = 13

# starting message
input_file = 'winesrch.csv'
print('Reading and converting:', input_file)

# read in file and convert
with open(input_file,'r') as src_file:
    for line in src_file:
        stripped_line = line.strip()
        current_col_count = len(stripped_line.split(','))
        hydrated_line = stripped_line+','*(maxCols-current_col_count)
        fpOut.write(hydrated_line+"\n")

fpOut.close()

# output message:
print('created file:', os.path.normcase(full_output_filename))

#eof
