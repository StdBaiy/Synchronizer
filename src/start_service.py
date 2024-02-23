import argparse
from Synchronizer.api import start_scanner, start_server

parser = argparse.ArgumentParser()
parser.add_argument('--type', type=str, help="input 'scanner' or 'server' to choose one of them")
# parser.add_argument('--switch', type=str, help="input 'on' or 'off' to control service")

args = parser.parse_args()


if args.type == 'scanner':
    start_scanner()
elif args.type == 'server':
    start_server()