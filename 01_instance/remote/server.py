import sys
import os
import sqlite3


def main(argv):
    conn = sqlite3.connect('example.db')
    c = conn.cursor()
    
    conn.close()


if __name__ == "__main__":
    main(sys.argv)
