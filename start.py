import sys
import os

# os.system('clear')

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))

from cockpitdecks.start import main

if __name__ == "__main__":
    main()
