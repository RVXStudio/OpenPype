#!/usr/bin/env bash

RST='\033[0m'             # Text Reset

# Regular Colors
Black='\033[0;30m'        # Black
Red='\033[0;31m'          # Red
Green='\033[0;32m'        # Green
Yellow='\033[0;33m'       # Yellow
Blue='\033[0;34m'         # Blue
Purple='\033[0;35m'       # Purple
Cyan='\033[0;36m'         # Cyan
White='\033[0;37m'        # White

echo -e "${Red}Updating windows ...$RST"
rsync -av openpype /pipeline/AstralProjection/apps/ayon/builds/ayon_3.15.8_win/ --delete --exclude *.pyc --exclude __pycache__
echo -e "${Cyan}Updating linux ...$RST"
rsync -av openpype /pipeline/AstralProjection/apps/ayon/builds/ayon_3.15.8_linux/ --delete --exclude *.pyc --exclude __pycache__
echo -e "${Green}Done! $RST"

# tput sgr0
