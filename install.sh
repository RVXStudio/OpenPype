#!/usr/bin/env bash


rsync -vrlptDI server_addon/package/ pipedev:/root/ayon-docker/addons
