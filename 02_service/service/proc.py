import sys
import os
import argparse
import zipfile
from PyPDF2 import PdfFileMerger, PdfFileWriter, PdfFileReader

# Accept a list of pdfs, merge them into one
def merge(input_path, output_path):
    merger = PdfFileMerger()
    for pdf in input_path:
        merger.append(pdf)

    merger.write(output_path)


# Accepts one pdf file, split it by each page, output as zip
def split(input_path, output_path):
    path = 'output'
    inputpdf = PdfFileReader(open(input_path, "rb"))
    outputzip = zipfile.ZipFile(output_path, 'w')

    os.mkdir(path)
    for i in range(inputpdf.numPages):
        output = PdfFileWriter()
        output.addPage(inputpdf.getPage(i))
        filename = path+ '/result_page_'+str(i+1)+'.pdf'
        with open(filename, "wb") as outputStream:
            output.write(outputStream)

    for folder, subfolders, files in os.walk(path):
        for file in files:
            outputzip.write(os.path.join(path, file), file, compress_type = zipfile.ZIP_DEFLATED)

    outputzip.close()

    os.system('rm -rf %s' % (path))


def main(argv):
    # Parse argument
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input", 
                        action="store", dest="input", help="input file path", required=True)
    parser.add_argument("-o", "--output", 
                        action="store", dest="output", help="output file path", required=True)
    parser.add_argument("-m", "--merge", 
                        action="store_true", help="merge pdf files")
    options = parser.parse_args()

    if(options.merge):
        merge(options.input, options.output)
    else:
        split(options.input, options.output)


if __name__=="__main__":
    main(sys.argv)